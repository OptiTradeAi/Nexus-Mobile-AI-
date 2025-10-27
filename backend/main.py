# /backend/main.py
import asyncio
import json
import datetime
from typing import Dict, Any, List
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from ai_analyzer import analyze_candles

app = FastAPI(title="Nexus Mobile AI - Stream Receiver")

# Allow CORS from anywhere for testing (narrow in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files (viewer)
app.mount("/static", StaticFiles(directory="backend/static"), name="static")

# In-memory structures
HISTORY: Dict[str, List[Dict[str, Any]]] = {}   # pair -> list of candles
VIEWERS: List[WebSocket] = []
STREAM_CLIENTS: List[WebSocket] = []

# Helper broadcast
async def broadcast_to_viewers(message: Dict[str, Any]):
    dead = []
    for ws in VIEWERS:
        try:
            await ws.send_text(json.dumps(message))
        except Exception:
            dead.append(ws)
    for d in dead:
        try:
            VIEWERS.remove(d)
        except:
            pass

@app.get("/health")
async def health():
    return {"status": "ok", "time": datetime.datetime.utcnow().isoformat() + "Z"}

@app.get("/history")
async def get_history():
    return JSONResponse(HISTORY)

@app.get("/")
async def index():
    # simple redirect to static viewer or info
    try:
        with open("backend/static/viewer.html", "r", encoding="utf-8") as f:
            html = f.read()
        return HTMLResponse(html)
    except Exception:
        return JSONResponse({"msg":"Viewer not found. Check backend/static/viewer.html"})

@app.websocket("/ws/stream")
async def ws_stream(ws: WebSocket):
    """
    Endpoint used by the browser extension/Tamper/Vilmonkey to send:
    - JSON candles: {"type":"candle", "pair":"X", "timestamp": "...", "open":..., "high":..., "low":..., "close":..., "volume":...}
    - Or frames: {"type":"frame", "pair":"X", "data":"base64..."}
    """
    await ws.accept()
    STREAM_CLIENTS.append(ws)
    try:
        await broadcast_to_viewers({"type":"status", "source":"backend", "msg":"Stream client connected"})
        while True:
            msg = await ws.receive_text()
            # parse
            try:
                obj = json.loads(msg)
            except Exception:
                # ignore non-json
                continue

            # Candle message
            if obj.get("type") == "candle":
                pair = obj.get("pair", "UNKNOWN")
                # ensure history list
                HISTORY.setdefault(pair, [])
                # append candle snapshot
                HISTORY[pair].append({
                    "timestamp": obj.get("timestamp"),
                    "open": obj.get("open"),
                    "high": obj.get("high"),
                    "low": obj.get("low"),
                    "close": obj.get("close"),
                    "volume": obj.get("volume", 0)
                })
                # keep history short (last 200)
                if len(HISTORY[pair]) > 500:
                    HISTORY[pair] = HISTORY[pair][-500:]

                # run analyzer against the history for this pair
                analysis = analyze_candles(HISTORY[pair][:-1], HISTORY[pair][-1])
                # Prepare message for viewers
                payload = {
                    "type": "analysis",
                    "pair": pair,
                    "analysis": analysis,
                    "last_candle": HISTORY[pair][-1]
                }
                # send to viewers
                await broadcast_to_viewers(payload)

                # if analyzer recommends send==True -> create signal entry
                if analysis.get("send"):
                    signal = {
                        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                        "pair": pair,
                        "decision": analysis["decision"],
                        "confidence": analysis["confidence"],
                        "explanation": analysis["explanation"],
                        "time_to_open": analysis["time_to_open"]
                    }
                    # store signal in history (separate list)
                    HISTORY.setdefault("_signals", [])
                    HISTORY["_signals"].append(signal)
                    # broadcast signal
                    await broadcast_to_viewers({"type": "signal", "signal": signal})

                # ack back to stream client
                try:
                    await ws.send_text(json.dumps({"type":"ack","status":"ok","analysis":analysis}))
                except:
                    pass

            elif obj.get("type") == "frame":
                # forward frames to viewers
                payload = {
                    "type":"frame",
                    "pair": obj.get("pair","UNKNOWN"),
                    "data": obj.get("data")  # base64 image
                }
                await broadcast_to_viewers(payload)
                # ack
                try:
                    await ws.send_text(json.dumps({"type":"ack","status":"ok","frame":True}))
                except:
                    pass
            else:
                # unknown type - just broadcast raw
                await broadcast_to_viewers({"type":"raw","payload":obj})
    except WebSocketDisconnect:
        try:
            STREAM_CLIENTS.remove(ws)
        except:
            pass
        await broadcast_to_viewers({"type":"status","msg":"Stream client disconnected"})
    except Exception as e:
        try:
            STREAM_CLIENTS.remove(ws)
        except:
            pass
        await broadcast_to_viewers({"type":"error","msg": str(e)})

@app.websocket("/ws/viewer")
async def ws_viewer(ws: WebSocket):
    """Clients (web UI) connect here to receive updates in real time"""
    await ws.accept()
    VIEWERS.append(ws)
    try:
        # on connect, send initial state
        await ws.send_text(json.dumps({"type":"status","msg":"viewer connected"}))
        # send history summary
        await ws.send_text(json.dumps({"type":"history_summary", "pairs": list(HISTORY.keys())}))
        while True:
            # viewers might send pings or commands; just keep the connection alive
            msg = await ws.receive_text()
            # echo or respond to simple commands
            try:
                data = json.loads(msg)
                if data.get("cmd") == "get_history":
                    await ws.send_text(json.dumps({"type":"history", "history": HISTORY}))
            except:
                pass
    except WebSocketDisconnect:
        try:
            VIEWERS.remove(ws)
        except:
            pass
    except Exception:
        try:
            VIEWERS.remove(ws)
        except:
            pass
