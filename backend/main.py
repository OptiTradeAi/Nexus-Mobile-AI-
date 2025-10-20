# backend/main.py
import base64
import datetime
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from typing import List

app = FastAPI()
HISTORY: List[dict] = []   # history of signals / events
FRAMES: List[dict] = []    # last N frames (timestamp, dataurl)

# mount static folder (viewer.html lives in backend/static/)
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
async def root():
    # serve viewer.html
    f = static_dir / "viewer.html"
    if f.exists():
        return FileResponse(f, media_type="text/html")
    return HTMLResponse("<h1>Nexus Stream</h1><p>Backend running.</p>")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/history")
async def get_history():
    # return last 100 entries
    return JSONResponse(HISTORY[-200:])


@app.get("/frames")
async def get_frames():
    # return last few frames metadata (not images to save bandwidth by default)
    return JSONResponse([{"timestamp": f["timestamp"]} for f in FRAMES[-50:]])


# WebSocket: clients (viewer) can receive broadcasted frames.
# Also the Tampermonkey script will connect here and PUSH frames as base64 images.
clients: List[WebSocket] = []

@app.websocket("/ws/stream")
async def ws_stream(ws: WebSocket):
    await ws.accept()
    clients.append(ws)
    try:
        while True:
            msg = await ws.receive_text()
            # Expect JSON messages:
            # { "type":"frame", "data":"data:image/png;base64,...." }
            # or { "type":"dom", "payload": {...} }
            try:
                obj = json.loads(msg)
            except Exception:
                # ignore non-json or malformed
                continue

            if obj.get("type") == "frame" and obj.get("data"):
                timestamp = datetime.datetime.utcnow().isoformat() + "Z"
                dataurl = obj["data"]
                # keep last N frames
                FRAMES.append({"timestamp": timestamp, "data": dataurl})
                if len(FRAMES) > 300:
                    FRAMES.pop(0)
                # optionally store small history entry
                HISTORY.append({"timestamp": timestamp, "event": "frame_received"})
                if len(HISTORY) > 1000:
                    HISTORY.pop(0)
                # broadcast to all connected viewer-clients
                bcast = json.dumps({"type":"frame","timestamp":timestamp,"data":dataurl})
                # iterate copy to avoid mutation errors
                for c in clients.copy():
                    try:
                        # do not send back to origin (optional) - we still will send
                        await c.send_text(bcast)
                    except Exception:
                        try:
                            clients.remove(c)
                        except:
                            pass

            elif obj.get("type") == "dom":
                ts = datetime.datetime.utcnow().isoformat() + "Z"
                HISTORY.append({"timestamp": ts, "event": "dom", "payload": obj.get("payload")})
                if len(HISTORY) > 1000:
                    HISTORY.pop(0)
                # echo back ack
                await ws.send_text(json.dumps({"type":"ack","timestamp":ts}))
            else:
                # unknown type, ack anyway
                await ws.send_text(json.dumps({"type":"ack","timestamp":datetime.datetime.utcnow().isoformat()+"Z"}))

    except WebSocketDisconnect:
        try:
            clients.remove(ws)
        except:
            pass
        print("WebSocket disconnected")
