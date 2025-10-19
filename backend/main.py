# backend/main.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
import base64, json

app = FastAPI()
latest_frame = None  # guarda o último frame recebido

# Página principal
@app.get("/")
async def index():
    return FileResponse("backend/static/viewer.html")

# Endpoint WebSocket
@app.websocket("/ws/stream")
async def websocket_endpoint(ws: WebSocket):
    global latest_frame
    await ws.accept()
    print("✅ Conexão WS aceita")
    try:
        while True:
            data = await ws.receive_text()
            payload = json.loads(data)

            # Recebe frame
            if payload.get("type") == "frame":
                latest_frame = payload["image"]
                print("📡 Frame recebido")

            # Responde ACK
            await ws.send_text(json.dumps({"status": "ok"}))

    except WebSocketDisconnect:
        print("❌ Cliente desconectado")

# Endpoint para o viewer requisitar frame
@app.get("/latest")
async def get_latest():
    if latest_frame:
        return {"image": latest_frame}
    return {"image": None}
