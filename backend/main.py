# backend/main.py - Nexus AI Stream Backend (corrigido)
import datetime
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from starlette.websockets import WebSocketState

app = FastAPI()

# Armazena histórico e clientes conectados
HISTORY = []
CLIENTS = set()

@app.get("/")
async def home():
    """Página inicial do Nexus Stream."""
    html_content = """
    <html>
    <head>
        <title>Nexus Stream</title>
        <style>
            body { font-family: system-ui; background: #0f172a; color: white; text-align: center; padding-top: 60px; }
            h1 { color: #38bdf8; font-size: 2.5rem; }
            #status { color: #a5f3fc; margin-top: 20px; font-size: 1.2rem; }
        </style>
    </head>
    <body>
        <h1>🧠 Nexus Stream em Tempo Real</h1>
        <p id="status">Aguardando transmissão...</p>

        <script>
            const ws = new WebSocket("wss://" + window.location.host + "/ws/stream");
            ws.onopen = () => document.getElementById("status").innerText = "✅ Conectado. Aguardando dados...";
            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                if (data.type === "frame") {
                    document.getElementById("status").innerText = "📡 Recebendo stream em tempo real...";
                }
            };
            ws.onerror = () => document.getElementById("status").innerText = "⚠️ Erro no WebSocket";
            ws.onclose = () => document.getElementById("status").innerText = "❌ Conexão encerrada.";
        </script>
    </body>
    </html>
    """
    return HTMLResponse(html_content)

@app.websocket("/ws/stream")
async def websocket_endpoint(ws: WebSocket):
    """Recebe dados da extensão (frames base64)."""
    await ws.accept()
    CLIENTS.add(ws)
    try:
        while True:
            msg = await ws.receive_text()
            data = json.loads(msg)

            if data.get("type") == "frame":
                HISTORY.append({
                    "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                    "pair": data.get("pair", "UNKNOWN"),
                    "price": data.get("price", 0)
                })

                # Envia para todos os clientes conectados
                for client in CLIENTS.copy():
                    if client.application_state == WebSocketState.CONNECTED:
                        await client.send_text(json.dumps(data))
            else:
                await ws.send_text(json.dumps({"type": "ack"}))

    except WebSocketDisconnect:
        CLIENTS.remove(ws)
        print("Cliente desconectado do stream.")

@app.get("/health")
async def health():
    return {"status": "ok", "clients": len(CLIENTS), "history": len(HISTORY)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
