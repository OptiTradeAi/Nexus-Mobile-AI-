# backend/main_updated.py
# FastAPI + WebSocket + Stream Handler para Nexus Stream

import datetime
import json
import base64
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.websockets import WebSocketState

app = FastAPI(title="Nexus Stream AI")

# CORS liberado para acesso externo (ex: extensão Tampermonkey)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Memória temporária
STREAM_CACHE = []
DATA_CACHE = []
SIGNAL_HISTORY = []

# Configurações de thresholds e ajustes
CONFIDENCE_THRESHOLD = 0.8
MAX_CACHE_SIZE = 100  # máximo de frames armazenados


@app.get("/")
async def root():
    """Página inicial básica"""
    return HTMLResponse(
        "<h2>Nexus Stream AI Backend ativo ✅</h2><p>Use /viewer para visualizar o stream.</p>"
    )


@app.get("/health")
async def health():
    return {"status": "ok", "active_streams": len(STREAM_CACHE)}


@app.get("/history")
async def history():
    return JSONResponse(SIGNAL_HISTORY)


@app.get("/viewer")
async def viewer_page():
    """Carrega o visualizador HTML"""
    html_path = "backend/static/viewer.html"
    try:
        with open(html_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content, status_code=200)
    except FileNotFoundError:
        return HTMLResponse(
            "<h3>viewer.html não encontrado em /backend/static/</h3>", status_code=404
        )


@app.websocket("/ws/stream")
async def websocket_stream(ws: WebSocket):
    """Recebe stream de vídeo e dados da corretora"""
    await ws.accept()
    print("🟢 Nova conexão recebida no WebSocket /ws/stream")
    try:
        while True:
            data = await ws.receive_text()
            payload = json.loads(data)

            # Identifica o tipo de dado
            if payload.get("type") == "frame":
                frame_data = payload.get("data")
                timestamp = datetime.datetime.utcnow().isoformat() + "Z"

                STREAM_CACHE.append({"timestamp": timestamp, "frame": frame_data})
                if len(STREAM_CACHE) > MAX_CACHE_SIZE:
                    STREAM_CACHE.pop(0)

            elif payload.get("type") == "dom":
                DATA_CACHE.append(payload)
                if len(DATA_CACHE) > MAX_CACHE_SIZE:
                    DATA_CACHE.pop(0)

            elif payload.get("type") == "signal":
                SIGNAL_HISTORY.append(payload)

            # Envia ACK para confirmar recebimento
            await ws.send_text(json.dumps({"status": "received"}))

    except WebSocketDisconnect:
        print("🔴 Cliente desconectado de /ws/stream")


@app.get("/api/stream/latest")
async def get_latest_frame():
    """Retorna o último frame recebido"""
    if not STREAM_CACHE:
        return JSONResponse({"error": "Nenhum frame recebido ainda."})
    return JSONResponse(STREAM_CACHE[-1])


@app.get("/api/data/latest")
async def get_latest_data():
    """Retorna o último pacote de dados DOM recebido"""
    if not DATA_CACHE:
        return JSONResponse({"error": "Nenhum dado recebido ainda."})
    return JSONResponse(DATA_CACHE[-1])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main_updated:app", host="0.0.0.0", port=8000, reload=True)
