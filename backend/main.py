# backend/main.py - FastAPI + WebSocket receiver + engine stub
import datetime, json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from starlette.websockets import WebSocketState

app = FastAPI()
HISTORY = []  # each entry: {timestamp, pair, confidence, result}
SIGNAL_THRESHOLD = 0.8

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/history")
async def get_history():
    return JSONResponse(HISTORY)

@app.websocket("/ws/stream")
async def ws_stream(ws: WebSocket):
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

                try:
                    if ws.application_state == WebSocketState.CONNECTED:
                        await ws.send_text(json.dumps({
                            "type": "signal",
                            "pair": rec["pair"],
                            "confidence": conf,
                            "timestamp": rec["timestamp"]
                        }))
                except:
                    pass

            await ws.send_text(json.dumps({
                "type": "ack",
                "size": len(data),
                "confidence": conf
            }))
    except WebSocketDisconnect:
        print("Cliente desconectado")

def fake_confidence(nbytes: int) -> float:
    if nbytes > 200000: return 0.9
    if nbytes > 50000: return 0.82
    if nbytes > 10000: return 0.6
    return 0.4

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
