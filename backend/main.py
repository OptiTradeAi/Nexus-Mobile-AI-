from fastapi import FastAPI, WebSocket, Request, Query, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import asyncio, json, base64
from datetime import datetime
import pytz
import os

from .ai_engine_fusion import analyze_frame # Importa corretamente

app = FastAPI(title="Nexus Mobile AI Stream Server")
TZ = pytz.timezone("America/Sao_Paulo")

# --- Configuração de CORS ---
# Permite acesso de qualquer origem. Em produção, restrinja a domínios específicos.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Permite todas as origens para facilitar o desenvolvimento
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Static Files e Viewer ---
# Monta a pasta 'static' para servir arquivos como viewer.html
app.mount("/static", StaticFiles(directory="backend/static"), name="static")

@app.get("/")
async def root():
    return {
        "status": "Nexus Mobile AI ativo",
        "viewer_url": "/static/viewer.html",
        "stream_ws": "/ws/stream",
        "viewer_ws": "/ws/viewer"
    }

@app.get("/health")
async def health():
    return {"status": "ok", "time": datetime.now(TZ).isoformat()}

# --- Autenticação (opcional) ---
# Defina um token seguro como variável de ambiente no Render (ex: NEXUS_WS_TOKEN)
# Se não definido, a autenticação é desabilitada.
AUTH_TOKEN = os.environ.get("NEXUS_WS_TOKEN", "")

# --- Gerenciamento de Conexões WebSocket ---
stream_clients = set() # Clientes que enviam o stream (userscript)
viewer_clients = set() # Clientes que recebem o stream (seu viewer.html)

# --- WebSocket para o Userscript (envia frames) ---
@app.websocket("/ws/stream")
async def websocket_stream_endpoint(websocket: WebSocket, token: str = Query(None)):
    if AUTH_TOKEN and token != AUTH_TOKEN:
        print(f"🚫 Conexão de stream recusada: token inválido de {websocket.client.host}")
        await websocket.close(code=1008) # Código 1008 indica violação de política
        return

    await websocket.accept()
    stream_clients.add(websocket)
    print(f"🟢 Streamer conectado: {websocket.client.host}")

    try:
        while True:
            message = await websocket.receive() # Recebe mensagem (pode ser texto ou bytes)

            frame_data = None
            mime_type = "image/webp" # Padrão para o userscript

            if "text" in message and message["text"]:
                # Mensagem de texto (JSON com base64)
                try:
                    payload = json.loads(message["text"])
                    if payload.get("type") == "frame" and payload.get("data"):
                        frame_data = payload["data"] # Já é base64
                        mime_type = payload.get("mime", "image/webp")
                except json.JSONDecodeError:
                    print(f"⚠️ Streamer {websocket.client.host} enviou JSON inválido.")
                    continue
            elif "bytes" in message and message["bytes"]:
                # Mensagem binária (blob direto)
                # Se o userscript enviar binário, ele precisa enviar o mime-type separadamente
                # ou o backend precisa inferir. Por simplicidade, assumimos webp.
                frame_data = base64.b64encode(message["bytes"]).decode("utf-8")
                mime_type = "image/webp" # Assumimos WebP para binário

            if frame_data:
                # Analisa o frame (ai_engine_fusion)
                analysis_result = analyze_frame(frame_data, mime=mime_type)

                # Prepara o pacote para os viewers
                viewer_packet = {
                    "type": "frame",
                    "data": frame_data, # Envia base64 para o viewer
                    "mime": mime_type,
                    "analysis": analysis_result,
                    "timestamp": datetime.now(TZ).isoformat()
                }

                # Broadcast para todos os viewers conectados
                for client in list(viewer_clients):
                    try:
                        await client.send_json(viewer_packet)
                    except Exception:
                        print(f"🔴 Viewer desconectado durante broadcast: {client.client.host}")
                        viewer_clients.remove(client)
            await asyncio.sleep(0.001) # Pequena pausa para não bloquear o loop de eventos

    except WebSocketDisconnect:
        print(f"🔴 Streamer desconectado: {websocket.client.host}")
    except Exception as e:
        print(f"❌ Erro no stream de {websocket.client.host}: {e}")
    finally:
        stream_clients.remove(websocket)

# --- WebSocket para o Viewer (recebe frames) ---
@app.websocket("/ws/viewer")
async def websocket_viewer_endpoint(websocket: WebSocket):
    await websocket.accept()
    viewer_clients.add(websocket)
    print(f"🟢 Viewer conectado: {websocket.client.host}")

    try:
        while True:
            # Viewers não enviam dados, apenas recebem.
            # Mantemos o loop para a conexão permanecer aberta.
            await websocket.receive_text() # Apenas para manter a conexão viva, ignora o que for enviado
    except WebSocketDisconnect:
        print(f"🔴 Viewer desconectado: {websocket.client.host}")
    except Exception as e:
        print(f"❌ Erro no viewer de {websocket.client.host}: {e}")
    finally:
        viewer_clients.remove(websocket)

# --- Rota para o viewer.html ---
@app.get("/viewer")
async def get_viewer_page():
    # Serve o viewer.html diretamente da pasta static
    return FileResponse("backend/static/viewer.html", media_type="text/html")
