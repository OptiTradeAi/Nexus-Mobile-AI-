# backend/ai_analyzer.py
import base64
import io
from PIL import Image
import random
import datetime

# placeholder analyzer: inspeciona frame bytes (jpeg) or candle JSON
# returns {"signal": "CALL"/"PUT"/None, "confidence": float}
def analyze_frame_base64(b64jpeg: str) -> dict:
    # Decodifica (exemplo, mas não faz processamento real)
    try:
        data = base64.b64decode(b64jpeg)
        img = Image.open(io.BytesIO(data))
        # placeholder: compute naive 'confidence' from image size
        w,h = img.size
        conf = min(0.95, 0.3 + (w*h)/1000000.0)
        # dummy random signal based on timestamp (replace with real model)
        rnd = random.random()
        signal = None
        if conf > 0.75 and rnd > 0.7:
            signal = "CALL" if rnd>0.85 else "PUT"
        return {"signal": signal, "confidence": float(round(conf, 3)), "timestamp": datetime.datetime.utcnow().isoformat()+"Z"}
    except Exception as e:
        return {"signal": None, "confidence": 0.0, "error": str(e)}

def analyze_candle_json(candle: dict) -> dict:
    # candle example: {"pair": "...", "open":..., "high":..., "low":..., "close":..., "timestamp": "..."}
    # Placeholder rule: if last candle close > open -> CALL with low confidence.
    try:
        o = float(candle.get("open", 0))
        c = float(candle.get("close", 0))
        conf = 0.5
        signal = None
        if c > o:
            signal = "CALL"
            conf = 0.6
        elif c < o:
            signal = "PUT"
            conf = 0.6
        else:
            signal = None
            conf = 0.3
        return {"signal": signal, "confidence": conf, "timestamp": candle.get("timestamp")}
    except Exception as e:
        return {"signal": None, "confidence": 0.0, "error": str(e)}
