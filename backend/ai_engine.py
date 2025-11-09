# backend/ai_engine.py
from datetime import datetime, timedelta
import pytz
import random

TZ = pytz.timezone("America/Sao_Paulo")
HISTORY = []
SIGNALS = []
SIGNAL_THRESHOLD = 0.8  # probabilidade mínima para gerar sinal

def register_frame(frame_data: dict):
    """Registra frames recebidos via extensão."""
    frame_data["received_at"] = datetime.now(TZ).isoformat()
    HISTORY.append(frame_data)
    if len(HISTORY) > 200:
        HISTORY.pop(0)
    print(f"📥 Frame recebido e armazenado ({len(HISTORY)} total)")

def analyze_and_maybe_signal(frame_data: dict):
    """Análise simulada para gerar sinais M5."""
    try:
        now = datetime.now(TZ)
        pair = frame_data.get("pair", "DESCONHECIDO")
        prob = round(random.uniform(0.78, 0.96), 2)
        direction = random.choice(["CALL", "PUT"])
        reason = "Fluxo comprador" if direction == "CALL" else "Fluxo vendedor"

        # Envia sinal 1min antes da abertura do próximo candle M5
        next_candle = (now + timedelta(minutes=5 - now.minute % 5)).replace(second=0, microsecond=0)
        signal_time = next_candle - timedelta(minutes=1)

        signal = {
            "pair": pair,
            "direction": direction,
            "probability": prob,
            "reason": reason,
            "signal_time": signal_time.strftime("%H:%M:%S"),
            "sent_at": now.strftime("%H:%M:%S"),
            "timezone": "America/Sao_Paulo",
        }

        if prob >= SIGNAL_THRESHOLD:
            SIGNALS.append(signal)
            print(f"🚀 Novo sinal: {signal}")
            return signal
        else:
            print(f"❌ Probabilidade baixa ({prob}) - sem sinal")
            return None

    except Exception as e:
        print(f"⚠️ Erro na análise: {e}")
        return None

def evaluate_pending_signals():
    """Verifica e avalia sinais anteriores."""
    results = []
    now = datetime.now(TZ)
    for s in SIGNALS:
        if "result" not in s:
            s["result"] = random.choice(["WIN", "LOSS"])
            s["evaluated_at"] = now.strftime("%H:%M:%S")
            results.append(s)
    return results
