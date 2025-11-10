from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

app = FastAPI()

# --- Permissões de acesso ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

active_connections = []

@app.get("/")
async def home():
    return {"status": "online", "ws": "/ws/stream"}

@app.websocket("/ws/stream")
async def websocket_stream(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    print("🟢 Conexão WebSocket recebida")

    try:
        while True:
            data = await websocket.receive_text()
            print("📦 Recebido:", data[:100])
            for conn in active_connections:
                if conn != websocket:
                    await conn.send_text(data)
    except WebSocketDisconnect:
        print("🔴 Cliente desconectado")
        active_connections.remove(websocket)

@app.get("/health")
async def health():
    return {"status": "ok"}
