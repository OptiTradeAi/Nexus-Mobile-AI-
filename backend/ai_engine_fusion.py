import base64
import io
from datetime import datetime
from PIL import Image, ImageStat
import numpy as np

FRAME_LOG = []
SIGNAL_LOG = []
SIGNAL_THRESHOLD = 0.65

def analyze_frame(frame_b64: str, mime="image/webp", pair="AUTO"):
    try:
        img_bytes = base64.b64decode(frame_b64)
        img = Image.open(io.BytesIO(img_bytes)).convert("RGB")

        stat = ImageStat.Stat(img)
        brightness = float(np.mean(stat.mean))
        contrast = float(np.mean(stat.stddev))

        if contrast > 40 and brightness > 100:
            action = "CALL"
        elif contrast > 40:
            action = "PUT"
        else:
            action = "HOLD"

        confidence = min(0.99, contrast / 160)

        result = {
            "ok": True,
            "pair": pair,
            "brightness": brightness,
            "contrast": contrast,
            "suggested_action": action,
            "confidence": confidence,
            "time": datetime.now().isoformat()
        }

        FRAME_LOG.append(result)

        if action in ("CALL", "PUT") and confidence >= SIGNAL_THRESHOLD:
            SIGNAL_LOG.append(result)

        FRAME_LOG[:] = FRAME_LOG[-300:]
        SIGNAL_LOG[:] = SIGNAL_LOG[-300:]

        return result

    except Exception as e:
        return {"ok": False, "error": str(e)}

def get_logs():
    return {"frames": FRAME_LOG[-50:], "signals": SIGNAL_LOG[-50:]}
