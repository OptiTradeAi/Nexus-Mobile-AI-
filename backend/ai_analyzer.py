# backend/ai_analyzer.py
# Módulo inicial de análise (ponto de partida)
def analyze_frame_b64(b64str):
    # placeholder simples: return fake_confidence
    size = len(b64str) if b64str else 0
    if size > 200000: return {"confidence":0.92, "signal":"PENDING"}
    if size > 50000: return {"confidence":0.82, "signal":"PENDING"}
    return {"confidence":0.4, "signal":None}
