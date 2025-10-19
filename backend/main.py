from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI()

# Libera acesso de qualquer origem (Edge, Render, etc.)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

connected_clients = set()

@app.get("/")
async def home():
    html = """
    <html>
    <head>
    <title>Nexus Mobile AI — Stream</title>
    <style>
      body { background:#0d1117; color:white; text-align:center; font-family:Arial; margin:0; }
      h1 { color:#00ffcc; margin:20px 0; }
      img { max-width:95vw; border:2px solid #00ffcc; border-radius:12px; margin-top:20px; }
      #status { margin-top:15px; font-size:18px; }
    </style>
    </head>
    <body>
      <h1>✅ Nexus Mobile AI — Servidor Online</h1>
      <p>Aguardando frames do Tampermonkey...</p>
      <div id="status">Status: 🔴 Desconectado</div>
      <img id="frame" src="" alt="Espelhamento aguardando..." />
      <script>
        const ws = new WebSocket(`wss://${location.host}/ws/stream`);
        const status = document.getElementById("status");
        const img = document.getElementById("frame");

        ws.onopen = () => status.textContent = "Status: 🟢 Conectado";
        ws.onclose = () => status.textContent = "Status: 🔴 Desconectado";
        ws.onmessage = (event) => {
          const data = JSON.parse(event.data);
          if (data.frame) img.src = data.frame;
        };
      </script>
    </body>
    </html>
    """
    return HTMLResponse(html)

@app.websocket("/ws/stream")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.add(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Reenvia a todos conectados (exibição ao vivo)
            for client in list(connected_clients):
                try:
                    await client.send_text(data)
                except:
                    connected_clients.remove(client)
    except WebSocketDisconnect:
        connected_clients.remove(websocket)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=10000)
