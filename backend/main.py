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

# 🔓 CORS (libera todas as origens)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 🧭 Caminhos absolutos robustos
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

# Verifica também um nível acima (caso o Render mude a raiz)
ALT_STATIC_DIR = os.path.abspath(os.path.join(BASE_DIR, "../static"))
VIEWER_FILE = None

if os.path.exists(os.path.join(STATIC_DIR, "viewer.html")):
    VIEWER_FILE = os.path.join(STATIC_DIR, "viewer.html")
elif os.path.exists(os.path.join(ALT_STATIC_DIR, "viewer.html")):
    VIEWER_FILE = os.path.join(ALT_STATIC_DIR, "viewer.html")

print(f"📁 [Nexus] Static path detectado: {STATIC_DIR}")
print(f"📄 [Nexus] Viewer file detectado: {VIEWER_FILE}")

# Monta pasta estática, escolhendo a que existe
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
elif os.path.exists(ALT_STATIC_DIR):
    app.mount("/static", StaticFiles(directory=ALT_STATIC_DIR), name="static")

# 📦 Controle de stream
active_viewers = set()
latest_frame = None

@app.get("/")
async def root():
    return {
        "status": "Nexus Mobile AI ativo",
        "viewer_url": "/viewer",
        "stream_ws": "/ws/stream",
        "timezone": "America/Sao_Paulo",
    }

@app.get("/viewer")
async def get_viewer():
    if not VIEWER_FILE or not os.path.exists(VIEWER_FILE):
        print("⚠️ viewer.html não encontrado. Caminho atual:", VIEWER_FILE)
        return JSONResponse({"error": "viewer.html não encontrado"}, status_code=404)
    return FileResponse(VIEWER_FILE)

@app.get("/health")
async def health_check():
    return {"status": "ok", "time": datetime.now().isoformat()}

# 🧩 WebSocket - Recebe da extensão
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
                    # retransmitir para todos viewers conectados
                    for viewer in list(active_viewers):
                        try:
                            await viewer.send_text(json.dumps(data))
                        except Exception:
                            active_viewers.remove(viewer)
                    print(f"📦 Frame recebido e retransmitido para {len(active_viewers)} viewers.")
            except json.JSONDecodeError:
                print("⚠️ Erro JSON recebido do WS.")
    except WebSocketDisconnect:
        print("🔴 Extensão desconectada")

# 🧠 Viewer WebSocket (recebe e mostra stream)
@app.websocket("/ws/viewer")
async def ws_viewer(websocket: WebSocket):
    await websocket.accept()
    active_viewers.add(websocket)
    print("👁️ Viewer conectado...")

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

# Fallback via POST
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
