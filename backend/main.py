# backend/main.py
import base64
import io
import os
import traceback
import uuid
from collections import deque
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware

import logging
from logging.handlers import RotatingFileHandler

# Pillow (assumimos instalado no container)
from PIL import Image

# --------------- Logging config ---------------
LOG_PATH = "/tmp/nexus.log"
os.makedirs("/tmp", exist_ok=True)

logger = logging.getLogger("nexus")
logger.setLevel(logging.INFO)

# stdout handler (so Render/containers still show logs)
sh = logging.StreamHandler()
sh.setLevel(logging.INFO)
sh.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s %(message)s"))

# rotating file handler
fh = RotatingFileHandler(LOG_PATH, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8")
fh.setLevel(logging.DEBUG)
fh.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s %(message)s"))

# attach handlers if not already attached (idempotent for hot reloads)
if not logger.handlers:
    logger.addHandler(sh)
    logger.addHandler(fh)

# --------------- App & CORS ---------------
app = FastAPI(title="Nexus Mobile AI Backend (debug-logging)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # restrinja em produção
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middleware para gerar request-id e log básico de request/response
class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        rid = str(uuid.uuid4())
        request.state.rid = rid
        logger.info(f"REQ_START rid={rid} method={request.method} path={request.url.path} full_url={request.url}")
        resp = await call_next(request)
        resp.headers["X-Request-ID"] = rid
        logger.info(f"REQ_END   rid={rid} status={resp.status_code}")
        return resp

app.add_middleware(RequestIDMiddleware)

# --------------- State / Models ---------------
STATE = {"pairs_seen": set(), "frames_received": 0, "signals": 0}

class FramePayload(BaseModel):
    type: str
    pair: Optional[str] = None
    data: Optional[str] = None  # base64 image data (sem prefixo data:)

# --------------- Helpers ---------------
def log_exc(prefix=""):
    tb = traceback.format_exc()
    logger.error(f"{prefix}\n{tb}")
    return tb

def tail_file(path: str, lines: int = 200) -> str:
    # lê as últimas N linhas do arquivo de forma eficiente
    try:
        dq = deque(maxlen=lines)
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                dq.append(line.rstrip("\n"))
        return "\n".join(dq)
    except Exception as e:
        logger.error(f"tail_file error: {e}")
        return f"Could not read log file: {e}"

# --------------- Endpoints ---------------
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "pairs_known": list(STATE["pairs_seen"]),
        "frames_received": STATE["frames_received"],
        "signals": STATE["signals"],
    }

@app.post("/frame")
async def receive_frame(payload: FramePayload, req: Request):
    rid = getattr(req.state, "rid", "no-rid")
    receive_time = datetime.utcnow().isoformat()
    client = getattr(req.client, "host", "unknown")

    # Log request summary + some headers
    origin = req.headers.get("origin")
    ua = req.headers.get("user-agent")
    cl = req.headers.get("content-length")
    logger.info(f"FRAME_RECEIVE rid={rid} from={client} origin={origin} ua={ua} content-length={cl}")

    if payload.type != "frame":
        logger.warning(f"rid={rid} invalid type: {payload.type}")
        raise HTTPException(status_code=400, detail="type must be 'frame'")

    if not payload.data:
        logger.warning(f"rid={rid} no data in payload")
        raise HTTPException(status_code=400, detail="no image data provided")

    # bookkeeping
    STATE["frames_received"] += 1
    if payload.pair:
        STATE["pairs_seen"].add(payload.pair)

    # decode base64
    pillow_ok = False
    pillow_error = None
    pillow_trace = None
    b64_len = len(payload.data) if payload.data else 0
    raw_len = 0
    saved_path = None

    try:
        decoded = base64.b64decode(payload.data)
        raw_len = len(decoded)
        logger.info(f"rid={rid} decoded lengths b64_len={b64_len} raw_len={raw_len}")
    except Exception as e:
        pillow_error = f"base64 decode error: {e}"
        pillow_trace = traceback.format_exc()
        logger.error(f"rid={rid} {pillow_error}\n{pillow_trace}")
        raise HTTPException(status_code=400, detail=pillow_error)

    # Try to validate image with Pillow
    try:
        img = Image.open(io.BytesIO(decoded))
        img.verify()
        pillow_ok = True
        logger.info(f"rid={rid} Pillow verification OK")
    except Exception as e:
        pillow_ok = False
        pillow_error = str(e)
        pillow_trace = traceback.format_exc()
        logger.error(f"rid={rid} Pillow verification failed: {pillow_error}\n{pillow_trace}")

    # Save for debugging: full base64 if failure, or jpeg if ok
    try:
        os.makedirs("/tmp/nexus_frames", exist_ok=True)
        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S%f")[:-3]
        basefn = f"/tmp/nexus_frames/{(payload.pair or 'unknown')}-{ts}-rid{rid}"
        if pillow_ok:
            try:
                img2 = Image.open(io.BytesIO(decoded)).convert("RGB")
                img2.thumbnail((1600, 1600))
                filename = basefn + ".jpg"
                img2.save(filename, "JPEG", quality=85)
                saved_path = filename
                logger.info(f"rid={rid} Saved JPEG to {filename}")
            except Exception:
                logger.error(f"rid={rid} failed saving JPEG")
                log_exc()
        else:
            # save full base64 for later inspection (may be large)
            try:
                filename = basefn + ".b64"
                with open(filename, "wb") as f:
                    f.write(decoded)
                saved_path = filename
                logger.info(f"rid={rid} Saved raw blob to {filename}")
            except Exception:
                logger.error(f"rid={rid} failed saving raw blob")
                log_exc()
    except Exception:
        logger.error(f"rid={rid} error creating debug save")
        log_exc()

    response = {
        "status": "ok",
        "received": True,
        "pair": payload.pair,
        "b64_len": b64_len,
        "raw_len": raw_len,
        "pillow_ok": pillow_ok,
        "pillow_error": pillow_error,
        "pillow_trace": (pillow_trace[:2000] if pillow_trace else None),
        "saved_path": saved_path,
        "received_at": receive_time,
        "rid": rid,
        "signal": None,
    }
    return response

@app.post("/echo")
async def echo(req: Request):
    body = await req.json()
    rid = getattr(req.state, "rid", "no-rid")
    logger.info(f"rid={rid} /echo called keys={list(body.keys()) if isinstance(body, dict) else 'non-dict'}")
    return {"received": body}

# --------------- Debug-only endpoint to tail logs ---------------
# Protect with token set in env: DEBUG_LOG_TOKEN
@app.get("/debug/logs")
async def debug_logs(lines: int = 200, token: Optional[str] = None, req: Request = None):
    expected = os.environ.get("DEBUG_LOG_TOKEN")
    rid = getattr(req.state, "rid", "no-rid")
    if not expected:
        logger.warning(f"rid={rid} /debug/logs attempted but no DEBUG_LOG_TOKEN set")
        raise HTTPException(status_code=403, detail="debug logs not enabled")
    if token != expected:
        logger.warning(f"rid={rid} /debug/logs bad token")
        raise HTTPException(status_code=401, detail="invalid token")
    content = tail_file(LOG_PATH, lines)
    return Response(content, media_type="text/plain")
