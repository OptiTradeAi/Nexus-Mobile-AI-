# backend/main.py
import os
import io
import uuid
import json
import base64
import logging
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Set, Dict, Any, List

from fastapi import FastAPI, Request, HTTPException, Body, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, RedirectResponse, FileResponse, PlainTextResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from PIL import Image, UnidentifiedImageError
from gtts import gTTS

# ---------- Config (ajuste via ENV se quiser) ----------
TMP_DIR = Path(os.environ.get("NEXUS_FRAMES_DIR", "/tmp/nexus_frames"))
TMP_DIR.mkdir(parents=True, exist_ok=True)
AUDIO_DIR = TMP_DIR / "audio"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)
SIGNALS_FILE = Path(os.environ.get("NEXUS_SIGNALS_FILE", TMP_DIR / "signals.json"))
LOG_FILE = Path(os.environ.get("NEXUS_LOG_FILE", TMP_DIR / "nexus_app.log"))
DEBUG_WS_TOKEN = os.environ.get("DEBUG_WS_TOKEN", "d33144d6cb84fe05bf38bb9f22591683")
ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "*")
BACKEND_BASE_URL = os.environ.get("BACKEND_BASE_URL", "https://nexus-mobile-ai.onrender.com")

# ---------- Logging ----------
logger = logging.getLogger("nexus")
logger.setLevel(logging.INFO)
fmt = logging.Formatter("[%(asctime)s] %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S")
sh = logging.StreamHandler()
sh.setFormatter(fmt)
logger.addHandler(sh)
try:
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)
except Exception:
    logger.exception("Could not open logfile; continuing with stdout only")

# ---------- App & CORS ----------
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

# ---------- State ----------
frames_received = 0

# ---------- Models ----------
class FramePayload(BaseModel):
    type: Optional[str] = "frame"
    pair: Optional[str] = None
    data: Optional[str] = None
    data_b64: Optional[str] = None
    mime: Optional[str] = "image/jpeg"
    method: Optional[str] = None
    client_ts: Optional[int] = None

class SignalPayload(BaseModel):
    type: str
    rid: str
    pair: str
    timeframe: str
    open_ts: int
    sent_at: int
    action: str
    confidence: float
    reason: str
    expires_at: Optional[int] = None
    preview_image: Optional[str] = None
    audio_url: Optional[str] = None
    note: Optional[str] = None

# ---------- WS connection manager ----------
class ConnectionManager:
    def __init__(self):
        self.active_ws: Set[WebSocket] = set()
        self._mjpeg_queues: Set[asyncio.Queue] = set()
        self._mq_max = 4

    async def connect(self, websocket: WebSocket, token: Optional[str] = None):
        if DEBUG_WS_TOKEN and token != DEBUG_WS_TOKEN:
            await websocket.close(code=1008)
            logger.info("WS connection rejected: invalid token")
            return False
        await websocket.accept()
        self.active_ws.add(websocket)
        logger.info(f"WS CONNECT - clients={len(self.active_ws)}")
        return True

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_ws:
            self.active_ws.remove(websocket)
        logger.info(f"WS DISCONNECT - clients={len(self.active_ws)}")

    async def broadcast_text(self, message: str):
        to_remove = []
        for ws in list(self.active_ws):
            try:
                await ws.send_text(message)
            except Exception:
                logger.exception("WS send_text error")
                to_remove.append(ws)
        for ws in to_remove:
            self.disconnect(ws)

    async def broadcast_binary(self, data: bytes):
        to_remove = []
        for ws in list(self.active_ws):
            try:
                await ws.send_bytes(data)
            except Exception:
                logger.exception("WS send_bytes error")
                to_remove.append(ws)
        for ws in to_remove:
            self.disconnect(ws)

    def register_mjpeg(self) -> asyncio.Queue:
        q = asyncio.Queue(maxsize=self._mq_max)
        self._mjpeg_queues.add(q)
        logger.info(f"MJPEG registered (queues={len(self._mjpeg_queues)})")
        return q

    def unregister_mjpeg(self, q: asyncio.Queue):
        self._mjpeg_queues.discard(q)
        logger.info(f"MJPEG unregistered (queues={len(self._mjpeg_queues)})")

    def push_mjpeg(self, data: bytes):
        for q in list(self._mjpeg_queues):
            try:
                if q.full():
                    try:
                        _ = q.get_nowait()
                    except Exception:
                        pass
                q.put_nowait(data)
            except Exception:
                logger.exception("mjpeg push fail; unregistering queue")
                self._mjpeg_queues.discard(q)

manager = ConnectionManager()

# ---------- Helpers ----------
def save_json_signal(signal: Dict[str, Any]):
    arr = []
    if SIGNALS_FILE.exists():
        try:
            arr = json.loads(SIGNALS_FILE.read_text(encoding="utf-8") or "[]")
        except Exception:
            arr = []
    arr.append(signal)
    try:
        SIGNALS_FILE.write_text(json.dumps(arr, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        logger.exception("Failed saving signals file")

async def generate_tts_and_url(text: str, rid: str, lang: str = "pt-br") -> Optional[str]:
    try:
        fname = f"signal-{rid}.mp3"
        path = AUDIO_DIR / fname
        # gTTS language code: 'pt' or 'pt-br' often works as 'pt'
        tts = gTTS(text=text, lang="pt")
        tts.save(str(path))
        return f"{BACKEND_BASE_URL}/audio/{fname}"
    except Exception:
        logger.exception("TTS generation failed")
        return None

async def process_frame_and_build_payload(b64: str, pair: Optional[str], client_info: dict, method: Optional[str]=None, client_ts: Optional[int]=None):
    global frames_received
    rid = str(uuid.uuid4())
    client_host = client_info.get("client_host", "unknown")
    origin = client_info.get("origin", "")
    ua = client_info.get("ua", "")
    logger.info(f"FRAME_RECEIVE rid={rid} from={client_host} origin={origin} ua={ua} (b64_len={len(b64) if b64 else 0})")
    try:
        bdata = base64.b64decode(b64)
        logger.info(f"rid={rid} decoded raw_len={len(bdata)}")
    except Exception as e:
        logger.exception("base64 decode error")
        raise HTTPException(status_code=400, detail=f"Invalid base64: {e}")

    # save raw & verify via Pillow
    try:
        raw_name = f"AUTO-{datetime.utcnow().strftime('%Y%m%dT%H%M%S%f')}-rid{rid}.b64"
        raw_path = TMP_DIR / raw_name
        raw_path.write_bytes(bdata)
    except Exception:
        logger.exception("saving raw .b64 failed")

    pillow_ok = False
    pillow_err = None
    saved_image_name = None
    jpeg_bytes = None
    try:
        img = Image.open(io.BytesIO(bdata))
        img.verify()
        img = Image.open(io.BytesIO(bdata)).convert("RGB")
        pillow_ok = True
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=85)
        jpeg_bytes = out.getvalue()
        saved_image_name = f"AUTO-{datetime.utcnow().strftime('%Y%m%dT%H%M%S%f')}-rid{rid}.jpg"
        (TMP_DIR / saved_image_name).write_bytes(jpeg_bytes)
        logger.info(f"Saved JPEG {saved_image_name}")
    except UnidentifiedImageError as e:
        pillow_err = f"UnidentifiedImageError: {e}"
        logger.exception("Pillow UnidentifiedImageError")
    except Exception as e:
        pillow_err = str(e)
        logger.exception("Pillow error")

    frames_received += 1

    response_payload = {
        "received": True,
        "rid": rid,
        "pillow_ok": pillow_ok,
        "pillow_error": pillow_err,
        "saved": saved_image_name,
        "pair": pair or "AUTO",
        "method": method,
        "client_ts": client_ts
    }

    ws_payload = {
        "type": "frame",
        "rid": rid,
        "pair": pair or "AUTO",
        "saved": saved_image_name,
        "pillow_ok": pillow_ok,
        "data_b64": b64,
        "method": method,
        "client": {"host": client_host, "ua": ua, "origin": origin},
        "sent_at": int(datetime.now(tz=timezone.utc).timestamp())
    }

    return response_payload, ws_payload, jpeg_bytes

def next_m5_open_ts(now_ts: Optional[int] = None) -> int:
    from datetime import datetime, timedelta
    if now_ts is None:
        now = datetime.utcnow()
    else:
        now = datetime.fromtimestamp(now_ts, tz=timezone.utc)
    # round up to next multiple of 5 minutes with seconds=0
    minute = now.minute
    add = (5 - (minute % 5)) % 5
    if add == 0 and now.second == 0 and now.microsecond == 0:
        target = now
    else:
        # move to next multiple
        target = (now.replace(second=0, microsecond=0) + 
                  (timedelta(minutes=add) if add > 0 else timedelta(minutes=5)))
    return int(target.replace(tzinfo=timezone.utc).timestamp())

# ---------- Routes ----------
@app.get("/")
async def root():
    return RedirectResponse("/health")

@app.get("/health")
async def health():
    return JSONResponse({"status": "ok", "frames_received": frames_received})

@app.post("/echo")
async def echo(payload: dict = Body(...)):
    return JSONResponse({"received": payload})

# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: Optional[str] = Query(None)):
    ok = await manager.connect(websocket, token)
    if not ok:
        return
    last_meta: Optional[Dict[str, Any]] = None
    try:
        while True:
            # receive either text JSON or binary (ArrayBuffer)
            msg = await websocket.receive()
            if "text" in msg and msg["text"] is not None:
                text = msg["text"]
                logger.info(f"WS RX text len={len(text)}")
                # try parse JSON
                try:
                    obj = json.loads(text)
                except Exception:
                    # broadcast raw text
                    await manager.broadcast_text(text)
                    continue
                # if it's a frame metadata or generic message
                if obj.get("type") == "meta":
                    # store last_meta to pair with next binary
                    last_meta = obj
                    # also broadcast meta (so viewers/workers can use data_b64 fallback)
                    await manager.broadcast_text(json.dumps(obj))
                    continue
                if obj.get("type") == "frame":
                    # frame payload may include data_b64 in text
                    await manager.broadcast_text(json.dumps(obj))
                    continue
                if obj.get("type") == "command":
                    # rebroadcast commands to all viewers
                    await manager.broadcast_text(json.dumps(obj))
                    continue
                # otherwise broadcast generic json
                await manager.broadcast_text(json.dumps(obj))
            elif "bytes" in msg and msg["bytes"] is not None:
                data = msg["bytes"]
                logger.info(f"WS RX binary len={len(data)}")
                # Broadcast binary to viewers
                try:
                    await manager.broadcast_binary(data)
                    # if there is last_meta with pair and method, also broadcast a composed JSON frame (with base64 omitted to save) referencing that saved image
                    if last_meta:
                        # try to process locally: create base64 and frame entry (but to avoid heavy load, just broadcast metadata indicating binary arrived)
                        meta = {
                            "type": "frame_binary",
                            "meta": last_meta,
                            "rid_meta": last_meta.get("rid") if last_meta else None,
                            "sent_at": int(datetime.now(tz=timezone.utc).timestamp())
                        }
                        await manager.broadcast_text(json.dumps(meta))
                        last_meta = None
                except Exception:
                    logger.exception("broadcast binary failed")
            else:
                # unknown message structure
                logger.info("WS unknown message: %s", msg)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        logger.exception("WS handler exception")
        manager.disconnect(websocket)

# HTTP frame POST (compat)
@app.post("/frame")
async def receive_frame(request: Request, payload: FramePayload):
    b64 = payload.data or payload.data_b64 or ""
    client_info = {"client_host": request.client.host if request.client else "unknown", "origin": request.headers.get("origin",""), "ua": request.headers.get("user-agent","")}
    resp_payload, ws_payload, jpeg_bytes = await process_frame_and_build_payload(b64, payload.pair, client_info, method=payload.method, client_ts=payload.client_ts)
    # broadcast metadata + binary if available
    try:
        await manager.broadcast_text(json.dumps(ws_payload))
    except Exception:
        logger.exception("broadcast text error")
    if jpeg_bytes:
        try:
            await manager.broadcast_binary(jpeg_bytes)
        except Exception:
            logger.exception("broadcast binary error")
        manager.push_mjpeg(jpeg_bytes)
    return JSONResponse(resp_payload)

# MJPEG streaming
async def mjpeg_generator(q: asyncio.Queue):
    try:
        while True:
            try:
                jpeg = await asyncio.wait_for(q.get(), timeout=30.0)
            except asyncio.TimeoutError:
                # keepalive
                yield b"\r\n"
                continue
            if not jpeg:
                continue
            part = b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: " + str(len(jpeg)).encode() + b"\r\n\r\n"
            yield part
            yield jpeg
            yield b"\r\n"
    finally:
        pass

@app.get("/mjpeg")
async def mjpeg_stream(token: Optional[str] = Query(None)):
    if DEBUG_WS_TOKEN and token != DEBUG_WS_TOKEN:
        raise HTTPException(status_code=403, detail="Forbidden")
    q = manager.register_mjpeg()
    async def stream():
        try:
            async for chunk in mjpeg_generator(q):
                yield chunk
        finally:
            manager.unregister_mjpeg(q)
    return StreamingResponse(stream(), media_type="multipart/x-mixed-replace; boundary=frame")

# ---------- Signals endpoints ----------
@app.post("/signals")
async def post_signal(signal: SignalPayload, token: Optional[str] = Query(None)):
    # token-protect
    if DEBUG_WS_TOKEN and token != DEBUG_WS_TOKEN:
        raise HTTPException(status_code=403, detail="Forbidden")
    sig = signal.dict()
    # generate audio if not provided
    if not sig.get("audio_url"):
        text = f"{sig.get('action')} {sig.get('pair')} para abertura do candle {sig.get('timeframe')}. Confiança {sig.get('confidence'):.2f}. Motivo: {sig.get('reason')}"
        audio_url = await generate_tts_and_url(text, sig.get("rid"))
        sig["audio_url"] = audio_url
    # preview_image: if present and points to local saved file, convert to full URL
    if sig.get("preview_image") and not sig["preview_image"].startswith("http"):
        sig["preview_image"] = f"{BACKEND_BASE_URL}/debug/getfile?file={sig['preview_image']}&token={DEBUG_WS_TOKEN}"
    # save and broadcast
    save_json_signal(sig)
    try:
        await manager.broadcast_text(json.dumps({"type":"signal","signal":sig}, ensure_ascii=False))
    except Exception:
        logger.exception("broadcast signal failed")
    return JSONResponse({"ok": True, "signal": sig})

@app.get("/signals/latest")
async def signals_latest(pair: Optional[str] = Query(None), limit: int = Query(20, ge=1, le=200)):
    arr = []
    if SIGNALS_FILE.exists():
        try:
            arr = json.loads(SIGNALS_FILE.read_text(encoding="utf-8") or "[]")
        except Exception:
            arr = []
    if pair:
        arr = [s for s in arr if s.get("pair") == pair]
    return JSONResponse({"signals": arr[-limit:]})

@app.get("/signals/history")
async def signals_history(limit: int = Query(200, ge=1, le=2000)):
    arr = []
    if SIGNALS_FILE.exists():
        try:
            arr = json.loads(SIGNALS_FILE.read_text(encoding="utf-8") or "[]")
        except Exception:
            arr = []
    return JSONResponse({"signals": arr[-limit:]})

# serve audio files
@app.get("/audio/{file_name}")
async def get_audio(file_name: str):
    fpath = AUDIO_DIR / Path(file_name).name
    if not fpath.exists():
        raise HTTPException(status_code=404, detail="Audio not found")
    return FileResponse(path=str(fpath), filename=fpath.name, media_type="audio/mpeg")

# debug logs & files
@app.get("/debug/logs")
async def debug_logs(lines: int = Query(200, ge=1, le=2000), token: str = Query(...)):
    if DEBUG_WS_TOKEN and token != DEBUG_WS_TOKEN:
        raise HTTPException(status_code=403, detail="Forbidden")
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

@app.get("/debug/getfile")
async def debug_getfile(file: str = Query(...), token: str = Query(...)):
    if DEBUG_WS_TOKEN and token != DEBUG_WS_TOKEN:
        raise HTTPException(status_code=403, detail="Forbidden")
    file_path = TMP_DIR / Path(file).name
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path=str(file_path), filename=file_path.name, media_type="application/octet-stream")

# ---------- Run ----------
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
