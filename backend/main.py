# backend/main.py
# Nexus Mobile AI – backend principal (FastAPI + WebSocket)
# Compatível com Render + retransmissão de candles para viewer
# Suporta múltiplos pares simultaneamente + fuso horário correto

import json
from typing import Dict, Any, List
from collections import defaultdict, deque
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from starlette.websockets import WebSocketState

from backend.ai_analyzer import analyze_candles, next_candle_open_from_iso

app = FastAPI()

# Histórico separado por par (máx 1000 candles por par)
CANDLES_BY_PAIR: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
SIGNALS: List[Dict[str, Any]] = []
VIEWERS: set[WebSocket] = set()

def _normalize_pair(name: str) -> str:
    """Normaliza o nome do par: capitaliza e mantém (OTC) apenas uma vez."""
    if not name:
        return "UNKNOWN"
    s = " ".join(str(name).split()).strip()
    has_otc = "(otc" in s.lower()
    base = s.replace("(OTC)", "").replace("(otc)", "").strip()
    base = " ".join([w if w.isupper() else w.capitalize() for w in base.split(" ")])
    return f"{base} (OTC)" if has_otc else base

@app.get("/")
async def index():
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
                .candle { color:#38bdf8; font-family: ui-monospace, SFMono-Regular, Menlo; white-space: pre; font-size: 11px; }
                .signal { padding:10px; border-radius:8px; margin: 10px 0; }
                .CALL { background: linear-gradient(90deg,#052e11,#064e2a); color:#a7f3d0;}
                .PUT  { background: linear-gradient(90deg,#2b021e,#4b002f); color:#ffccd5;}
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

                // Força fuso horário de Brasília (UTC-3)
                function fmtTime(tsIso) {
                    try {
                        const d = new Date(tsIso);
                        // Opção 1: força America/Sao_Paulo
                        return d.toLocaleTimeString('pt-BR', { 
                            timeZone: 'America/Sao_Paulo',
                            hour: '2-digit', 
                            minute: '2-digit', 
                            second: '2-digit' 
                        });
                    } catch {
                        return tsIso || '';
                    }
                }

                function fmtPct(confFloat) {
                    if (typeof confFloat !== 'number') return '';
                    return (confFloat * 100).toFixed(2) + '%';
                }

                function pushCandle(c){
                    const el = document.createElement("div");
                    el.className = "candle";
                    el.textContent = `${c.timestamp} | ${c.pair} | O:${c.open} H:${c.high} L:${c.low} C:${c.close}`;
                    candlesEl.appendChild(el);
                    while (candlesEl.children.length > 120) candlesEl.removeChild(candlesEl.firstChild);
                    candlesEl.scrollTop = candlesEl.scrollHeight;
                }

                function pushSignal(s) {
                    const decision = s.decision || 'NONE';
                    const pair = s.pair || '';
                    const confPct = s.confidence_pct || fmtPct(s.confidence);
                    const entryTime = fmtTime(s.timestamp);
                    const lead = (typeof s.lead_time_seconds === 'number') ? s.lead_time_seconds : '';

                    const el = document.createElement("div");
                    el.className = "signal " + decision;
                    el.innerHTML = `
                      <div style="display:flex;justify-content:space-between;align-items:center;gap:8px;">
                        <div>
                          <strong style="letter-spacing:0.5px;">${decision}</strong>
                          <span style="opacity:.9"> — ${pair}</span>
                        </div>
                        <div class="muted" style="font-variant-numeric: tabular-nums;">
                          conf: <strong>${confPct}</strong>
                        </div>
                      </div>
                      <div class="muted" style="margin-top:4px; font-variant-numeric: tabular-nums;">
                        entrada: <strong>${entryTime}</strong> (próx. vela M5) — lead: ${lead}s
                      </div>
                      ${s.explanation ? `<div class="muted" style="margin-top:6px;">${s.explanation}</div>` : ''}
                    `;
                    signalsEl.prepend(el);
                    if (signalsEl.children.length > 50) signalsEl.removeChild(signalsEl.lastChild);
                }

                ws.onopen  = () => { statusEl.textContent = "Conectado ao viewer"; statusEl.style.color = "#7ee787"; };
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

@app.websocket("/ws/stream")
async def ws_stream(ws: WebSocket):
    await ws.accept()
    print("🟢 Produtor conectado (stream de candles)")
    try:
        while True:
            raw = await ws.receive_text()
            data = json.loads(raw)

            # Aceita {type:'candle',data:{...}} ou candle cru
            if isinstance(data, dict) and data.get("type") == "candle" and "data" in data:
                candle = data["data"]
            else:
                candle = data

            if not isinstance(candle, dict) or "timestamp" not in candle or "close" not in candle:
                continue

            # Normaliza o par
            pair_raw = candle.get("pair", "UNKNOWN")
            pair_norm = _normalize_pair(pair_raw)
            candle["pair"] = pair_norm

            # Armazena no histórico SEPARADO por par
            CANDLES_BY_PAIR[pair_norm].append(candle)

            # Difunde candle imediatamente para o viewer
            for v in list(VIEWERS):
                if v.application_state == WebSocketState.CONNECTED:
                    await v.send_text(json.dumps({"type": "candle", "data": candle}))

            # Análise usando APENAS o histórico deste par
            history = list(CANDLES_BY_PAIR[pair_norm])[:-1]  # todos menos o atual
            try:
                signal = analyze_candles(history, candle)
            except TypeError:
                # fallback se analyze_candles aceitar só 1 arg
                signal = analyze_candles(list(CANDLES_BY_PAIR[pair_norm]))

            if signal and isinstance(signal, dict) and signal.get("send"):
                # Próxima abertura da vela M5 (horário de ENTRADA)
                try:
                    entry_dt = next_candle_open_from_iso(candle.get("timestamp"))
                    entry_iso = entry_dt.isoformat()
                except Exception:
                    entry_iso = candle.get("timestamp")

                # Garante campos padronizados no payload do sinal
                payload = {
                    "pair": pair_norm,
                    "decision": signal.get("decision", "NONE"),
                    "confidence": float(signal.get("confidence", 0.0)),
                    "confidence_pct": f"{float(signal.get('confidence', 0.0))*100:.2f}%",
                    "lead_time_seconds": int(signal.get("lead_time_seconds", 30)),
                    "timestamp": entry_iso,  # hora da ENTRADA (próxima vela M5)
                    "explanation": signal.get("explanation", "")
                }

                SIGNALS.append(payload)
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
            await ws.receive_text()  # mantém a conexão
    except WebSocketDisconnect:
        VIEWERS.discard(ws)
        print("👁️ Viewer desconectado")

@app.get("/health")
async def health():
    total_candles = sum(len(q) for q in CANDLES_BY_PAIR.values())
    return {
        "status": "ok", 
        "pairs": len(CANDLES_BY_PAIR),
        "candles": total_candles, 
        "signals": len(SIGNALS)
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
