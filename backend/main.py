from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import json
import datetime

app = FastAPI()

# Permitir acesso da extensão (Edge, Chrome, etc)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Variável para armazenar o último frame recebido
last_frame_data = None


@app.get("/")
async def root():
    html_content = """
    <html>
        <head>
            <title>Nexus Stream</title>
            <style>
                body { 
                    background-color: #0d1117; 
                    color: #e6edf3; 
                    font-family: Arial; 
                    text-align: center; 
                    padding-top: 20vh;
                }
                h1 { font-size: 2em; margin-bottom: 10px; }
                p { color: #8b949e; }
            </style>
        </head>
        <body>
            <h1>✅ Nexus Mobile AI — Servidor Online</h1>
            <p>Aguardando conexão da extensão Tampermonkey...</p>
            <p>Endpoint WS: <b>/ws/stream</b></p>
        </body>
    </html>
    """
    return HTMLResponse(content=html_content, status_code=200)


@app.websocket("/ws/stream")
async def websocket_endpoint(websocket: WebSocket):
    """
    Este endpoint recebe dados em tempo real da extensão Nexus Stream.
    A extensão envia capturas (frames) e dados DOM da corretora.
    """
    await websocket.accept()
    print("🔌 Conexão recebida da extensão Nexus Stream")

    global last_frame_data

    try:
        while True:
            data = await websocket.receive_text()

            try:
                parsed = json.loads(data)
                timestamp = parsed.get("timestamp", datetime.datetime.now().isoformat())
                last_frame_data = parsed

                print(f"📈 Frame recebido às {timestamp}")
            except Exception as e:
                print("⚠️ Erro ao processar dado recebido:", e)

    except WebSocketDisconnect:
        print("❌ Extensão Nexus Stream desconectada.")
    except Exception as e:
        print("⚠️ Erro inesperado:", e)


@app.get("/last_frame")
async def get_last_frame():
    """
    Endpoint auxiliar para testar se o backend está recebendo dados.
    Retorna o último frame de dados recebido da extensão.
    """
    if last_frame_data:
        return {"status": "ok", "last_frame": last_frame_data}
    else:
        return {"status": "waiting", "message": "Nenhum frame recebido ainda."}
