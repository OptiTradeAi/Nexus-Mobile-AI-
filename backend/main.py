import os
import base64
import json
import asyncio
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Nexus Mobile AI")

# Permitir origem cruzada (Render + localhost + HomeBroker)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 🧩 Caminho absoluto para a pasta static
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
VIEWER_FILE = os.path.join(STATIC_DIR, "viewer.html")

# Monta arquivos estáticos
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# 🧠 Variáveis globais para stream
active_viewers = set()
latest_frame = None

# ✅ Página inicial (status)
@app.get("/")
async def root():
    return {
        "status": "Nexus Mobile AI ativo",
        "viewer_url": "/viewer",
        "stream": "/ws/stream",
        "timezone": "America/Sao_Paulo"
    }

# ✅ Viewer HTML
@app.get("/viewer")
async def get_viewer():
    if not os.path.exists(VIEWER_FILE):
        return JSONResponse({"error": "viewer.html não encontrado"}, status_code=404)
    return FileResponse(VIEWER_FILE)

# ✅ Health check (usado pela extensão)
@app.get("/health")
async def health_check():
    return {"status": "ok", "time": datetime.now().isoformat()}

# ✅ WebSocket: recebe dados da extensão
@app.websocket("/ws/stream")
async def ws_stream(websocket: WebSocket):
    await websocket.accept()
    print("🟢 Extensão conectada e enviando dados...")
    global latest_frame

    try:
        while True:
            msg = await websocket.receive_text()
            try:
                data = json.loads(msg)
                if data.get("type") == "frame":
                    latest_frame = data
                    # retransmitir para todos os viewers conectados
                    for viewer in list(active_viewers):
                        try:
                            await viewer.send_text(json.dumps(data))
                        except Exception:
                            active_viewers.remove(viewer)
                    print(f"📦 Frame recebido e retransmitido ({len(active_viewers)} viewers)")
            except json.JSONDecodeError:
                print("⚠️ Erro ao decodificar mensagem JSON")
    except WebSocketDisconnect:
        print("🔴 Extensão desconectada")

# ✅ WebSocket: viewers (visualização ao vivo)
@app.websocket("/ws/viewer")
async def ws_viewer(websocket: WebSocket):
    await websocket.accept()
    active_viewers.add(websocket)
    print("👁️ Novo viewer conectado...")

    # Se já houver um frame, envia o último para inicializar a tela
    if latest_frame:
        try:
            await websocket.send_text(json.dumps(latest_frame))
        except Exception:
            pass

    try:
        while True:
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        active_viewers.remove(websocket)
        print("👁️ Viewer desconectado")

# ✅ Fallback POST (caso WS falhe)
@app.post("/frame")
async def post_frame(data: dict):
    global latest_frame
    latest_frame = data
    for viewer in list(active_viewers):
        try:
            await viewer.send_text(json.dumps(data))
        except Exception:
            active_viewers.remove(viewer)
    return {"status": "ok", "received": True}
