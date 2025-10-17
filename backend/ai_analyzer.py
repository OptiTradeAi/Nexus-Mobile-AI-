# backend/ai_analyzer.py
# Simple analyzer heuristics (placeholder). Expand with ML model later.

import base64
import json
import numpy as np
from PIL import Image
import io

def detect_timeframe(dom: dict) -> str:
    """
    Try to detect timeframe from DOM (example selectors must be provided by client).
    dom: optional dict with keys captured by extension: {timeframe: '1', ...}
    """
    if not dom:
        return "unknown"
    tf = dom.get("timeframe") or dom.get("tf") or dom.get("chart_timeframe")
    if tf:
        return str(tf)
    return "unknown"

def compute_confidence(frame_bytes: bytes | None, dom: dict | None) -> float:
    """
    Quick heuristic:
    - If large frame (bytes) => more confident (we have real image)
    - If DOM has price and volume and timeframe => increase confidence
    Returns float 0..1
    """
    conf = 0.0
    try:
        if frame_bytes:
            # size heuristic
            n = len(frame_bytes)
            if n > 200_000:
                conf += 0.5
            elif n > 50_000:
                conf += 0.3
            elif n > 10_000:
                conf += 0.15
            else:
                conf += 0.05
            # visual feature: detect high-contrast (quick)
            try:
                img = Image.open(io.BytesIO(frame_bytes)).convert("L").resize((64,64))
                arr = np.array(img).astype(float)
                std = float(arr.std())
                if std > 40:
                    conf += 0.25
                elif std > 20:
                    conf += 0.12
            except Exception:
                pass
        # DOM contributions
        if dom:
            if dom.get("price") is not None:
                conf += 0.1
            if dom.get("volume") is not None:
                conf += 0.05
            if dom.get("timeframe"):
                conf += 0.05
        # clamp
        if conf > 1.0:
            conf = 1.0
        return round(float(conf), 3)
    except Exception:
        return 0.0

# Placeholder: this module should be replaced by a real ML / heuristic system.
# Keep these functions simple so they run fast in real time.
