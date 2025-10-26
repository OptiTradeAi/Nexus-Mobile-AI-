from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import json
import time

app = FastAPI()

# Monta a pasta /static
app.mount("/static", StaticFiles(directory="backend/static"), name="static")

latest_data = None  # Armazena o último dado recebido

@app.get("/")
async def get_root():
    with open("backend/static/viewer.html", "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())

@app.websocket("/ws/stream")
async def websocket_endpoint(websocket: WebSocket):
    global latest_data
    await websocket.accept()
    print("🟢 Conexão recebida da extensão")
    try:
        while True:
            data = await websocket.receive_text()
            latest_data = json.loads(data)
            print(f"📦 Dado recebido: {latest_data}")
    except Exception as e:
        print("⚠️ Conexão finalizada:", e)

@app.websocket("/ws/viewer")
async def websocket_viewer(websocket: WebSocket):
    print("👁️ Viewer conectado")
    await websocket.accept()
    last_sent = 0
    try:
        while True:
            if latest_data:
                await websocket.send_json({
                    "timestamp": time.strftime("%H:%M:%S"),
                    "data": latest_data
                })
                last_sent = time.time()
            await asyncio.sleep(1)
    except Exception as e:
        print("Viewer desconectado:", e)
