# backend/main.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import asyncio, base64, uuid
from typing import List
import os

app = FastAPI()
# static folder (viewer) - adjust path if viewer moved
static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.isdir(static_dir):
    # if static doesn't exist, try ../static (in case file structure differs)
    static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# store connected websockets
stream_clients: List[WebSocket] = []  # extension connections (optional)
viewer_clients: List[WebSocket] = []

# simple health
@app.get("/health")
async def health():
    return {"status":"ok"}

# fallback POST to accept frames
@app.post("/frame")
async def post_frame(req: Request):
    j = await req.json()
    # broadcast to viewers
    await broadcast_to_viewers(j)
    return JSONResponse({"rid": str(uuid.uuid4())})

async def broadcast_to_viewers(payload):
    dead = []
    for ws in viewer_clients:
        try:
            await ws.send_json(payload)
        except Exception:
            dead.append(ws)
    for d in dead:
        try:
            viewer_clients.remove(d)
        except:
            pass

# websocket route for extension to send frames
@app.websocket("/ws/stream")
async def websocket_stream(websocket: WebSocket):
    await websocket.accept()
    # this connection is mainly a sender - we don't need to add to stream_clients
    try:
        while True:
            data = await websocket.receive_text()
            # try parse json
            try:
                import json
                j = json.loads(data)
            except:
                j = {"raw": data}
            # broadcast to all viewers
            await broadcast_to_viewers(j)
    except WebSocketDisconnect:
        return
    except Exception as e:
        print("stream ws error:", e)
        return

# websocket route for viewers (UI) to receive frames
@app.websocket("/ws/viewer")
async def websocket_viewer(websocket: WebSocket):
    await websocket.accept()
    viewer_clients.append(websocket)
    try:
        while True:
            # keep connection alive - viewer may send pings
            msg = await websocket.receive_text()
            # ignore or handle ping
    except WebSocketDisconnect:
        try:
            viewer_clients.remove(websocket)
        except:
            pass
    except Exception:
        try:
            viewer_clients.remove(websocket)
        except:
            pass

# basic index - redirect or info
@app.get("/")
async def index():
    content = {
        "status":"Nexus Mobile AI",
        "viewer_url":"/static/viewer.html",
        "stream":"/ws/stream"
    }
    return JSONResponse(content)
