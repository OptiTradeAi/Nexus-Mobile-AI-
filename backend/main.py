import base64
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import os

app = FastAPI(title="Nexus Mobile AI")

# CORS (para a extensão se conectar)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Variáveis globais
active_viewers = []
last_frame = None


@app.get("/")
async def root():
    return {
        "status": "Nexus Mobile AI ativo",
        "viewer_url": "/viewer",
        "stream": "/ws/stream",
        "timezone": "America/Sao_Paulo"
    }


@app.get("/viewer", response_class=HTMLResponse)
async def get_viewer():
    """Carrega o visualizador HTML"""
    viewer_path = os.path.join(os.path.dirname(__file__), "viewer.html")
    if not os.path.exists(viewer_path):
        return JSONResponse({"error": "viewer.html não encontrado"}, status_code=404)
    with open(viewer_path, "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())


@app.websocket("/ws/stream")
async def websocket_stream(ws: WebSocket):
    """Recebe frames da extensão"""
    global last_frame
    await ws.accept()
    print("📡 Extensão conectada ao WS /stream")
    try:
        while True:
            data = await ws.receive_text()
            last_frame = data  # mantém último frame na memória
            for viewer in active_viewers:
                await viewer.send_text(data)
    except WebSocketDisconnect:
        print("⚠️ Extensão desconectada do /stream")


@app.websocket("/ws/viewer")
async def websocket_viewer(ws: WebSocket):
    """Envia frames para o navegador"""
    await ws.accept()
    active_viewers.append(ws)
    print("👁️ Viewer conectado ao WS /viewer")
    try:
        while True:
            await asyncio.sleep(1)
            if last_frame:
                await ws.send_text(last_frame)
    except WebSocketDisconnect:
        print("👁️ Viewer desconectado")
        active_viewers.remove(ws)


@app.get("/health")
async def health():
    return {"status": "ok"}
