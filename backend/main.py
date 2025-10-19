# backend/main.py
import base64
import asyncio
import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from typing import List

app = FastAPI()
app.mount("/static", StaticFiles(directory="backend/static"), name="static")

# Keep a set of connected viewer websockets
VIEWERS: List[WebSocket] = []
# Keep last N frames (simple ring)
LAST_FRAMES = []
MAX_FRAMES = 200

@app.get("/")
async def index():
    html_path = "backend/static/viewer.html"
    try:
        with open(html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    except FileNotFoundError:
        return JSONResponse({"detail":"viewer.html not found"}, status_code=404)

@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.datetime.utcnow().isoformat() + "Z"}

@app.websocket("/ws/stream")
async def ws_stream(ws: WebSocket):
    # endpoint for the producer (Tampermonkey) -> sends base64 frames
    await ws.accept()
    try:
        while True:
            data = await ws.receive_text()  # expect JSON with {type:"frame", data:"base64,..."}
            # Broadcast to viewers
            try:
                for v in VIEWERS:
                    try:
                        await v.send_text(data)
                    except:
                        pass
            except:
                pass

            # store last frames (keep small memory)
            if isinstance(data, str) and data.startswith('{"type'):
                # naive store
                if len(LAST_FRAMES) >= MAX_FRAMES:
                    LAST_FRAMES.pop(0)
                LAST_FRAMES.append({"received": datetime.datetime.utcnow().isoformat()+"Z", "payload_len": len(data)})
    except WebSocketDisconnect:
        print("Stream client disconnected")
    except Exception as e:
        print("Stream error:", e)

@app.websocket("/ws/viewer")
async def ws_viewer(ws: WebSocket):
    # endpoint for viewer page to receive frames
    await ws.accept()
    VIEWERS.append(ws)
    try:
        # Send last frame summaries on connect
        await ws.send_text('{"type":"meta","last_frames":' + str(len(LAST_FRAMES)) + '}')
        while True:
            # keep the connection alive
            await asyncio.sleep(10)
    except WebSocketDisconnect:
        print("Viewer disconnected")
    finally:
        try:
            VIEWERS.remove(ws)
        except:
            pass

@app.get("/history")
async def history():
    return JSONResponse(LAST_FRAMES)
