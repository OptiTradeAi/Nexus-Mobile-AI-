import os
import sys
import json
import base64
import logging
import asyncio
from pathlib import Path
from datetime import datetime
import pytz

from fastapi import FastAPI, WebSocket, Query, Body
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("startup")

log.info("=== Nexus Mobile AI Startup Debug Info ===")
log.info(f"CWD: {os.getcwd()}")
log.info(f"PYTHONPATH (first 10): {sys.path[:10]}")

backend_path = Path(__file__).parent.resolve()
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))
    log.info(f"Added to sys.path: {backend_path}")

try:
    from backend.ai_engine_fusion import analyze_frame_with_meta, register_entry
    from backend.ws_router import router as ws_router
    log.info("✅ Import backend.ai_engine_fusion and ws_router OK")
except Exception as e:
    log.error("❌ Import failed", exc_info=True)
    raise

app = FastAPI(title="Nexus Mobile AI Stream Server")
TZ = pytz.timezone("America/Sao_Paulo")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = os.path.join(backend_path, "static")
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Include WebSocket router
app.include_router(ws_router)

@app.get("/")
async def root():
    return {
        "status": "Nexus Mobile AI ativo",
        "viewer_url": "/static/viewer.html",
        "stream_ws": "/ws/stream",
        "viewer_ws": "/ws/viewer"
    }

@app.get("/health")
async def health():
    return {"status": "ok", "time": datetime.now(TZ).isoformat()}

@app.post("/agent/frame")
async def receive_frame(data: dict = Body(...)):
    """
    Endpoint para receber frames do Selenium Agent via POST
    """
    try:
        pair = data.get("pair")
        frame_b64 = data.get("frame")
        if not pair or not frame_b64:
            return {"ok": False, "error": "pair or frame missing"}

        # Salvar frame para debug
        frame_path = os.path.join(STATIC_DIR, f"latest_{pair.replace('/', '_')}.webp")
        with open(frame_path, "wb") as f:
            f.write(base64.b64decode(frame_b64))

        # Analisar frame
        analysis = analyze_frame_with_meta({"pair": pair, "data": frame_b64, "timestamp": datetime.now(TZ).isoformat()})

        return {"ok": True, "analysis": analysis}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.post("/agent/heartbeat")
async def agent_heartbeat(data: dict = Body(...)):
    """
    Endpoint para receber heartbeat do Selenium Agent
    """
    # Aqui você pode atualizar status do agente, logs, etc.
    return {"ok": True, "message": "heartbeat recebido"}
