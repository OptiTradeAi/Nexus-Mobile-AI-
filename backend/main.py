# backend/main.py
import datetime, json, os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.websockets import WebSocketState

app = FastAPI()
HISTORY = []
CLIENTS = set()
SIGNAL_THRESHOLD = 0.8

# --- endpoints simples ---
@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/history")
async def get_history():
    return JSONResponse(HISTORY)

# --- websocket principal ---
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    CLIENTS.add(ws)
    print("📡 Novo cliente WS conectado")
    try:
        while True:
            # recebendo texto JSON com candle
            text = await ws.receive_text()
            candle = json.loads(text)
            conf = fake_confidence(candle)
            rec = {
                "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                "pair": candle.get("symbol", "HOME/OTC"),
                "confidence": conf,
                "result": "PENDING",
                "open": candle.get("open"),
                "close": candle.get("close"),
                "high": candle.get("high"),
                "low": candle.get("low"),
            }
            HISTORY.append(rec)

            # broadcast candle
            await broadcast({"type": "candle", "data": rec})

            # se for sinal, broadcast sinal
            if conf >= SIGNAL_THRESHOLD:
                await broadcast({"type": "signal", "data": rec})

    except WebSocketDisconnect:
        CLIENTS.discard(ws)
        print("❌ Cliente WS desconectado")

async def broadcast(message: dict):
    remove = []
    text = json.dumps(message)
    for c in CLIENTS:
        try:
            await c.send_text(text)
        except Exception:
            remove.append(c)
    for r in remove:
        CLIENTS.discard(r)

def fake_confidence(candle) -> float:
    try:
        rng = abs(float(candle["close"]) - float(candle["open"]))
        return min(1.0, 0.5 + rng * 50)
    except Exception:
        return 0.5

# --- montar frontend como estático (USAR CAMINHO ABSOLUTO) ---
HERE = os.path.dirname(__file__)
FRONTEND_PATH = os.path.abspath(os.path.join(HERE, "..", "frontend"))

# diagnóstico no startup
@app.on_event("startup")
async def startup_event():
    print("=== STARTUP DIAGNOSTIC ===")
    print("backend __file__:", __file__)
    print("Expected frontend path:", FRONTEND_PATH)
    exists = os.path.exists(FRONTEND_PATH)
    print("frontend exists?:", exists)
    if exists:
        index_path = os.path.join(FRONTEND_PATH, "index.html")
        print("index.html exists?:", os.path.exists(index_path))
    print("===========================")

# monta os arquivos estáticos na raiz "/"
if os.path.exists(FRONTEND_PATH):
    app.mount("/", StaticFiles(directory=FRONTEND_PATH, html=True), name="frontend")
else:
    print("Warning: frontend folder not found at", FRONTEND_PATH, "- root / will return 404 until fixed.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000)
