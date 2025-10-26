from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# 🔓 Permitir acesso externo
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 📦 Armazenamento temporário das velas recebidas
candle_buffer = []

@app.get("/", response_class=HTMLResponse)
async def home():
    return """
    <html>
    <head><title>Nexus Stream</title></head>
    <body style="font-family:system-ui;background:#111;color:#0f0;text-align:center;">
        <h2>🔥 Nexus AI Stream Ativo</h2>
        <p>Aguardando dados da HomeBroker...</p>
    </body>
    </html>
    """

@app.post("/api/candles")
async def receive_candle(request: Request):
    try:
        data = await request.json()
        candle_buffer.append(data)
        print(f"📩 Recebido: {data}")
        return JSONResponse({"status": "ok", "message": "Candle recebido"})
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=400)

@app.get("/api/candles")
async def get_candles():
    return {"candles": candle_buffer[-50:]}  # últimas 50
