from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import asyncio, json, base64
from datetime import datetime
import pytz

# Import corrigido 👇
from backend.ai_engine_fusion import analyze_frame

app = FastAPI()
TZ = pytz.timezone("America/Sao_Paulo")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def root():
    return {"status": "Nexus Mobile AI ativo", "viewer_url": "/static/viewer.html", "stream": "/ws/stream"}

@app.get("/health")
async def health():
    return {"status": "ok", "time": datetime.now(TZ).isoformat()}

clients = set()
last_frame = None

@app.websocket("/ws/stream")
async def websocket_endpoint(websocket: WebSocket):
    global last_frame
    await websocket.accept()
    clients.add(websocket)
    print("Cliente conectado ao stream.")

    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)

            result = analyze_frame(payload["data"])
            last_frame = payload.get("data")

            for client in list(clients):
                try:
                    await client.send_json({"type": "frame", "data": last_frame, "analysis": result})
                except Exception:
                    clients.remove(client)
    except Exception as e:
        print("Stream encerrado:", e)
    finally:
        clients.remove(websocket)

@app.get("/viewer")
async def viewer():
    html_path = "static/viewer.html"
    try:
        with open(html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read(), status_code=200)
    except FileNotFoundError:
        return JSONResponse(content={"error": "viewer.html não encontrado"}, status_code=404)
