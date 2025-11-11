from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import pytz
import json
import os

app = FastAPI(title="Nexus Mobile AI - Backend")

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- VARIÁVEIS GLOBAIS ---
TZ = pytz.timezone("America/Sao_Paulo")
VIEWERS = set()
STREAM_CLIENTS = set()
LATEST_FRAME = None


# ==========================================================
# 🧩 HEALTH CHECK
# ==========================================================
@app.get("/health")
async def health():
    return {"status": "ok", "time": datetime.now(TZ).isoformat()}


# ==========================================================
# 🧠 WEBSOCKET DE STREAM (RECEBE FRAMES DA EXTENSÃO)
# ==========================================================
@app.websocket("/ws/stream")
async def stream_ws(websocket: WebSocket):
    await websocket.accept()
    STREAM_CLIENTS.add(websocket)
    print("🟢 Extensão conectada.")
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("type") == "frame":
                    global LATEST_FRAME
                    LATEST_FRAME = msg
                    # retransmite aos viewers
                    dead = []
                    for v in VIEWERS:
                        try:
                            await v.send_text(json.dumps(msg))
                        except:
                            dead.append(v)
                    for d in dead:
                        VIEWERS.remove(d)
            except Exception as e:
                print("Erro ao processar mensagem WS:", e)
    except WebSocketDisconnect:
        STREAM_CLIENTS.remove(websocket)
        print("🔴 Extensão desconectada.")


# ==========================================================
# 👁️ WEBSOCKET VIEWER (EXIBE OS FRAMES NA TELA)
# ==========================================================
@app.websocket("/ws/viewer")
async def viewer_ws(websocket: WebSocket):
    await websocket.accept()
    VIEWERS.add(websocket)
    print("👁️ Visualizador conectado.")
    try:
        # envia último frame se já existir
        if LATEST_FRAME:
            await websocket.send_text(json.dumps(LATEST_FRAME))
        while True:
            await websocket.receive_text()  # mantem conexão
    except WebSocketDisconnect:
        VIEWERS.remove(websocket)
        print("👁️ Visualizador desconectado.")


# ==========================================================
# 📦 ROTA ALTERNATIVA (RECEBE VIA POST CASO WS FALHE)
# ==========================================================
@app.post("/frame")
async def frame_post(payload: dict):
    global LATEST_FRAME
    LATEST_FRAME = payload
    dead = []
    for v in VIEWERS:
        try:
            await v.send_text(json.dumps(payload))
        except:
            dead.append(v)
    for d in dead:
        VIEWERS.remove(d)
    rid = datetime.now(TZ).strftime("%Y%m%d%H%M%S%f")
    return JSONResponse({"status": "ok", "rid": rid})


# ==========================================================
# 📈 ROTA VISUAL (MOSTRA O STREAM AO VIVO)
# ==========================================================
@app.get("/viewer")
async def viewer():
    viewer_path = os.path.join("backend", "viewer.html")
    if not os.path.exists(viewer_path):
        return JSONResponse({"error": "viewer.html não encontrado"}, status_code=404)
    with open(viewer_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


# ==========================================================
# 🧩 INDEX SIMPLES
# ==========================================================
@app.get("/")
async def index():
    return {
        "status": "Nexus Mobile AI ativo",
        "viewer_url": "/viewer",
        "stream": "/ws/stream",
        "timezone": "America/Sao_Paulo"
    }
