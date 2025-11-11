from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import pytz
from datetime import datetime
import base64
import os

app = FastAPI(title="Nexus Mobile AI")

# Monta a pasta STATIC (agora dentro de /backend/static)
app.mount("/static", StaticFiles(directory="backend/static"), name="static")

# Permitir acesso da extensão e do viewer
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Timezone Brasil
TZ = pytz.timezone("America/Sao_Paulo")

# Armazena WebSockets conectados
active_streams = set()
active_viewers = set()

@app.get("/")
async def root():
    """Rota principal de status"""
    return {
        "status": "Nexus Mobile AI ativo",
        "viewer_url": "/viewer",
        "stream": "/ws/stream",
        "timezone": "America/Sao_Paulo"
    }

@app.get("/viewer", response_class=HTMLResponse)
async def get_viewer():
    """Serve a página do visualizador"""
    viewer_path = os.path.join("backend", "static", "viewer.html")
    if not os.path.exists(viewer_path):
        return HTMLResponse("<h3>Erro: viewer.html não encontrado.</h3>", status_code=404)
    with open(viewer_path, "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())

@app.get("/health")
async def health_check():
    """Verifica se o servidor está ativo"""
    return {"status": "ok", "time": datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")}

# ------------------------------
# WebSocket: Extensão envia frames aqui
# ------------------------------
@app.websocket("/ws/stream")
async def ws_stream(websocket: WebSocket):
    await websocket.accept()
    active_streams.add(websocket)
    print("🟢 Extensão conectada e enviando dados...")
    try:
        while True:
            data = await websocket.receive_text()
            # Reenvia frame recebido para todos os viewers conectados
            for v in active_viewers.copy():
                try:
                    await v.send_text(data)
                except Exception:
                    active_viewers.remove(v)
            print("📦 Frame recebido e enviado aos viewers.")
    except WebSocketDisconnect:
        print("🔴 Extensão desconectada.")
        active_streams.remove(websocket)
    except Exception as e:
        print("⚠️ Erro no stream:", e)
        if websocket in active_streams:
            active_streams.remove(websocket)

# ------------------------------
# WebSocket: Viewer recebe os frames
# ------------------------------
@app.websocket("/ws/viewer")
async def ws_viewer(websocket: WebSocket):
    await websocket.accept()
    active_viewers.add(websocket)
    print("👁️ Visualizador conectado...")
    try:
        while True:
            await websocket.receive_text()  # apenas mantém a conexão viva
    except WebSocketDisconnect:
        print("👁️ Visualizador desconectado.")
        active_viewers.remove(websocket)

# ------------------------------
# Endpoint alternativo: POST direto (fallback)
# ------------------------------
@app.post("/frame")
async def receive_frame(payload: dict):
    """Recebe frame em base64 (quando WS não disponível)"""
    try:
        data_b64 = payload.get("data")
        pair = payload.get("pair", "N/A")
        if not data_b64:
            return JSONResponse({"error": "Frame inválido"}, status_code=400)
        
        # Envia para todos os viewers conectados
        for v in active_viewers.copy():
            try:
                await v.send_text(data_b64)
            except Exception:
                active_viewers.remove(v)
        
        print(f"📩 Frame recebido via POST do par {pair}")
        return {"status": "ok", "pair": pair}
    except Exception as e:
        print("Erro em /frame:", e)
        return JSONResponse({"error": str(e)}, status_code=500)
