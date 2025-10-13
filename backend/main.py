# backend/main.py
import datetime, json, os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.websockets import WebSocketState

app = FastAPI()
HISTORY = []  # Histórico de sinais
SIGNAL_THRESHOLD = 0.8  # 80% de confiança mínima

# === ROTAS PRINCIPAIS ===
@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/history")
async def get_history():
    return JSONResponse(HISTORY)

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            data = await ws.receive_bytes()
            conf = fake_confidence(len(data))
            if conf >= SIGNAL_THRESHOLD:
                rec = {
                    "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                    "pair": "HOME/TEST",
                    "confidence": conf,
                    "result": "PENDING"
                }
                HISTORY.append(rec)
                if ws.application_state == WebSocketState.CONNECTED:
                    await ws.send_text(json.dumps({
                        "type": "signal",
                        "pair": rec["pair"],
                        "confidence": conf,
                        "timestamp": rec["timestamp"]
                    }))
            await ws.send_text(json.dumps({
                "type": "ack",
                "size": len(data),
                "confidence": conf
            }))
    except WebSocketDisconnect:
        print("Cliente desconectado")

def fake_confidence(nbytes: int) -> float:
    """Estimativa de confiança falsa (placeholder para IA real)."""
    if nbytes > 200000: return 0.9
    if nbytes > 50000: return 0.83
    if nbytes > 10000: return 0.7
    return 0.4

# === FRONTEND STATIC ===
frontend_path = os.path.join(os.path.dirname(__file__), "../frontend")
app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000)
