# backend/main.py
import datetime
import json
import base64
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.websockets import WebSocketState
from pathlib import Path

# =========================
# CONFIGURAÇÃO GERAL
# =========================
app = FastAPI(title="Nexus Mobile AI - Backend")
HISTORY = []  # cada entrada: {timestamp, pair, confidence, result}
SIGNAL_THRESHOLD = 0.8  # mínimo de confiança para sinal
STATIC_DIR = Path(__file__).parent / "static"

# Servir arquivos estáticos (viewer.html, CSS, etc)
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# =========================
# ROTAS HTTP
# =========================
@app.get("/")
async def root():
    """Rota principal - página de visualização"""
    viewer_path = STATIC_DIR / "viewer.html"
    if viewer_path.exists():
        return HTMLResponse(viewer_path.read_text())
    return JSONResponse({"status": "ok", "message": "Nexus Mobile AI backend ativo."})

@app.get("/health")
async def health():
    return {"status": "ok", "message": "Servidor operacional."}

@app.get("/history")
async def get_history():
    return JSONResponse(HISTORY)

# =========================
# WEBSOCKET STREAM RECEIVER
# =========================
@app.websocket("/ws/stream")
async def ws_stream(ws: WebSocket):
    await ws.accept()
    print("[NEXUS STREAM] Cliente conectado ao WebSocket.")

    try:
        while True:
            data = await ws.receive_text()
            payload = json.loads(data)

            # Caso seja uma imagem (frame) enviada em base64
            if payload.get("type") == "frame":
                image_data = base64.b64decode(payload["data"].split(",")[1])
                conf = fake_confidence(len(image_data))
                pair = payload.get("pair", "HOME/TEST")

                if conf >= SIGNAL_THRESHOLD:
                    rec = {
                        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                        "pair": pair,
                        "confidence": conf,
                        "result": "PENDING"
                    }
                    HISTORY.append(rec)
                    await send_signal(ws, rec)

                await ws.send_text(json.dumps({
                    "type": "ack",
                    "msg": f"Frame recebido ({len(image_data)} bytes)",
                    "confidence": conf
                }))

            # Caso sejam dados de DOM (preço, volume etc)
            elif payload.get("type") == "data":
                HISTORY.append({
                    "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                    "pair": payload.get("pair", "HOME/TEST"),
                    "data": payload.get("data")
                })
                await ws.send_text(json.dumps({"type": "ack", "msg": "Dados DOM recebidos"}))

    except WebSocketDisconnect:
        print("[NEXUS STREAM] Cliente desconectado.")


async def send_signal(ws: WebSocket, rec: dict):
    """Envia sinal para o frontend quando há alta confiança."""
    if ws.application_state == WebSocketState.CONNECTED:
        await ws.send_text(json.dumps({
            "type": "signal",
            "pair": rec["pair"],
            "confidence": rec["confidence"],
            "timestamp": rec["timestamp"]
        }))

# =========================
# FUNÇÕES AUXILIARES
# =========================
def fake_confidence(size: int) -> float:
    """Simula confiança com base no tamanho dos dados recebidos."""
    if size > 200000:
        return 0.92
    elif size > 80000:
        return 0.85
    elif size > 30000:
        return 0.75
    else:
        return 0.55


# =========================
# EXECUÇÃO LOCAL (Termux)
# =========================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
