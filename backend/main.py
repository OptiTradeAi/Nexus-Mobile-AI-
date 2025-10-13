# backend/main.py
import datetime, json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

HISTORY = []
CLIENTS = set()
SIGNAL_THRESHOLD = 0.8

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/history")
async def get_history():
    return JSONResponse(HISTORY)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    CLIENTS.add(websocket)
    print("📡 Novo cliente conectado")

    try:
        while True:
            data = await websocket.receive_text()
            candle = json.loads(data)
            conf = fake_confidence(candle)

            record = {
                "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                "pair": candle.get("symbol", "HOME/OTC"),
                "confidence": conf,
                "result": "PENDING",
                "open": candle.get("open"),
                "close": candle.get("close"),
                "high": candle.get("high"),
                "low": candle.get("low"),
            }
            HISTORY.append(record)

            if conf >= SIGNAL_THRESHOLD:
                await broadcast({"type": "signal", "data": record})

            await broadcast({"type": "candle", "data": record})

    except WebSocketDisconnect:
        CLIENTS.remove(websocket)
        print("❌ Cliente desconectado")

async def broadcast(message: dict):
    to_remove = set()
    for client in CLIENTS:
        try:
            await client.send_text(json.dumps(message))
        except:
            to_remove.add(client)
    for c in to_remove:
        CLIENTS.remove(c)

def fake_confidence(candle) -> float:
    try:
        rng = abs(candle["close"] - candle["open"])
        return min(1.0, 0.5 + rng * 50)
    except:
        return 0.5

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
