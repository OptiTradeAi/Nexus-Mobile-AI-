# backend/main.py
import asyncio
import json
import datetime
import base64
from typing import List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Body
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from ai_analyzer import analyze_frame_base64, analyze_candle_json

app = FastAPI(title="Nexus Stream Server")

# CORS - permitir requests do userscript (mobile).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# mount static viewer
app.mount("/static", StaticFiles(directory="backend/static"), name="static")

# connected clients
STREAM_CLIENTS: List[WebSocket] = []
VIEWER_CLIENTS: List[WebSocket] = []

HISTORY = []
SIGNAL_THRESHOLD = 0.8

async def broadcast_to_viewers(message: dict):
    dead = []
    text = json.dumps(message)
    for ws in VIEWER_CLIENTS:
        try:
            await ws.send_text(text)
        except Exception:
            dead.append(ws)
    for d in dead:
        try:
            VIEWER_CLIENTS.remove(d)
        except:
            pass

@app.get("/health")
async def health():
    return {"status":"ok"}

@app.get("/")
async def index():
    return HTMLResponse("<html><body><h3>Nexus Stream Server</h3><p>Use /static/viewer.html para abrir o visualizador.</p></body></html>")

@app.post("/frame")
async def post_frame(payload: dict = Body(...)):
    """
    Recebe JSON: {"type":"frame","pair":"EURUSD-OTC","data":"<base64jpeg_no_prefix>"}
    """
    try:
        b64 = payload.get("data")
        if not b64:
            return JSONResponse({"error":"no data"}, status_code=400)
        pair = payload.get("pair", "OTC")
        msg = {"type":"frame", "pair": pair, "data": b64, "ts": datetime.datetime.utcnow().isoformat()+"Z"}
        await broadcast_to_viewers(msg)

        # run analyzer
        res = analyze_frame_base64(b64)
        if res.get("signal") and res.get("confidence", 0) >= SIGNAL_THRESHOLD:
            sig = {"pair": pair, "signal": res["signal"], "confidence": res["confidence"], "timestamp": res["timestamp"]}
            HISTORY.append(sig)
            await broadcast_to_viewers({"type":"signal", "data": sig})
        return JSONResponse({"status":"ok"})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.websocket("/ws/stream")
async def ws_stream(websocket: WebSocket):
    await websocket.accept()
    STREAM_CLIENTS.append(websocket)
    try:
        while True:
            msg = await websocket.receive()
            payload = None
            if 'text' in msg and msg['text'] is not None:
                try:
                    payload = json.loads(msg['text'])
                except:
                    payload = {"type":"raw", "data": msg['text']}
            elif 'bytes' in msg and msg['bytes'] is not None:
                b64 = base64.b64encode(msg['bytes']).decode('ascii')
                payload = {"type":"frame", "data": b64}
            else:
                continue

            if isinstance(payload, dict) and payload.get("type") == "frame":
                b64 = payload.get("data")
                pair = payload.get("pair", "OTC")
                msg_out = {"type":"frame", "pair": pair, "data": b64, "ts": datetime.datetime.utcnow().isoformat()+"Z"}
                await broadcast_to_viewers(msg_out)
                try:
                    res = analyze_frame_base64(b64)
                    if res.get("signal") and res.get("confidence",0) >= SIGNAL_THRESHOLD:
                        sig = {"pair": pair, "signal": res["signal"], "confidence": res["confidence"], "timestamp": res["timestamp"]}
                        HISTORY.append(sig)
                        await broadcast_to_viewers({"type":"signal", "data": sig})
                except Exception:
                    pass

            elif isinstance(payload, dict) and payload.get("type") == "candle":
                res = analyze_candle_json(payload.get("data", {}))
                pair = payload.get("data", {}).get("pair", "OTC")
                if res.get("signal") and res.get("confidence",0) >= SIGNAL_THRESHOLD:
                    sig = {"pair": pair, "signal": res["signal"], "confidence": res["confidence"], "timestamp": res.get("timestamp")}
                    HISTORY.append(sig)
                    await broadcast_to_viewers({"type":"signal", "data": sig})

    except WebSocketDisconnect:
        try:
            STREAM_CLIENTS.remove(websocket)
        except:
            pass
    except Exception:
        try:
            STREAM_CLIENTS.remove(websocket)
        except:
            pass

@app.websocket("/ws/viewer")
async def ws_viewer(websocket: WebSocket):
    await websocket.accept()
    VIEWER_CLIENTS.append(websocket)
    try:
        await websocket.send_text(json.dumps({"type":"history","data":HISTORY}))
        while True:
            msg = await websocket.receive_text()
            try:
                j = json.loads(msg)
                if j.get("cmd") == "get_history":
                    await websocket.send_text(json.dumps({"type":"history","data":HISTORY}))
            except:
                pass
    except WebSocketDisconnect:
        try:
            VIEWER_CLIENTS.remove(websocket)
        except:
            pass
    except Exception:
        try:
            VIEWER_CLIENTS.remove(websocket)
        except:
            pass
