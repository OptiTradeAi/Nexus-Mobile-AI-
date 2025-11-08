# main.py
import os
import json
import base64
from datetime import datetime
from typing import List, Dict, Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

STATIC_DIR = "static"
FRAMES_DIR = os.path.join(STATIC_DIR, "frames")
os.makedirs(FRAMES_DIR, exist_ok=True)

app = FastAPI(title="Nexus Mobile AI - Backend")

# CORS (liberal for testing; restrinja em produção)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Servir arquivos estáticos (viewer.html em /static)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# In-memory state (simple)
frames_received = 0
last_meta: Dict[str, Any] = {}
last_frame_filename: str = ""
clients: List[WebSocket] = []
LOGS: List[str] = []

DEBUG_LOG_TOKEN = os.environ.get("DEBUG_LOG_TOKEN", "d33144d6cb84fe05bf38bb9f22591683")

def log(msg: str):
    t = datetime.utcnow().isoformat()
    entry = f"{t} {msg}"
    LOGS.insert(0, entry)
    if len(LOGS) > 500:
        LOGS.pop()

class ConnectionManager:
    def __init__(self):
        self.active: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active.append(websocket)
        log("WS client connected; total:" + str(len(self.active)))

    def disconnect(self, websocket: WebSocket):
        try:
            self.active.remove(websocket)
            log("WS client disconnected; total:" + str(len(self.active)))
        except ValueError:
            pass

    async def send_text_all(self, message: str):
        for ws in list(self.active):
            try:
                await ws.send_text(message)
            except Exception:
                self.disconnect(ws)

    async def send_bytes_all(self, data: bytes):
        for ws in list(self.active):
            try:
                await ws.send_bytes(data)
            except Exception:
                self.disconnect(ws)

manager = ConnectionManager()

@app.get("/status")
async def status():
    return {"status": "ok", "frames_received": frames_received, "last_frame": last_frame_filename}

@app.get("/debug/logs")
async def get_logs(token: str = ""):
    if token != DEBUG_LOG_TOKEN:
        raise HTTPException(status_code=403, detail="forbidden")
    # return last 200 logs
    return JSONResponse({"logs": LOGS[:200]})

@app.post("/frame")
async def post_frame(request: Request):
    """
    HTTP fallback: expects JSON with keys:
    - pair
    - data_b64 (base64 jpeg)
    - method (optional)
    - rid (optional)
    """
    global frames_received, last_frame_filename, last_meta
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="invalid json")

    pair = body.get("pair", "unknown")
    data_b64 = body.get("data_b64")
    rid = body.get("rid") or ("http-" + datetime.utcnow().strftime("%Y%m%d%H%M%S%f"))
    if not data_b64:
        raise HTTPException(status_code=400, detail="data_b64 required")

    try:
        imgbytes = base64.b64decode(data_b64)
    except Exception as e:
        raise HTTPException(status_code=400, detail="invalid base64")

    filename = f"{rid}.jpg"
    filepath = os.path.join(FRAMES_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(imgbytes)

    frames_received += 1
    last_frame_filename = filepath
    last_meta = {"type": "meta", "rid": rid, "pair": pair, "method": body.get("method", "http"), "ts": datetime.utcnow().isoformat()}

    # broadcast meta then binary to websocket clients
    try:
        await manager.send_text_all(json.dumps(last_meta))
        await manager.send_bytes_all(imgbytes)
    except Exception as e:
        log(f"broadcast error: {e}")

    log(f"frame received HTTP rid={rid} pair={pair}")
    return {"status": "ok", "rid": rid}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint used by userscript to send:
    - JSON meta messages (text)
    - binary frames (bytes)
    Also used by viewer to receive broadcasts. Clients should provide a token query parameter for light auth (optional).
    """
    token = websocket.query_params.get("token", "")
    # light token check if desired (skip for now)
    await manager.connect(websocket)
    try:
        while True:
            msg = await websocket.receive()
            # msg can be {'type':'websocket.receive','text':...} or {'type':'websocket.receive','bytes':...}
            if "text" in msg and msg["text"] is not None:
                txt = msg["text"]
                # try JSON
                try:
                    obj = json.loads(txt)
                except Exception:
                    obj = {"raw_text": txt}
                # handle types
                mtype = obj.get("type")
                if mtype in ("meta", "pusher_event", "ohlc_m5", "signal", "meta_info"):
                    # store last meta if meta
                    last_meta.update(obj if isinstance(obj, dict) else {})
                    await manager.send_text_all(json.dumps(obj))
                    log(f"received text type={mtype}")
                else:
                    # broadcast generically
                    await manager.send_text_all(json.dumps(obj))
                    log("received text generic")
            elif "bytes" in msg and msg["bytes"] is not None:
                data = msg["bytes"]
                # save to file
                rid = f"ws-{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"
                filename = f"{rid}.jpg"
                filepath = os.path.join(FRAMES_DIR, filename)
                with open(filepath, "wb") as f:
                    f.write(data)
                frames_received += 1
                last_frame_filename = filepath
                # broadcast binary to all
                await manager.send_bytes_all(data)
                log(f"received bytes saved {filename}")
            else:
                # ping/pong or unknown
                pass
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        manager.disconnect(websocket)
        log(f"ws exception: {e}")

@app.get("/")
async def root():
    return {"detail": "Nexus backend: see /static/viewer.html for viewer"}
