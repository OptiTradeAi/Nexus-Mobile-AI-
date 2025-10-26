import asyncio
import json
import time
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI()

# Monta a pasta de arquivos estáticos
app.mount("/static", StaticFiles(directory="backend/static"), name="static")

latest_data = None  # Último dado recebido

@app.get("/")
async def get_root():
    with open("backend/static/viewer.html", "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())

@app.websocket("/ws/stream")
async def websocket_endpoint(websocket: WebSocket):
    """Recebe dados da extensão"""
    global latest_data
    await websocket.accept()
    print("🟢 Extensão conectada e enviando dados...")
    try:
        while True:
            data = await websocket.receive_text()
            parsed = json.loads(data)
            latest_data = {
                "pair": parsed.get("pair", "OTC"),
                "close": parsed.get("close", 0.0),
                "timestamp": parsed.get("timestamp", time.strftime("%H:%M:%S"))
            }
            print(f"📦 Recebido: {latest_data}")
    except Exception as e:
        print("⚠️ Conexão encerrada:", e)

@app.websocket("/ws/viewer")
async def websocket_viewer(websocket: WebSocket):
    """Envia os dados recebidos para o visualizador"""
    global latest_data
    await websocket.accept()
    print("👁️ Visualizador conectado...")
    try:
        while True:
            if latest_data:
                await websocket.send_json(latest_data)
            await asyncio.sleep(1)
    except Exception as e:
        print("Viewer desconectado:", e)
