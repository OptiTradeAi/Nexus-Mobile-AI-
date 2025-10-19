from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import asyncio, io, base64

app = FastAPI()

# Permite conexões do navegador (Tampermonkey)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

latest_frame = None

@app.get("/")
async def home():
    return HTMLResponse("<h2>Nexus Stream ativo 🚀</h2><p>Aguardando transmissão...</p>")

@app.websocket("/ws/stream")
async def stream(ws: WebSocket):
    global latest_frame
    await ws.accept()
    try:
        while True:
            data = await ws.receive_bytes()
            latest_frame = base64.b64encode(data).decode("utf-8")
            await ws.send_text("Frame recebido ✅")
    except WebSocketDisconnect:
        print("Extensão desconectada.")

@app.get("/stream")
async def get_frame():
    if latest_frame:
        html = f"""
        <html>
        <head><title>Nexus Viewer</title></head>
        <body style='background:black;margin:0'>
          <img src='data:image/jpeg;base64,{latest_frame}' style='width:100%;height:100%;object-fit:contain'>
          <script>
            setTimeout(()=>location.reload(),500);
          </script>
        </body>
        </html>"""
        return HTMLResponse(html)
    return HTMLResponse("<h2 style='color:red'>Sem imagem recebida</h2>")
