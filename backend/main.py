# backend/main.py
import base64
import io
import os
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from PIL import Image  # Pillow instalado no container Docker

app = FastAPI(title="Nexus Mobile AI Backend (logging)")

# CORS - durante testes usamos "*" para facilitar. Troque para domínios específicos em produção.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Estado simples em memória (apenas para /health)
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
    client = None
    try:
        client = req.client.host
    except Exception:
        client = "unknown"
    log(f"Incoming /frame request from {client}")

    if payload.type != "frame":
        log("Invalid frame type")
        raise HTTPException(status_code=400, detail="type must be 'frame'")

    if not payload.data:
        log("No data in frame payload")
        raise HTTPException(status_code=400, detail="no image data provided")

    # Bookkeeping
    STATE["frames_received"] += 1
    if payload.pair:
        STATE["pairs_seen"].add(payload.pair)

    # Decode and measure
    try:
        b64_len = len(payload.data)
        decoded = base64.b64decode(payload.data)
        raw_len = len(decoded)
        log(f"RECEIVED FRAME pair={payload.pair or 'unknown'} b64_len={b64_len} raw_len={raw_len}")
    except Exception as e:
        log(f"Error decoding base64: {e}")
        raise HTTPException(status_code=400, detail=f"invalid base64 data: {e}")

    # Validate with Pillow
    pillow_ok = False
    try:
        img = Image.open(io.BytesIO(decoded))
        img.verify()
        pillow_ok = True
        log("Pillow verification OK")
    except Exception as e:
        log(f"Pillow verification failed: {e}")
        # continuamos (não falha o endpoint), mas marcamos pillow_ok=False

    # Optional: salvar uma cópia para debug em /tmp/nexus_frames
    try:
        os.makedirs("/tmp/nexus_frames", exist_ok=True)
        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S%f")[:-3]
        filename = f"/tmp/nexus_frames/{(payload.pair or 'unknown')}-{ts}.jpg"
        if pillow_ok:
            img2 = Image.open(io.BytesIO(decoded)).convert("RGB")
            img2.thumbnail((1200, 1200))
            img2.save(filename, "JPEG", quality=75)
            log(f"Saved frame to {filename}")
        else:
            # salva um pedaço do blob para debug
            with open(filename + ".b64hdr", "wb") as f:
                f.write(decoded[:1024])
            log(f"Saved debug partial to {filename}.b64hdr")
    except Exception as e:
        log(f"Could not save frame: {e}")

    # Aqui você colocaria sua lógica de inferência / heurística. Ex.: stub que devolve null.
    response = {
        "status": "ok",
        "received": True,
        "pair": payload.pair,
        "b64_len": b64_len,
        "raw_len": raw_len,
        "pillow_ok": pillow_ok,
        "received_at": receive_time,
        "signal": None,
    }
    return response

@app.post("/echo")
async def echo(req: Request):
    body = await req.json()
    log(f"/echo called, body keys: {list(body.keys()) if isinstance(body, dict) else 'non-dict'}")
    return {"received": body}
