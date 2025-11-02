# backend/main.py
import base64
import io
import os
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Pillow import (assumimos que estará disponível no ambiente Docker)
from PIL import Image

app = FastAPI(title="Nexus Mobile AI Backend")

# CORS - durante testes usamos "*" para facilitar. Depois restrinja aos domínios necessários.
# Em produção, substitua ["*"] por uma lista de domínios permitidos, ex:
# ["https://www.homebroker.com"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Estado simples em memória (apenas para /health)
STATE = {"pairs": 0, "candles": 0, "signals": 0}

class FramePayload(BaseModel):
    type: str
    pair: Optional[str] = None
    data: Optional[str] = None  # base64 image data (sem prefixo data:)

@app.get("/health")
async def health():
    return {"status": "ok", "pairs": STATE["pairs"], "candles": STATE["candles"], "signals": STATE["signals"]}

@app.post("/frame")
async def receive_frame(payload: FramePayload):
    """
    Recebe JSON com:
    {
      "type": "frame",
      "pair": "EURUSD-OTC",
      "data": "<base64 image data>"
    }
    Responde com JSON opcional contendo sinal.
    """
    if payload.type != "frame":
        raise HTTPException(status_code=400, detail="type must be 'frame'")

    if not payload.data:
        raise HTTPException(status_code=400, detail="no image data provided")

    # Decode base64
    try:
        decoded = base64.b64decode(payload.data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"invalid base64 data: {e}")

    # Validate image with Pillow
    try:
        img = Image.open(io.BytesIO(decoded))
        img.verify()  # verificacao basica
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"invalid image data: {e}")

    # Opcional: salvar uma cópia para depuração (pasta /tmp no container)
    try:
        os.makedirs("/tmp/nexus_frames", exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S%f")[:-3]
        filename = f"/tmp/nexus_frames/{(payload.pair or 'unknown')}-{timestamp}.jpg"
        # Re-abre e salva (verify() fecha o arquivo)
        img2 = Image.open(io.BytesIO(decoded)).convert("RGB")
        img2.thumbnail((1200, 1200))
        img2.save(filename, "JPEG", quality=75)
    except Exception:
        # não falha se não conseguir salvar
        pass

    # Aqui entra a sua lógica de inferência (modelo / análise). Por enquanto devolvemos resposta de debug.
    response = {"status": "ok", "received": True, "signal": None}
    return response

# Endpoint simples para debug
@app.post("/echo")
async def echo(req: Request):
    body = await req.json()
    return {"received": body}
