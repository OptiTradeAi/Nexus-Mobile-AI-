import os
import base64
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import pytz
import json

app = FastAPI(title="Nexus Mobile AI Stream Server")

# 🌎 Fuso horário de Brasília
TZ = pytz.timezone("America/Sao_Paulo")

# 🔄 Armazena as conexões WebSocket
active_streams = set()
active_viewers = set()

# 🔐 Configuração de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 🧭 Página inicial
@app.get("/")
async def root():
    return {
        "status": "Nexus Mobile AI ativo",
        "viewer_url": "/viewer",
        "stream": "/ws/stream",
        "timezone": "America/Sao_Paulo"
    }

# 🧩 Serve o arquivo viewer.html
@app.get("/viewer")
async def serve_viewer():
    file_path = os.path.join(os.path.dirname(__file__), "static", "viewer.html")
    if not os.path.exists(file_path):
        return {"error": "viewer.html não encontrado"}
    return FileResponse(file_path, media_type="text/html")

# 🧠 WebSocket que recebe as capturas da extensão
@app.websocket("/ws/stream")
async def websocket_stream(ws: WebSocket):
    await ws.accept()
    client_ip = ws.client.host
    print(f"🟢 Extensão conectada: {client_ip}")
    active_streams.add(ws)

    try:
        while True:
            data = await ws.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("type") == "frame":
                    # repassa para todos os viewers conectados
                    for v in list(active_viewers):
                        try:
                            await v.send_text(json.dumps({
                                "type": "frame",
                                "pair": msg.get("pair"),
                                "timestamp": msg.get("timestamp"),
                                "data": msg.get("data")
                            }))
                        except Exception:
                            active_viewers.discard(v)
                else:
                    print(f"📦 Mensagem não reconhecida: {msg}")
            except json.JSONDecodeError:
                print("⚠️ Dados recebidos não são JSON válidos")

    except WebSocketDisconnect:
        print(f"🔴 Extensão desconectada: {client_ip}")
        active_streams.discard(ws)

# 👁️ WebSocket dos visualizadores (Render UI)
@app.websocket("/ws/viewer")
async def websocket_viewer(ws: WebSocket):
    await ws.accept()
    client_ip = ws.client.host
    print(f"👁️ Viewer conectado: {client_ip}")
    active_viewers.add(ws)

    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        print(f"👁️ Viewer desconectado: {client_ip}")
        active_viewers.discard(ws)

# 🚀 Health check
@app.get("/health")
async def health():
    return {"status": "ok", "active_streams": len(active_streams), "active_viewers": len(active_viewers)}

# 🔥 Inicialização
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
