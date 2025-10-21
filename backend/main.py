# backend/main.py
import datetime
import json
import base64
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.websockets import WebSocketState
import os

app = FastAPI()
HISTORY = []  # each entry: {timestamp, source, confidence, result}
SIGNAL_THRESHOLD = 0.80

# Mount static folder (viewer.html)
static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/history")
async def get_history():
    return JSONResponse(HISTORY)

@app.get("/")
async def index():
    # serve viewer.html
    fp = os.path.join(static_dir, "viewer.html")
    if os.path.exists(fp):
        return FileResponse(fp, media_type="text/html")
    return HTMLResponse("<h1>Nexus Mobile AI - backend</h1><p>Servidor OK, mas viewer faltando.</p>")

@app.websocket("/ws/stream")
async def ws_stream(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            # Espera string JSON ou bytes.
            msg = await ws.receive_text()
            # cliente envia JSON: {"type":"frame","b64":"..."} ou {"type":"data","payload": {...}}
            try:
                data = json.loads(msg)
            except:
                await ws.send_text(json.dumps({"type":"error","reason":"invalid json"}))
                continue

            if data.get("type") == "frame":
                b64 = data.get("b64")
                # heurística de confiança (exemplo)
                conf = fake_confidence(len(b64) if b64 else 0)
                # registro opcional: só quando alta confiança
                if conf >= SIGNAL_THRESHOLD:
                    rec = {"timestamp": datetime.datetime.utcnow().isoformat()+"Z",
                           "source": "mobile_stream",
                           "confidence": conf,
                           "result": "PENDING"}
                    HISTORY.append(rec)
                    # envia notificação de sinal para cliente
                    try:
                        if ws.application_state == WebSocketState.CONNECTED:
                            await ws.send_text(json.dumps({"type":"signal","pair":rec["source"], "confidence":conf, "timestamp":rec["timestamp"]}))
                    except:
                        pass
                # ack
                await ws.send_text(json.dumps({"type":"ack","size": len(b64) if b64 else 0, "confidence": conf}))
            elif data.get("type") == "data":
                # dados DOM / json da extensão
                payload = data.get("payload", {})
                # aqui você pode salvar/analisar em ai_analyzer
                # por enquanto armazena no histórico breve
                rec = {"timestamp": datetime.datetime.utcnow().isoformat()+"Z",
                       "source": payload.get("source","dom"),
                       "confidence": payload.get("confidence",0.0),
                       "result":"DATA"}
                HISTORY.append(rec)
                await ws.send_text(json.dumps({"type":"ack-data","received": True}))
            else:
                await ws.send_text(json.dumps({"type":"error","reason":"unknown type"}))
    except WebSocketDisconnect:
        print("Cliente desconectado")
    except Exception as e:
        print("Erro ws:", e)

def fake_confidence(n:int)->float:
    # heurística simples
    if n > 200000: return 0.92
    if n > 50000: return 0.83
    if n > 15000: return 0.6
    return 0.4

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
