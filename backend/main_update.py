# backend/main_updated.py
# FastAPI server to receive frames + DOM JSON via WebSocket, run simple analysis and emit signals.
import asyncio
import base64
import datetime
import json
from typing import Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.websockets import WebSocketState
from pathlib import Path
import backend.ai_analyzer as ai

app = FastAPI(title="Nexus Mobile AI - Stream Receiver")

# expose static files from backend/static
ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "static"
if not STATIC_DIR.exists():
    STATIC_DIR.mkdir(parents=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# history of signals (in-memory). Each: {id, timestamp, pair, confidence, result, closed_at}
HISTORY = []
SIGNAL_THRESHOLD = 0.8

connected_viewers: set[WebSocket] = set()
connected_sources: set[WebSocket] = set()

@app.get("/health")
async def health():
    return {"status":"ok"}

@app.get("/history")
async def get_history():
    return JSONResponse(HISTORY)

@app.get("/")
async def root():
    # simple landing page redirect to viewer
    index = STATIC_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    return JSONResponse({"msg":"Nexus Mobile AI backend. Visit /static/viewer.html"})

def register_signal(pair: str, confidence: float) -> dict:
    rec = {
        "id": len(HISTORY) + 1,
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "pair": pair,
        "confidence": round(confidence, 3),
        "result": "PENDING",
        "closed_at": None
    }
    HISTORY.append(rec)
    return rec

async def broadcast_to_viewers(msg: dict):
    dead = []
    for ws in list(connected_viewers):
        try:
            if ws.application_state == WebSocketState.CONNECTED:
                await ws.send_text(json.dumps(msg))
        except Exception:
            dead.append(ws)
    for d in dead:
        try:
            connected_viewers.remove(d)
        except: pass

async def handle_frame_and_dom(frame_bytes: Optional[bytes], dom_json: Optional[dict], source_ws: WebSocket):
    """
    Runs analysis on incoming frame and dom. If AI finds a signal with confidence >= threshold,
    register and broadcast to viewers.
    """
    try:
        conf = ai.compute_confidence(frame_bytes, dom_json)
        timeframe = ai.detect_timeframe(dom_json)
        # require threshold
        if conf >= SIGNAL_THRESHOLD:
            rec = register_signal(pair="HOME/TEST", confidence=conf)
            # prepare message
            msg = {"type":"signal", "id": rec["id"], "pair": rec["pair"], "confidence": rec["confidence"], "timestamp": rec["timestamp"], "timeframe": timeframe}
            await broadcast_to_viewers(msg)
    except Exception as e:
        print("analyzer error:", e)

@app.websocket("/ws/stream")
async def ws_stream(ws: WebSocket):
    """
    This websocket accepts two modes of incoming data:
    - Binary frames (image bytes) via ws.receive_bytes()
    - Text messages (JSON) with type 'dom' containing DOM-extracted data.
    The client should send JSON like {"type":"dom", ...} and binary as raw bytes for frames.
    """
    await ws.accept()
    # determine if this is a 'viewer' or 'source' based on an initial message or path header.
    # We'll accept both. Clients may send {"role":"viewer"} as first text message.
    connected_sources.add(ws)
    try:
        # optional initial handshake
        try:
            init = await asyncio.wait_for(ws.receive_text(), timeout=0.5)
            # if init is JSON and role viewer, treat accordingly
            try:
                j = json.loads(init)
                if j.get("role") == "viewer":
                    connected_viewers.add(ws)
            except Exception:
                # not JSON or not role
                pass
        except asyncio.TimeoutError:
            pass
        # primary loop
        last_dom = None
        while True:
            msg = await ws.receive()
            if msg.get("type") == "websocket.receive":
                if "bytes" in msg:
                    frame = msg["bytes"]
                    # send ack
                    await ws.send_text(json.dumps({"type":"ack","size": len(frame)}))
                    # analyze (spawn task)
                    asyncio.create_task(handle_frame_and_dom(frame, last_dom, ws))
                    # also forward frame to viewers as base64
                    b64 = base64.b64encode(frame).decode("ascii")
                    fmsg = {"type":"frame","data":"data:image/jpeg;base64,"+b64}
                    await broadcast_to_viewers(fmsg)
                elif "text" in msg:
                    try:
                        text = msg["text"]
                        j = json.loads(text)
                    except Exception:
                        j = {"raw_text": msg.get("text")}
                    # if it's role viewer
                    if isinstance(j, dict) and j.get("role") == "viewer":
                        connected_viewers.add(ws)
                        await ws.send_text(json.dumps({"type":"info","msg":"registered as viewer"}))
                        continue
                    # dom message
                    if isinstance(j, dict) and j.get("type") == "dom":
                        last_dom = j.get("payload", {})
                        # optional: analyze DOM only
                        asyncio.create_task(handle_frame_and_dom(None, last_dom, ws))
                        # acks
                        await ws.send_text(json.dumps({"type":"ack_dom","len": len(json.dumps(last_dom))}))
                    else:
                        # generic text message ack
                        await ws.send_text(json.dumps({"type":"info","echo": j}))
            elif msg.get("type") == "websocket.disconnect":
                break
    except WebSocketDisconnect:
        print("source disconnected")
    finally:
        try:
            connected_sources.discard(ws)
            connected_viewers.discard(ws)
        except:
            pass

# simple admin endpoint to mark a signal closed (win/loss)
@app.post("/signal/{sig_id}/close")
async def close_signal(sig_id: int, payload: dict):
    result = payload.get("result", "LOSS")
    for s in HISTORY:
        if s["id"] == sig_id:
            s["result"] = result
            s["closed_at"] = datetime.datetime.utcnow().isoformat()+"Z"
            # broadcast update
            await broadcast_to_viewers({"type":"history_update","id": sig_id, "result": result})
            return JSONResponse({"ok":True,"signal":s})
    return JSONResponse({"ok":False,"error":"not found"}, status_code=404)
