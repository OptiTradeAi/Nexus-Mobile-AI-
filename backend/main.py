# backend/main.py
# Nexus Mobile AI – backend principal (FastAPI + WebSocket)
# Corrigido e compatível com Render + comunicação com extensão da corretora

import json
import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.websockets import WebSocketState

# ✅ Importação corrigida (Render reconhece corretamente o módulo)
from backend.ai_analyzer import analyze_candles

app = FastAPI()

# Histórico de candles e sinais
CANDLES = []
SIGNALS = []
VIEWERS = set()

@app.get("/")
async def index():
    html = """
    <html>
        <head>
            <title>Nexus Mobile AI Stream</title>
            <style>
                body { background: #0a0a0a; color: #00e676; font-family: monospace; text-align: center; padding: 60px; }
                h1 { font-size: 32px; }
                .status { color: #fff; font-size: 18px; margin-top: 20px; }
                .dot { width: 14px; height: 14px; background: #00e676; border-radius: 50%; display: inline-block; margin-right: 8px; }
            </style>
        </head>
        <body>
            <h1>🧠 Nexus Mobile AI</h1>
            <div class="status"><span class="dot"></span> Conectado - aguardando stream...</div>
            <script>
                const ws = new WebSocket("wss://" + location.host + "/ws/viewer");
                ws.onmessage = (event) => {
                    const msg = JSON.parse(event.data);
                    if (msg.type === "candle") {
                        document.body.innerHTML += `<pre style='color:#00bcd4;'>📊 ${msg.data.pair} → ${msg.data.close}</pre>`;
                    }
                    if (msg.type === "signal") {
                        document.body.innerHTML += `<pre style='color:#ffc107;'>⚡ ${msg.data.pair} ${msg.data.direction} (${msg.data.confidence.toFixed(2)})</pre>`;
                    }
                };
            </script>
        </body>
    </html>
    """
    return HTMLResponse(html)


@app.get("/health")
async def health():
    return {"status": "ok", "candles": len(CANDLES), "signals": len(SIGNALS)}


@app.websocket("/ws/stream")
async def ws_stream(ws: WebSocket):
    """Recebe dados da extensão do navegador (HomeBroker)"""
    await ws.accept()
    print("🟢 Extensão conectada e enviando dados...")

    try:
        while True:
            message = await ws.receive_text()
            data = json.loads(message)

            # Armazena candle recebido
            CANDLES.append(data)
            if len(CANDLES) > 500:
                CANDLES.pop(0)

            print(f"📦 Recebido: {data}")

            # 🔍 Analisa candle e gera sinal (sem gale, timeframe M5)
            signal = analyze_candles(data)
            if signal:
                SIGNALS.append(signal)
                # Envia aos viewers conectados
                for viewer in VIEWERS:
                    if viewer.application_state == WebSocketState.CONNECTED:
                        await viewer.send_text(json.dumps({"type": "signal", "data": signal}))
    except WebSocketDisconnect:
        print("🔴 Extensão desconectada.")


@app.websocket("/ws/viewer")
async def ws_viewer(ws: WebSocket):
    """Visualizador (Render / Nexus Mobile AI interface)"""
    await ws.accept()
    VIEWERS.add(ws)
    print("👁️ Visualizador conectado...")

    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        VIEWERS.remove(ws)
        print("👁️ Visualizador desconectado.")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
