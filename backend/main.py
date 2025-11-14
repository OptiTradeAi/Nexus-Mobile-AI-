# backend/main.py
"""
Nexus Mobile AI Stream Server
Recebe frames + meta via WebSocket, analisa com ai_engine_fusion e transmite para viewers.
"""

# --- DEBUG IMPORT HELPER (opcional, mas ajuda a diagnosticar erros de import) ---
import os, sys, logging
from pathlib import Path
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("startup")

log.info("=== Nexus Mobile AI Startup Debug Info ===")
log.info(f"CWD: {os.getcwd()}")
log.info(f"PYTHONPATH (first 10): {sys.path[:10]}")

# tenta garantir que backend está no sys.path
backend_path = Path(__file__).parent.resolve()
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))
    log.info(f"Added to sys.path: {backend_path}")

# tenta importar ai_engine_fusion com fallbacks
try:
    from backend.ai_engine_fusion import analyze_frame_with_meta
    log.info("✅ Import backend.ai_engine_fusion OK")
except ImportError as e:
    log.error("❌ Import backend.ai_engine_fusion FAILED")
    log.error("Traceback:", exc_info=True)
    raise e

# --- Imports principais ---
from fastapi import FastAPI, WebSocket, Query, Body
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import asyncio, json, base64, os
from datetime import datetime
import pytz

app = FastAPI(title="Nexus Mobile AI Stream Server")
TZ = pytz.timezone("America/Sao_Paulo")

# CORS - em produção restrinja allow_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve arquivos estáticos (viewer.html etc.)
STATIC_DIR = "backend/static"
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
async def root():
    return {
        "status": "Nexus Mobile AI ativo",
        "viewer_url": "/static/viewer.html",
        "stream_ws": "/ws/stream",
        "viewer_ws": "/ws/viewer"
    }

@app.get("/health")
async def health():
    return {"status": "ok", "time": datetime.now(TZ).isoformat()}

# --- WebSockets ---
stream_clients = set()
viewer_clients = set()
DEBUG_SAVE_PATH = os.path.join(STATIC_DIR, "latest_frame.webp")

@app.websocket("/ws/stream")
async def websocket_stream_endpoint(websocket: WebSocket, token: str = Query(None)):
    await websocket.accept()
    stream_clients.add(websocket)
    client_addr = getattr(websocket.client, "host", "unknown")
    print(f"🟢 Streamer conectado: {client_addr}")

    try:
        while True:
            msg = await websocket.receive()
            frame_b64 = None
            mime = "image/webp"
            pair = "AUTO"
            payload = None

            if "text" in msg and msg["text"]:
                try:
                    payload = json.loads(msg["text"])
                    if payload.get("type") == "frame" and payload.get("data"):
                        frame_b64 = payload.get("data")
                        mime = payload.get("mime", mime)
                        pair = payload.get("pair", pair)
                        print(f"📥 Frame recebido (texto) pair={pair} size={len(frame_b64)}")
                except Exception as e:
                    print("⚠️ JSON inválido recebido no stream:", e)
                    continue

            elif "bytes" in msg and msg["bytes"]:
                try:
                    frame_bytes = msg["bytes"]
                    frame_b64 = base64.b64encode(frame_bytes).decode("utf-8")
                    mime = "image/webp"
                    print(f"📥 Frame recebido (bytes) size={len(frame_bytes)}")
                    payload = {"type": "frame", "data": frame_b64, "mime": mime, "pair": pair, "timestamp": datetime.now(TZ).isoformat()}
                except Exception as e:
                    print("⚠️ Erro ao tratar bytes do stream:", e)
                    continue

            if not frame_b64:
                await asyncio.sleep(0.001)
                continue

            # Salva frame para debug
            try:
                with open(DEBUG_SAVE_PATH, "wb") as f:
                    f.write(base64.b64decode(frame_b64))
                print(f"💾 Debug: frame salvo em {DEBUG_SAVE_PATH}")
            except Exception as e:
                print("⚠️ Falha ao salvar debug frame:", e)

            # Análise com engine fusion
            try:
                if payload is None:
                    payload = {"type": "frame", "data": frame_b64, "mime": mime, "pair": pair, "timestamp": datetime.now(TZ).isoformat()}
                analysis_result = analyze_frame_with_meta(payload)
            except Exception as e:
                analysis_result = {"ok": False, "error": str(e)}
                print("⚠️ analyze_frame_with_meta gerou erro:", e)

            # Monta pacote para viewers
            packet = {
                "type": "frame",
                "data": frame_b64,
                "mime": mime,
                "pair": pair,
                "timestamp": payload.get("timestamp", datetime.now(TZ).isoformat()),
                "analysis": analysis_result.get("analysis") if isinstance(analysis_result, dict) else analysis_result
            }

            # Broadcast para viewers
            for v in list(viewer_clients):
                try:
                    await v.send_json(packet)
                except Exception as e:
                    print("🔴 Erro enviando para viewer, removendo:", e)
                    try:
                        viewer_clients.remove(v)
                    except:
                        pass

            await asyncio.sleep(0.001)

    except Exception as e:
        print("❌ Erro no websocket stream:", e)
    finally:
        try:
            stream_clients.remove(websocket)
        except:
            pass

@app.websocket("/ws/viewer")
async def websocket_viewer_endpoint(websocket: WebSocket):
    await websocket.accept()
    viewer_clients.add(websocket)
    client_addr = getattr(websocket.client, "host", "unknown")
    print(f"🟢 Viewer conectado: {client_addr}")

    try:
        while True:
            try:
                msg = await websocket.receive_text()
                try:
                    j = json.loads(msg)
                    if j.get("type") == "command_to_stream":
                        cmd_payload = j.get("command", {})
                        for s in list(stream_clients):
                            try:
                                await s.send_text(json.dumps(cmd_payload))
                            except Exception:
                                try: stream_clients.remove(s)
                                except: pass
                except Exception:
                    pass
            except Exception:
                await asyncio.sleep(0.1)
    except Exception as e:
        print("❌ Erro no websocket viewer:", e)
    finally:
        try:
            viewer_clients.remove(websocket)
        except:
            pass

@app.get("/viewer")
async def get_viewer_page():
    p = os.path.join(STATIC_DIR, "viewer.html")
    if os.path.isfile(p):
        return FileResponse(p, media_type="text/html")
    return JSONResponse({"error": "viewer.html não encontrado"}, status_code=404)

# --- Controle via HTTP ---
@app.post("/control/pairs")
async def control_pairs(body: dict = Body(...)):
    pairs = body.get("pairs", [])
    interval = int(body.get("interval", 2000))
    cmd = {"type": "command", "cmd": "set_pairs", "pairs": pairs, "interval": interval}
    sent = 0
    for s in list(stream_clients):
        try:
            await s.send_text(json.dumps(cmd))
            sent += 1
        except Exception:
            try: stream_clients.remove(s)
            except: pass
    return {"sent_to_streamers": sent, "pairs_count": len(pairs)}

@app.post("/control/command")
async def control_command(body: dict = Body(...)):
    cmd_body = body.copy()
    cmd = {"type": "command", "cmd": cmd_body.get("cmd"), **({k:v for k,v in cmd_body.items() if k!="cmd"})}
    sent = 0
    for s in list(stream_clients):
        try:
            await s.send_text(json.dumps(cmd))
            sent += 1
        except Exception:
            try: stream_clients.remove(s)
            except: pass
    return {"sent": sent, "cmd": cmd}
