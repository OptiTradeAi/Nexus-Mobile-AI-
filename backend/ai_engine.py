# backend/ai_engine.py
# Módulo de análise e geração de sinais do Nexus Mobile AI
# Inclui histórico, avaliação e envio antecipado de sinal (M5)

from datetime import datetime, timedelta
import pytz

TZ = pytz.timezone("America/Sao_Paulo")
HISTORY = []
SIGNALS = []
SIGNAL_THRESHOLD = 0.8  # probabilidade mínima para gerar sinal

def register_frame(frame_data: dict):
    """Registra cada frame (imagem ou dado recebido)"""
    frame_data["received_at"] = datetime.now(TZ).isoformat()
    HISTORY.append(frame_data)
    if len(HISTORY) > 100:
        HISTORY.pop(0)

def analyze_and_maybe_signal(frame_data: dict):
    """
    Análise simulada:
    - Avalia o par e candle
    - Se condições favoráveis: gera sinal antecipado (1 min antes da abertura do próximo candle M5)
    """
    try:
        now = datetime.now(TZ)
        pair = frame_data.get("pair", "DESCONHECIDO")
        close_price = frame_data.get("close", 0.0)
        prob = round(0.75 + (hash(pair + str(now.minute)) % 25) / 100, 2)  # probabilidade fake 75~99%
        direction = "CALL" if hash(pair + str(now.minute)) % 2 == 0 else "PUT"
        reason = "Engolfo de alta" if direction == "CALL" else "Fluxo vendedor"

        # Horário da próxima vela (M5)
        next_candle = (now + timedelta(minutes=5 - now.minute % 5)).replace(second=0, microsecond=0)
        signal_time = next_candle - timedelta(minutes=1)  # envia 1min antes da abertura

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
            print(f"🚀 Novo sinal gerado: {signal}")
            return signal
        else:
            print(f"❌ Probabilidade baixa ({prob}) para {pair}")
            return None

    except Exception as e:
        print(f"Erro na análise: {e}")
        return None

def evaluate_pending_signals():
    """Verifica sinais abertos e resultados fictícios"""
    now = datetime.now(TZ)
    results = []
    for s in SIGNALS:
        if "result" not in s:
            s["result"] = "WIN" if hash(s["pair"] + s["signal_time"]) % 3 != 0 else "LOSS"
            s["evaluated_at"] = now.strftime("%H:%M:%S")
            results.append(s)
    return results
