from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import json
import pytz
import asyncio
from datetime import datetime

# Import AI engine module
from .ai_engine_fusion import analyze_frame, get_logs

TZ = pytz.timezone("America/Sao_Paulo")

app = FastAPI(title="Nexus Mobile AI - Backend")

# ---------------- CORS ----------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------- STATIC FILES ---------------
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# --------------- ROUTES ---------------
@app.get("/")
def root():
    return {
        "status": "Nexus Mobile AI ativo",
        "viewer": "/static/viewer.html",
        "ws_stream": "/ws/stream",
        "ws_viewer": "/ws/viewer"
    }

@app.get("/health")
def health():
    return {"ok": True, "time": datetime.now(TZ).isoformat()}


# --------------- WEBSOCKETS ---------------
STREAM_CLIENTS = set()
VIEWER_CLIENTS = set()
LAST_FRAME = None
LOCK = asyncio.Lock()


@app.websocket("/ws/stream")
async def ws_stream(websocket: WebSocket):
    """Recebe frames da extensão ou do selenium agent."""
    await websocket.accept()
    STREAM_CLIENTS.add(websocket)

    try:
        while True:
            message = await websocket.receive_text()
            payload = json.loads(message)

            if payload.get("type") != "frame":
                continue

            frame_b64 = payload.get("data")
            mime = payload.get("mime", "image/webp")
            pair = payload.get("pair", "AUTO")

            analysis = analyze_frame(frame_b64, mime=mime, pair=pair)

            global LAST_FRAME
            async with LOCK:
                LAST_FRAME = {
                    "data": frame_b64,
                    "mime": mime,
                    "pair": pair,
                    "analysis": analysis,
                    "ts": datetime.now(TZ).isoformat()
                }

    except WebSocketDisconnect:
        pass
    finally:
        STREAM_CLIENTS.discard(websocket)


@app.websocket("/ws/viewer")
async def ws_viewer(websocket: WebSocket):
    """Envia frames atualizados para o painel visual."""
    await websocket.accept()
    VIEWER_CLIENTS.add(websocket)

    try:
        if LAST_FRAME:
            await websocket.send_json({"type": "frame", **LAST_FRAME})

        while True:
            await asyncio.sleep(0.4)
            if LAST_FRAME:
                await websocket.send_json({"type": "frame", **LAST_FRAME})

    except WebSocketDisconnect:
        pass
    finally:
        VIEWER_CLIENTS.discard(websocket)


@app.get("/viewer")
def viewer():
    html = (STATIC_DIR / "viewer.html").read_text(encoding="utf-8")
    return HTMLResponse(html)


@app.get("/admin/logs")
def logs():
    return get_logs()
