# backend/main.py
# Nexus Mobile AI - Servidor principal do agente inteligente com stream visual e análise
# Corrigido para Render + timezone de Brasília (UTC-3)

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from backend.ai_engine import (
    analyze_and_maybe_signal,
    register_frame,
    HISTORY,
    SIGNAL_THRESHOLD,
    evaluate_pending_signals,
    TZ
)
from datetime import datetime
import json

app = FastAPI(title="Nexus Mobile AI", version="3.2.0")

# 🔒 Permitir conexões de qualquer origem (Render + extensão)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Servir arquivos estáticos (viewer.html etc.)
app.mount("/static", StaticFiles(directory="backend/static"), name="static")

# Histórico em memória dos frames e conexões
active_connections = set()
frame_buffer = []

# 🩺 Rota de status
@app.get("/health")
async def health():
    now = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")
    return {"status": "ok", "time": now, "frames": len(frame_buffer), "connections": len(active_connections)}

# 🧠 Registro manual de frame (fallback POST)
@app.post("/frame")
async def register_from_post(payload: dict):
    try:
        register_frame(payload)
        result = analyze_and_maybe_signal(payload)
        return {"status": "ok", "received": True, "result": result}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

# 🎥 WebSocket principal: recebe imagens da extensão
@app.websocket("/ws")
async def websocket_stream(websocket: WebSocket):
    await websocket.accept()
    active_connections.add(websocket)
    print("🟢 Extensão conectada e enviando frames...")
    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)
            register_frame(payload)
            analyze_and_maybe_signal(payload)
            for viewer in list(active_connections):
                if viewer != websocket:
                    await viewer.send_text(json.dumps(payload))
    except WebSocketDisconnect:
        print("🔴 Extensão desconectada.")
        active_connections.remove(websocket)
    except Exception as e:
        print(f"⚠️ Erro no WebSocket: {e}")
        active_connections.remove(websocket)

# 👁️ WebSocket do visualizador (renderiza gráfico em tempo real)
@app.websocket("/ws/viewer")
async def websocket_viewer(websocket: WebSocket):
    await websocket.accept()
    active_connections.add(websocket)
    print("👁️ Visualizador conectado...")
    try:
        for frame in frame_buffer[-5:]:  # envia últimas 5 capturas
            await websocket.send_text(json.dumps(frame))
        while True:
            await websocket.receive_text()  # mantém conexão viva
    except WebSocketDisconnect:
        print("👁️ Visualizador desconectado.")
        active_connections.remove(websocket)

# 🧩 Avalia sinais pendentes (verificação periódica)
@app.get("/evaluate")
async def evaluate_signals():
    try:
        result = evaluate_pending_signals()
        return {"status": "ok", "evaluated": result}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

# ✅ Inicialização
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=10000, reload=True)
