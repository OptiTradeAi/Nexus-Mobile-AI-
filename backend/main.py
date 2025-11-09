# backend/main.py
import asyncio, base64, json, datetime, zoneinfo
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from typing import Dict, Any, List
from ai_engine import analyze_and_maybe_signal, register_frame, HISTORY, SIGNAL_THRESHOLD, evaluate_pending_signals, TZ

app = FastAPI()
app.mount("/static", StaticFiles(directory="backend/static"), name="static")

VIEWERS: List[WebSocket] = []
STREAMERS: Dict[str, WebSocket] = {}  # optional: map client id -> ws

@app.get("/")
async def root():
    return HTMLResponse("<h3>Nexus Mobile AI Backend — healthy. See /health and /static/viewer.html</h3>")

@app.get("/health")
async def health():
    return {"status": "ok", "time": datetime.datetime.now(TZ).isoformat()}

@app.get("/history")
async def get_history():
    return JSONResponse(HISTORY)

# WebSocket for extension -> stream (sends frames & candle data)
@app.websocket("/ws/stream")
async def ws_stream(ws: WebSocket):
    await ws.accept()
    client_id = f"stream-{id(ws)}"
    STREAMERS[client_id] = ws
    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except:
                # not JSON? ignore
                continue
            # msg expected {type:'frame'|'tick', ...}
            if msg.get("type") == "frame":
                # frame contains base64 image at msg['data'], pair at msg.get('pair')
                await register_frame(msg)  # store last frame for viewer & optional vision processing
                # forward to viewers
                for v in VIEWERS:
                    try:
                        await v.send_text(json.dumps({"type":"frame","pair":msg.get("pair"),"data": msg.get("data"), "ts": datetime.datetime.now(TZ).isoformat()}))
                    except:
                        pass
            elif msg.get("type") == "tick":
                # tick/candle numeric data
                tick = msg.get("tick")
                if tick:
                    # feed analysis pipeline
                    signal = analyze_and_maybe_signal(tick)
                    # forward tick to viewers
                    for v in VIEWERS:
                        try:
                            await v.send_text(json.dumps({"type":"tick","tick":tick}))
                        except:
                            pass
                    # if a signal generated, notify viewers
                    if signal:
                        for v in VIEWERS:
                            try:
                                await v.send_text(json.dumps({"type":"signal","signal":signal}))
                            except:
                                pass
            # periodically evaluate pending signals for result when candle closes
            await evaluate_pending_signals()
    except WebSocketDisconnect:
        STREAMERS.pop(client_id, None)

# WebSocket for viewer clients to receive frames/ticks/signals
@app.websocket("/ws/viewer")
async def ws_viewer(ws: WebSocket):
    await ws.accept()
    VIEWERS.append(ws)
    try:
        while True:
            # viewer can request history or ping
            data = await ws.receive_text()
            try:
                msg = json.loads(data)
            except:
                msg = {}
            if msg.get("cmd") == "history":
                await ws.send_text(json.dumps({"type":"history","history":HISTORY}))
            await asyncio.sleep(0.01)
    except WebSocketDisconnect:
        try:
            VIEWERS.remove(ws)
        except:
            pass

# Fallback POST endpoint to accept frames (if WS not available)
@app.post("/frame")
async def post_frame(req: Request):
    body = await req.json()
    if not body.get("data"):
        raise HTTPException(status_code=400, detail="no data")
    await register_frame(body)
    # forward to viewers (async fire-and-forget)
    for v in VIEWERS:
        try:
            await v.send_text(json.dumps({"type":"frame","pair": body.get("pair"), "data": body.get("data"), "ts": datetime.datetime.now(TZ).isoformat()}))
        except:
            pass
    return {"ok": True}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
