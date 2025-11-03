# main.py
import os
import io
import uuid
import json
import base64
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Set

from fastapi import FastAPI, Request, HTTPException, Body, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, RedirectResponse, FileResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from PIL import Image, UnidentifiedImageError

# ----------------------
# Config from env
# ----------------------
TMP_DIR = Path(os.environ.get("NEXUS_FRAMES_DIR", "/tmp/nexus_frames"))
TMP_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = Path(os.environ.get("NEXUS_LOG_FILE", "nexus_app.log"))
DEBUG_LOG_TOKEN = os.environ.get("DEBUG_LOG_TOKEN", "")
DEBUG_WS_TOKEN = os.environ.get("DEBUG_WS_TOKEN", DEBUG_LOG_TOKEN)
ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "*")

# ----------------------
# Logging
# ----------------------
logger = logging.getLogger("nexus")
logger.setLevel(logging.INFO)
fmt = logging.Formatter("[%(asctime)s] %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S")
# stdout
sh = logging.StreamHandler()
sh.setFormatter(fmt)
logger.addHandler(sh)
# file
try:
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)
except Exception:
    logger.exception("Could not open log file, continuing with stdout only")

# ----------------------
# FastAPI app + CORS
# ----------------------
app = FastAPI(title="Nexus Mobile AI Backend")

if ALLOWED_ORIGINS == "*" or not ALLOWED_ORIGINS:
    origins = ["*"]
else:
    origins = [o.strip() for o in ALLOWED_ORIGINS.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------
# Simple in-memory counter
# ----------------------
frames_received = 0

# ----------------------
# Models
# ----------------------
class FramePayload(BaseModel):
    type: Optional[str] = "frame"
    pair: Optional[str] = None
    data: str
    mime: Optional[str] = "image/jpeg"

# ----------------------
# WS Connection Manager
# ----------------------
class ConnectionManager:
    def __init__(self):
        self.active: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket, token: Optional[str] = None):
        # Validate token if configured
        if DEBUG_WS_TOKEN and token != DEBUG_WS_TOKEN:
            await websocket.close(code=1008)  # policy violation
            logger.info("WS connection rejected: invalid token")
            return False
        await websocket.accept()
        self.active.add(websocket)
        logger.info(f"WS CONNECT - clients={len(self.active)}")
        return True

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active:
            self.active.remove(websocket)
        logger.info(f"WS DISCONNECT - clients={len(self.active)}")

    async def broadcast(self, message: str):
        to_remove = []
        for ws in list(self.active):
            try:
                await ws.send_text(message)
            except Exception:
                logger.exception("WS send error, removing client")
                to_remove.append(ws)
        for ws in to_remove:
            self.disconnect(ws)

manager = ConnectionManager()

# ----------------------
# Routes
# ----------------------
@app.get("/")
async def root():
    return RedirectResponse("/health")

@app.get("/health")
async def health():
    return JSONResponse({"status": "ok", "frames_received": frames_received})

@app.post("/echo")
async def echo(payload: dict = Body(...)):
    return JSONResponse({"received": payload})

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: Optional[str] = Query(None)):
    ok = await manager.connect(websocket, token)
    if not ok:
        # connection closed in connect() if token invalid
        return
    try:
        while True:
            # receive messages (optional) and rebroadcast
            data = await websocket.receive_text()
            logger.info(f"WS RX msg len={len(data)}")
            # simple rebroadcast of messages received from clients
            await manager.broadcast(data)
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.post("/frame")
async def receive_frame(request: Request, payload: FramePayload):
    """
    Recebe frame base64, verifica com Pillow, salva e broadcast via WS.
    """
    global frames_received
    rid = str(uuid.uuid4())
    client_host = request.client.host if request.client else "unknown"
    origin = request.headers.get("origin", "")
    ua = request.headers.get("user-agent", "")
    content_length = request.headers.get("content-length", "unknown")

    logger.info(f"FRAME_RECEIVE rid={rid} from={client_host} origin={origin} ua={ua} content-length={content_length}")

    # decode base64
    try:
        b64 = payload.data
        bdata = base64.b64decode(b64)
        logger.info(f"rid={rid} decoded lengths b64_len={len(b64)} raw_len={len(bdata)}")
    except Exception as e:
        logger.exception(f"rid={rid} base64 decode error")
        raise HTTPException(status_code=400, detail=f"Invalid base64 data: {e}")

    # save raw .b64 (debug)
    try:
        raw_name = f"AUTO-{datetime.utcnow().strftime('%Y%m%dT%H%M%S%f')}-rid{rid}.b64"
        raw_path = TMP_DIR / raw_name
        with raw_path.open("wb") as f:
            f.write(bdata)
    except Exception:
        logger.exception(f"rid={rid} failed saving raw blob")

    pillow_ok = False
    pillow_error = None
    saved_image_name = None

    # verify with Pillow
    try:
        img = Image.open(io.BytesIO(bdata))
        img.verify()
        img = Image.open(io.BytesIO(bdata)).convert("RGB")
        pillow_ok = True
        logger.info(f"rid={rid} Pillow verification OK")
    except UnidentifiedImageError as e:
        pillow_error = f"UnidentifiedImageError: {e}"
        logger.exception(f"rid={rid} Pillow UnidentifiedImageError")
    except Exception as e:
        pillow_error = f"Error: {e}"
        logger.exception(f"rid={rid} Pillow error")

    if pillow_ok:
        try:
            saved_image_name = f"AUTO-{datetime.utcnow().strftime('%Y%m%dT%H%M%S%f')}-rid{rid}.jpg"
            saved_path = TMP_DIR / saved_image_name
            img.save(saved_path, format="JPEG", quality=85)
            logger.info(f"rid={rid} Saved JPEG to {saved_path}")
        except Exception:
            logger.exception(f"rid={rid} failed saving JPEG image")

    frames_received += 1

    response_payload = {
        "received": True,
        "rid": rid,
        "pillow_ok": pillow_ok,
        "pillow_error": pillow_error,
        "saved": str(saved_image_name) if saved_image_name else None,
        "pair": payload.pair or "AUTO",
        "origin": origin,
    }

    # --- broadcast via WebSocket to connected clients ---
    try:
        ws_payload = {
            "type": "frame",
            "rid": rid,
            "pair": payload.pair or "AUTO",
            "saved": saved_image_name,
            "pillow_ok": pillow_ok,
            "data_b64": b64
        }
        await manager.broadcast(json.dumps(ws_payload))
    except Exception:
        logger.exception(f"rid={rid} broadcast error")

    return JSONResponse(response_payload)

# ----------------------
# Debug endpoints (token-protected)
# ----------------------
@app.get("/debug/logs")
async def debug_logs(lines: int = Query(200, ge=1, le=2000), token: str = Query(...)):
    if not DEBUG_LOG_TOKEN or token != DEBUG_LOG_TOKEN:
        raise HTTPException(status_code=403, detail="Forbidden")
    try:
        if not LOG_FILE.exists():
            return PlainTextResponse("", status_code=200)
        with LOG_FILE.open("rb") as f:
            f.seek(0, os.SEEK_END)
            end = f.tell()
            size = 1024
            data = b""
            while end > 0 and data.count(b"\n") <= lines:
                read_size = min(size, end)
                f.seek(end - read_size, os.SEEK_SET)
                chunk = f.read(read_size)
                data = chunk + data
                end -= read_size
                if end == 0:
                    break
            text = data.decode("utf-8", errors="ignore")
            lines_all = text.splitlines()[-lines:]
            return PlainTextResponse("\n".join(lines_all), media_type="text/plain")
    except Exception:
        logger.exception("debug/logs read error")
        raise HTTPException(status_code=500, detail="Unable to read logs")

@app.get("/debug/getfile")
async def debug_getfile(file: str = Query(...), token: str = Query(...)):
    if not DEBUG_LOG_TOKEN or token != DEBUG_LOG_TOKEN:
        raise HTTPException(status_code=403, detail="Forbidden")
    file_path = TMP_DIR / Path(file).name
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path=str(file_path), filename=file_path.name, media_type="application/octet-stream")

# ----------------------
# Run (for local dev)
# ----------------------
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
