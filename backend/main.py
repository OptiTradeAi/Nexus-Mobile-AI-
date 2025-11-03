# main.py
import os
import io
import uuid
import base64
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request, HTTPException, Body, Query
from fastapi.responses import JSONResponse, RedirectResponse, FileResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from PIL import Image, UnidentifiedImageError

# Config
TMP_DIR = Path(os.environ.get("NEXUS_FRAMES_DIR", "/tmp/nexus_frames"))
TMP_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = Path(os.environ.get("NEXUS_LOG_FILE", "nexus_app.log"))
DEBUG_LOG_TOKEN = os.environ.get("DEBUG_LOG_TOKEN", "")
ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "*")  # "*" ou lista separada por vírgula

# Setup logging (stdout + file)
logger = logging.getLogger("nexus")
logger.setLevel(logging.INFO)
formatter = logging.Formatter("[%(asctime)s] %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S")

# stdout handler
ch = logging.StreamHandler()
ch.setFormatter(formatter)
logger.addHandler(ch)

# file handler
fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
fh.setFormatter(formatter)
logger.addHandler(fh)

app = FastAPI(title="Nexus Mobile AI Backend")

# CORS
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

# Simple in-memory counter
frames_received = 0

# Pydantic model for incoming frame
class FramePayload(BaseModel):
    type: Optional[str] = "frame"
    pair: Optional[str] = None
    data: str
    mime: Optional[str] = "image/jpeg"


# Root redirect to /health
@app.get("/")
async def root():
    """Redireciona / para /health para evitar 404 ao abrir o domínio."""
    return RedirectResponse("/health")


@app.get("/health")
async def health():
    """Health endpoint com contagem simples de frames recebidos."""
    return JSONResponse({"status": "ok", "frames_received": frames_received})


@app.post("/echo")
async def echo(payload: dict = Body(...)):
    """Echo simples para testar conectividade do navegador -> backend."""
    return JSONResponse({"received": payload})


@app.post("/frame")
async def receive_frame(request: Request, payload: FramePayload):
    """
    Recebe um frame em base64 (payload.data), verifica com Pillow, salva JPEG/PNG e retorna um RID.
    Logs incluem: FRAME_RECEIVE, Pillow verification OK/ERROR, Saved <file>.
    """
    global frames_received
    rid = str(uuid.uuid4())
    client_host = request.client.host if request.client else "unknown"
    origin = request.headers.get("origin", "")
    ua = request.headers.get("user-agent", "")
    content_length = request.headers.get("content-length", "unknown")

    logger.info(f"FRAME_RECEIVE rid={rid} from={client_host} origin={origin} ua={ua} content-length={content_length}")

    # Decode base64
    try:
        b64 = payload.data
        bdata = base64.b64decode(b64)
        logger.info(f"rid={rid} decoded lengths b64_len={len(b64)} raw_len={len(bdata)}")
    except Exception as e:
        logger.exception(f"rid={rid} base64 decode error")
        raise HTTPException(status_code=400, detail=f"Invalid base64 data: {e}")

    # Save raw .b64 for debugging (optional)
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

    # Verify with Pillow
    try:
        img = Image.open(io.BytesIO(bdata))
        # Force load to validate
        img.verify()  # verify might make the file unusable, so reopen to save
        # Re-open to save properly (Pillow pattern)
        img = Image.open(io.BytesIO(bdata)).convert("RGB")
        pillow_ok = True
        logger.info(f"rid={rid} Pillow verification OK")
    except UnidentifiedImageError as e:
        pillow_error = f"UnidentifiedImageError: {e}"
        logger.exception(f"rid={rid} Pillow UnidentifiedImageError")
    except Exception as e:
        pillow_error = f"Error: {e}"
        logger.exception(f"rid={rid} Pillow error")

    # Save image to disk if pillow_ok
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

    return JSONResponse(response_payload)


@app.get("/debug/logs")
async def debug_logs(lines: int = Query(200, ge=1, le=2000), token: str = Query(...)):
    """
    Retorna as últimas N linhas do arquivo de log.
    Protegido por token (DEBUG_LOG_TOKEN).
    """
    if not DEBUG_LOG_TOKEN or token != DEBUG_LOG_TOKEN:
        raise HTTPException(status_code=403, detail="Forbidden")

    try:
        if not LOG_FILE.exists():
            return PlainTextResponse("", status_code=200)

        # Read last N lines efficiently
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
    """
    Retorna arquivo salvo em /tmp/nexus_frames (ou NEXUS_FRAMES_DIR).
    Protegido por token.
    Use exatamente o nome do arquivo que aparece nos logs.
    """
    if not DEBUG_LOG_TOKEN or token != DEBUG_LOG_TOKEN:
        raise HTTPException(status_code=403, detail="Forbidden")

    # Normalize path to avoid directory traversal
    file_path = TMP_DIR / Path(file).name
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    # Return as file response
    return FileResponse(path=str(file_path), filename=file_path.name, media_type="application/octet-stream")


if __name__ == "__main__":
    import uvicorn
    # Port in Render is usually 10000? Use env PORT if provided
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
