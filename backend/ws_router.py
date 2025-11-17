import json
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from datetime import datetime
import pytz

router = APIRouter()
TZ = pytz.timezone("America/Sao_Paulo")

stream_clients = set()
viewer_clients = set()

@router.websocket("/ws/stream")
async def websocket_stream_endpoint(websocket: WebSocket):
    await websocket.accept()
    stream_clients.add(websocket)
    client_addr = getattr(websocket.client, "host", "unknown")
    print(f"🟢 Streamer conectado: {client_addr}")

    try:
        while True:
            msg = await websocket.receive_text()
            try:
                payload = json.loads(msg)
            except:
                continue

            # Aqui você pode tratar os frames e sinais recebidos
            # Por exemplo, encaminhar para viewers, analisar, etc.

            # Exemplo simples: encaminhar para viewers
            for v in list(viewer_clients):
                try:
                    await v.send_text(msg)
                except:
                    viewer_clients.remove(v)

    except WebSocketDisconnect:
        stream_clients.remove(websocket)
        print(f"🔴 Streamer desconectado: {client_addr}")

@router.websocket("/ws/viewer")
async def websocket_viewer_endpoint(websocket: WebSocket):
    await websocket.accept()
    viewer_clients.add(websocket)
    client_addr = getattr(websocket.client, "host", "unknown")
    print(f"🟢 Viewer conectado: {client_addr}")

    try:
        while True:
            await asyncio.sleep(0.1)
    except WebSocketDisconnect:
        viewer_clients.remove(websocket)
        print(f"🔴 Viewer desconectado: {client_addr}")
