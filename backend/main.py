# backend/main.py
import asyncio
import json
import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from typing import List
from ai_analyzer import analyze_frame_base64, analyze_candle_json

app = FastAPI(title="Nexus Stream Server")

# mount static viewer
app.mount("/static", StaticFiles(directory="backend/static"), name="static")

# keep lists of connected websockets
STREAM_CLIENTS: List[WebSocket] = []   # clients sending stream (extensions)
VIEWER_CLIENTS: List[WebSocket] = []   # dashboards / browser viewers
AI_CLIENTS: List[WebSocket] = []       # future: agent connections

HISTORY = []  # list of signals/entries

SIGNAL_THRESHOLD = 0.8

@app.get("/health")
async def health():
    return {"status":"ok"}

@app.get("/")
async def index():
    # simple page linking to viewer
    return HTMLResponse("<html><body><h3>Nexus Stream Server</h3><p>Use /static/viewer.html to open the visualizer.</p></body></html>")

@app.websocket("/ws/stream")
async def ws_stream(websocket: WebSocket):
    # endpoint for extensions/userscript to send frames (base64) or candle JSON
    await websocket.accept()
    STREAM_CLIENTS.append(websocket)
    try:
        while True:
            # we accept text messages (JSON) and also binary (bytes)
            data = await websocket.receive_text()
            # expect JSON like {"type":"frame","data":"<base64jpeg>"} or {"type":"candle", ...}
            try:
                payload = json.loads(data)
            except:
                payload = {"type":"raw","data": data}
            # handle frame
            if isinstance(payload, dict) and payload.get("type") == "frame":
                b64 = payload.get("data")
                # forward to viewer clients
                msg = {"type":"frame", "data": b64, "ts": datetime.datetime.utcnow().isoformat()+"Z"}
                await broadcast_to_viewers(msg)
                # run analyzer
                res = analyze_frame_base64(b64)
                if res.get("confidence",0) >= SIGNAL_THRESHOLD and res.get("signal"):
                    record = {"timestamp": res.get("timestamp"), "signal": res.get("signal"), "confidence": res.get("confidence")}
                    HISTORY.append(record)
                    # broadcast signal
                    await broadcast_to_viewers({"type":"signal","data":record})
            elif isinstance(payload, dict) and payload.get("type") == "candle":
                # send candle to viewers and analyze
                await broadcast_to_viewers({"type":"candle","data":payload})
                res = analyze_candle_json(payload)
                if res.get("confidence",0) >= SIGNAL_THRESHOLD and res.get("signal"):
                    record = {"timestamp": res.get("timestamp"), "signal": res.get("signal"), "confidence": res.get("confidence")}
                    HISTORY.append(record)
                    await broadcast_to_viewers({"type":"signal","data":record})
            else:
                await websocket.send_text(json.dumps({"type":"ack","received": True}))
    except WebSocketDisconnect:
        try:
            STREAM_CLIENTS.remove(websocket)
        except:
            pass

@app.websocket("/ws/viewer")
async def ws_viewer(ws: WebSocket):
    await ws.accept()
    VIEWER_CLIENTS.append(ws)
    try:
        while True:
            data = await ws.receive_text()  # viewers may send commands later
            # ignore for now
    except WebSocketDisconnect:
        try:
            VIEWER_CLIENTS.remove(ws)
        except:
            pass

async def broadcast_to_viewers(message: dict):
    text = json.dumps(message)
    dead = []
    for c in VIEWER_CLIENTS:
        try:
            await c.send_text(text)
        except:
            dead.append(c)
    for d in dead:
        try:
            VIEWER_CLIENTS.remove(d)
        except:
            pass

@app.get("/history")
async def get_history():
    return JSONResponse(HISTORY)
