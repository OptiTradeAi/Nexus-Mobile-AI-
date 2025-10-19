from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# 🔹 Libera conexões do navegador (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 🔹 Página inicial
@app.get("/")
async def home():
    return HTMLResponse("""
        <html>
        <head><title>Nexus Stream</title></head>
        <body style='font-family:Arial;text-align:center;margin-top:50px'>
            <h2>📡 Nexus Stream ativo</h2>
            <p>Aguardando dados da corretora...</p>
            <p>Status: <b style='color:orange'>Aguardando stream</b></p>
        </body>
        </html>
    """)

# 🔹 Endpoint WebSocket que recebe os frames da extensão
@app.websocket("/ws/stream")
async def stream_ws(websocket: WebSocket):
    await websocket.accept()
    print("🔌 Conexão recebida da extensão Nexus Stream")

    try:
        while True:
            data = await websocket.receive_json()
            print("📈 Frame recebido:", data.get("timestamp", "sem timestamp"))
            # Aqui futuramente você pode salvar, analisar ou repassar os dados
    except Exception as e:
        print("⚠️ Conexão encerrada:", e)
        await websocket.close()

# 🔹 Verificação rápida (health check)
@app.get("/health")
async def health():
    return {"status": "ok"}
