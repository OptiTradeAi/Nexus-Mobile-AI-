import base64, io
from PIL import Image
import numpy as np
import cv2
import json
from datetime import datetime
import pytz

TZ = pytz.timezone("America/Sao_Paulo")

def decode_frame(b64data: str):
    try:
        img_bytes = base64.b64decode(b64data)
        img = Image.open(io.BytesIO(img_bytes))
        return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    except Exception as e:
        print("Erro ao decodificar frame:", e)
        return None

def detect_candles(frame):
    """
    Analisa o frame (gráfico) e retorna informações básicas detectadas visualmente.
    Esta função é simples, mas serve como base para depois aplicar aprendizado.
    """
    try:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 60, 160)
        # Contagem simples de blocos verticais (padrão de candles)
        cols = np.sum(edges, axis=0)
        activity = np.count_nonzero(cols > 50)
        return {
            "candles_detected": int(activity / 10),
            "timestamp": datetime.now(TZ).isoformat()
        }
    except Exception as e:
        return {"error": str(e)}

def analyze_frame(payload):
    """
    Recebe o payload da extensão (com frame + par + timeframe)
    e retorna dados de análise visual e numérica combinada.
    """
    try:
        frame_b64 = payload.get("data")
        pair = payload.get("pair", "UNKNOWN")
        frame = decode_frame(frame_b64)
        if frame is None:
            return {"error": "Frame inválido"}
        visual = detect_candles(frame)
        return {
            "pair": pair,
            "visual": visual,
            "ai_signal": "NEUTRAL",
            "confidence": 0.0
        }
    except Exception as e:
        return {"error": f"Erro análise: {e}"}
