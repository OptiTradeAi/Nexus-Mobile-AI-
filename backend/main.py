from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import base64

app = FastAPI()

# 🔹 Permite conexões externas
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

html = """
<!DOCTYPE html>
<html>
  <head>
    <meta charset="utf-8">
    <title>Nexus Stream ativo 🚀</title>
  </head>
  <body style="background-color:#111; color:white; font-family:sans-serif;">
    <h3>Nexus Stream ativo 🚀</h3>
    <p>Aguardando transmissão...</p>
    <img id="stream" style="width:100%; border:2px solid #333; margin-top:10px;">
    <script>
      const ws = new WebSocket("wss://" + location.host + "/ws/stream");
      const img = document.getElementById("stream");
      ws.onmessage = (event) => {
        img.src = "data:image/png;base64," + event.data;
      };
    </script>
  </body>
</html>
"""

@app.get("/")
async def get():
    return HTMLResponse(html)

@app.websocket("/ws/stream")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(data)
    except WebSocketDisconnect:
        pass
