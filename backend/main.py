# backend/main.py
import base64
import io
import os
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from PIL import Image

app = FastAPI(title="Nexus Mobile AI Backend")

# CORS - durante testes usamos "*" para facilitar. Depois restrinja aos domínios necessários.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ❗ para produção, substitua por: ["https://www.homebroker.com"]
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

    # Try to open with Pillow to validate and optionally save a copy for debug
    try:
        img = Image.open(io.BytesIO(decoded))
        img.verify()  # verifica integridade básica
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"invalid image data: {e}")

    # Opcional: salvar uma cópia para depuração (limitado em produção)
    try:
        os.makedirs("/tmp/nexus_frames", exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S%f")[:-3]
        filename = f"/tmp/nexus_frames/{(payload.pair or 'unknown')}-{timestamp}.jpg"
        # Re-abre para salvar (verify() deixa a imagem fechada)
        img2 = Image.open(io.BytesIO(decoded)).convert("RGB")
        img2.thumbnail((1200, 1200))
        img2.save(filename, "JPEG", quality=75)
    except Exception:
        # Não falha o endpoint se não puder salvar
        pass

    # Aqui você chamaria sua lógica de inferência / análise
    # Para debug, retornamos um sinal vazio
    response = {"status": "ok", "received": True, "signal": None}
    return response

# Endpoint simples para receber e retornar um teste (útil para debug via fetch)
@app.post("/echo")
async def echo(req: Request):
    body = await req.json()
    return {"received": body}
