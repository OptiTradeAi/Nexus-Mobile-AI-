# backend/main.py
import base64
import io
import os
import traceback
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Pillow (assumimos instalado no container)
from PIL import Image

app = FastAPI(title="Nexus Mobile AI Backend (debug-pillow)")

# CORS para testes
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATE = {"pairs_seen": set(), "frames_received": 0, "signals": 0}

class FramePayload(BaseModel):
    type: str
    pair: Optional[str] = None
    data: Optional[str] = None  # base64 image data (sem prefixo data:)

def log(msg: str):
    ts = datetime.utcnow().isoformat()
    print(f"[{ts}] {msg}", flush=True)

@app.on_event("startup")
async def startup_event():
    log("Application startup")

@app.on_event("shutdown")
async def shutdown_event():
    log("Application shutdown")

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
    receive_time = datetime.utcnow().isoformat()
    client = getattr(req.client, "host", "unknown")
    log(f"Incoming /frame request from {client}")

    if payload.type != "frame":
        log("Invalid frame type")
        raise HTTPException(status_code=400, detail="type must be 'frame'")

    if not payload.data:
        log("No data in frame payload")
        raise HTTPException(status_code=400, detail="no image data provided")

    # bookkeeping
    STATE["frames_received"] += 1
    if payload.pair:
        STATE["pairs_seen"].add(payload.pair)

    # decode base64
    try:
        b64_len = len(payload.data)
        decoded = base64.b64decode(payload.data)
        raw_len = len(decoded)
        log(f"RECEIVED FRAME pair={payload.pair or 'unknown'} b64_len={b64_len} raw_len={raw_len}")
    except Exception as e:
        tb = traceback.format_exc()
        log(f"Base64 decode error: {e}\n{tb}")
        raise HTTPException(status_code=400, detail=f"invalid base64 data: {e}")

    pillow_ok = False
    pillow_error = None
    pillow_trace = None

    try:
        img = Image.open(io.BytesIO(decoded))
        # chama verify() para verificar integridade
        img.verify()
        pillow_ok = True
        log("Pillow verification OK")
    except Exception as e:
        pillow_ok = False
        pillow_error = str(e)
        pillow_trace = traceback.format_exc()
        # log completo no servidor
        log(f"Pillow verification failed: {pillow_error}\n{pillow_trace}")

    # tentativa de salvar (se possível)
    saved_path = None
    try:
        os.makedirs("/tmp/nexus_frames", exist_ok=True)
        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S%f")[:-3]
        basefn = f"/tmp/nexus_frames/{(payload.pair or 'unknown')}-{ts}"
        if pillow_ok:
            # reabrir e salvar em JPEG para depuração
            try:
                img2 = Image.open(io.BytesIO(decoded)).convert("RGB")
                img2.thumbnail((1200, 1200))
                filename = basefn + ".jpg"
                img2.save(filename, "JPEG", quality=75)
                saved_path = filename
                log(f"Saved frame to {filename}")
            except Exception as se:
                sp_tb = traceback.format_exc()
                log(f"Could not save image via Pillow: {se}\n{sp_tb}")
        else:
            # salva um cabeçalho parcial para debug
            try:
                filename = basefn + ".b64hdr"
                with open(filename, "wb") as f:
                    f.write(decoded[:1024])
                saved_path = filename
                log(f"Saved debug partial to {filename}")
            except Exception as se:
                sp_tb = traceback.format_exc()
                log(f"Could not save debug partial: {se}\n{sp_tb}")
    except Exception as e:
        sp_tb = traceback.format_exc()
        log(f"Error creating /tmp dir or saving: {e}\n{sp_tb}")

    response = {
        "status": "ok",
        "received": True,
        "pair": payload.pair,
        "b64_len": b64_len,
        "raw_len": raw_len,
        "pillow_ok": pillow_ok,
        "pillow_error": pillow_error,
        "pillow_trace": (pillow_trace[:1500] if pillow_trace else None),  # corta trace longa para JSON
        "saved_path": saved_path,
        "received_at": receive_time,
        "signal": None,
    }
    return response

@app.post("/echo")
async def echo(req: Request):
    body = await req.json()
    log(f"/echo called, body keys: {list(body.keys()) if isinstance(body, dict) else 'non-dict'}")
    return {"received": body}
