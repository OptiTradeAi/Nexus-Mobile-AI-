# backend/main.py
# Nexus Mobile AI – backend principal (FastAPI + WebSocket)
# Compatível com Render + retransmissão de candles para viewer

import json
from typing import List, Dict, Any
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from starlette.websockets import WebSocketState

from backend.ai_analyzer import analyze_candles  # analyze_candles(history, current) -> dict

app = FastAPI()

# Histórico de candles e sinais
CANDLES: List[Dict[str, Any]] = []
SIGNALS: List[Dict[str, Any]] = []
VIEWERS: set[WebSocket] = set()

@app.get("/")
async def index():
    # Viewer simples que conecta em /ws/viewer e exibe candle/sinal
    html = """
    <html>
        <head>
            <title>Nexus Mobile AI Stream</title>
            <meta name="viewport" content="width=device-width, initial-scale=1" />
            <style>
                body { background: #0a0a0a; color: #e2e8f0; font-family: system-ui, -apple-system, Roboto; padding: 16px; }
                h1 { color: #00e676; margin: 0 0 6px 0; }
                .muted { color: #94a3b8; }
                .line { border-bottom: 1px solid rgba(255,255,255,0.06); margin: 10px 0; }
                .candle { color:#38bdf8; font-family: ui-monospace, SFMono-Regular, Menlo; white-space: pre; }
                .signal { padding:8px; border-radius:6px; margin: 8px 0; }
                .CALL { background: linear-gradient(90deg,#052e11,#064e2a); color:#a7f3d0;}
                .PUT { background: linear-gradient(90deg,#2b021e,#4b002f); color:#ffccd5;}
                .NONE { background: rgba(255,255,255,0.05); color:#cbd5e1; }
                #candles { max-height: 40vh; overflow: auto; background:#0b0f1a; padding:8px; border-radius:8px; }
            </style>
        </head>
        <body>
            <h1>🧠 Nexus Mobile AI</h1>
            <div id="status" class="muted">Conectando...</div>
            <div class="line"></div>

            <h3>Candles (tempo real)</h3>
            <div id="candles"></div>

            <h3 style="margin-top:16px;">Sinais</h3>
            <div id="signals"></div>

            <script>
                const statusEl = document.getElementById("status");
                const candlesEl = document.getElementById("candles");
                const signalsEl = document.getElementById("signals");
                const ws = new WebSocket((location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws/viewer");

                function pushCandle(c){
                    const el = document.createElement("div");
                    el.className = "candle";
                    el.textContent = `${c.timestamp} | ${c.pair} | O:${c.open} H:${c.high} L:${c.low} C:${c.close}`;
                    candlesEl.appendChild(el);
                    while (candlesEl.children.length > 120) candlesEl.removeChild(candlesEl.firstChild);
                    candlesEl.scrollTop = candlesEl.scrollHeight;
                }

                function pushSignal(s){
                    const el = document.createElement("div");
                    el.className = "signal " + (s.decision || "NONE");
                    el.innerHTML = \`<strong>\${s.decision}</strong> — \${s.pair || ''} — conf: \${s.confidence} — lead: \${s.lead_time_seconds}s
                    <div class="muted">\${s.explanation || ""}</div>\`;
                    signalsEl.prepend(el);
                    if (signalsEl.children.length > 50) signalsEl.removeChild(signalsEl.lastChild);
                }

                ws.onopen = () => { statusEl.textContent = "Conectado ao viewer"; statusEl.style.color = "#7ee787"; };
                ws.onclose = () => { statusEl.textContent = "Desconectado. Reconectando..."; statusEl.style.color = "#ffb4b4"; setTimeout(()=>location.reload(), 3000); };
                ws.onerror = () => { statusEl.textContent = "Erro de conexão"; statusEl.style.color = "#f97316"; };

                ws.onmessage = (e) => {
                    try {
                        const msg = JSON.parse(e.data);
                        if (msg.type === "candle") pushCandle(msg.data);
                        else if (msg.type === "signal") pushSignal(msg.data);
                        else if (msg.type === "status") statusEl.textContent = msg.msg || "status";
                    } catch {}
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
    """Recebe dados da extensão/userscript"""
    await ws.accept()
    print("🟢 Produtor conectado (stream de candles)")

    try:
        while True:
            raw = await ws.receive_text()
            data = json.loads(raw)

            # Aceita tanto {type:'candle', data:{...}} quanto candle cru
            if isinstance(data, dict) and data.get("type") == "candle" and "data" in data:
                candle = data["data"]
            else:
                candle = data

            # Sanidade mínima
            if not isinstance(candle, dict) or "timestamp" not in candle or "close" not in candle:
                continue

            CANDLES.append(candle)
            if len(CANDLES) > 1000:
                CANDLES.pop(0)

            # Reenvia candle ao viewer (visual imediato)
            for v in list(VIEWERS):
                if v.application_state == WebSocketState.CONNECTED:
                    await v.send_text(json.dumps({"type": "candle", "data": candle}))

            # Análise e possível sinal
            try:
                signal = analyze_candles(CANDLES[:-1], candle)  # (history, current)
            except TypeError:
                # Compatibilidade caso sua versão aceite 1 arg
                signal = analyze_candles(CANDLES)

            if signal and isinstance(signal, dict) and signal.get("send"):
                payload = {
                    "pair": candle.get("pair", "UNK"),
                    "timestamp": candle.get("timestamp"),
                    **signal
                }
                SIGNALS.append(payload)
                # difunde sinal
                for v in list(VIEWERS):
                    if v.application_state == WebSocketState.CONNECTED:
                        await v.send_text(json.dumps({"type": "signal", "data": payload}))
    except WebSocketDisconnect:
        print("🔴 Produtor desconectado.")

@app.websocket("/ws/viewer")
async def ws_viewer(ws: WebSocket):
    await ws.accept()
    VIEWERS.add(ws)
    print("👁️ Viewer conectado")

    try:
        while True:
            # Apenas mantém a conexão viva (poderia aceitar pings no futuro)
            await ws.receive_text()
    except WebSocketDisconnect:
        VIEWERS.discard(ws)
        print("👁️ Viewer desconectado")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
