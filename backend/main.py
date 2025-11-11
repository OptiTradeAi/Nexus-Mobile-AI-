from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import base64
from datetime import datetime
import pytz

app = FastAPI(title="Nexus Mobile AI")

# ---- CONFIG ----
TZ = pytz.timezone("America/Sao_Paulo")
connected_clients = set()
latest_frame = None

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- STATIC ----
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def root():
    return {
        "status": "Nexus Mobile AI ativo",
        "viewer_url": "/viewer",
        "stream": "/ws/stream",
        "timezone": "America/Sao_Paulo"
    }


@app.get("/health")
async def health():
    return {"status": "ok", "time": datetime.now(TZ).isoformat()}


@app.get("/viewer", response_class=HTMLResponse)
async def viewer():
    try:
        with open("static/viewer.html", "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    except Exception as e:
        return JSONResponse({"error": f"viewer.html não encontrado: {e}"}, status_code=500)


# ---- WEBSOCKET PARA VIEWERS ----
@app.websocket("/ws/stream")
async def stream_ws(websocket: WebSocket):
    await websocket.accept()
    connected_clients.add(websocket)
    print("Viewer conectado:", websocket.client)

    try:
        # Envia o último frame, se existir
        if latest_frame:
            await websocket.send_json({"type": "frame", "data": latest_frame})
        while True:
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        connected_clients.remove(websocket)
        print("Viewer desconectado:", websocket.client)
    except Exception as e:
        print("Erro no viewer WS:", e)
        connected_clients.discard(websocket)


# ---- WEBSOCKET PARA EXTENSÃO ----
@app.websocket("/ws")
async def receive_frame_ws(websocket: WebSocket):
    global latest_frame
    await websocket.accept()
    print("Extensão conectada:", websocket.client)
    try:
        while True:
            msg = await websocket.receive_json()
            if msg.get("type") == "frame" and msg.get("data"):
                latest_frame = msg["data"]

                # Envia para todos os viewers conectados
                dead = []
                for client in connected_clients:
                    try:
                        await client.send_json({"type": "frame", "data": latest_frame})
                    except:
                        dead.append(client)
                for d in dead:
                    connected_clients.discard(d)

    except WebSocketDisconnect:
        print("Extensão desconectada:", websocket.client)
    except Exception as e:
        print("Erro WS extensão:", e)


# ---- POST Fallback ----
@app.post("/frame")
async def post_frame(request: Request):
    global latest_frame
    try:
        data = await request.json()
        frame_data = data.get("data")
        if not frame_data:
            return JSONResponse({"error": "Sem dados"}, status_code=400)
        latest_frame = frame_data

        # Broadcast do frame
        for client in list(connected_clients):
            try:
                await client.send_json({"type": "frame", "data": latest_frame})
            except:
                connected_clients.discard(client)

        rid = base64.urlsafe_b64encode(datetime.now().isoformat().encode()).decode()[:12]
        return {"status": "ok", "rid": rid}

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
