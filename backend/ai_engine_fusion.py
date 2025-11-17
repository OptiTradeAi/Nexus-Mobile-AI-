import pytz
from datetime import datetime, timedelta
import numpy as np

BR_TZ = pytz.timezone("America/Sao_Paulo")

# Histórico e estado
active_operation = None  # {"pair": str, "entry_time": datetime, "direction": str}
blocked_pairs = {}  # {pair: unblock_time}
history = []  # lista de dicts com entradas e resultados

# Parâmetros
CANDLE_DURATION = timedelta(minutes=5)
BLOCK_DURATION = CANDLE_DURATION * 3  # 3 candles bloqueados
SIGNAL_ADVANCE = timedelta(minutes=1)  # sinal 1 min antes do candle

# Funções auxiliares para indicadores (exemplo simplificado)
def calculate_rsi(prices, period=14):
    deltas = np.diff(prices)
    seed = deltas[:period]
    up = seed[seed >= 0].sum() / period
    down = -seed[seed < 0].sum() / period
    rs = up / down if down != 0 else 0
    rsi = 100 - 100 / (1 + rs)
    return rsi

def calculate_ema(prices, period=20):
    weights = np.exp(np.linspace(-1., 0., period))
    weights /= weights.sum()
    a = np.convolve(prices, weights, mode='full')[:len(prices)]
    a[:period] = a[period]
    return a

# Função principal de análise
def analyze_pairs(pairs_data, current_time):
    """
    pairs_data: dict {pair: {"candles": [...], "volume": [...], "indicators": {...}}}
    current_time: datetime em BR_TZ
    """
    global active_operation, blocked_pairs, history

    # Limpa pares bloqueados expirados
    for pair in list(blocked_pairs.keys()):
        if blocked_pairs[pair] <= current_time:
            del blocked_pairs[pair]

    # Se já tem operação ativa, aguarda fechamento
    if active_operation:
        op = active_operation
        # Verifica se candle atual passou do tempo de entrada + 5 min
        if current_time >= op["entry_time"] + CANDLE_DURATION:
            # Aqui você deve receber resultado real (WIN/LOSS) e atualizar histórico
            # Para exemplo, vamos simular resultado aleatório
            import random
            result = random.choice(["WIN", "LOSS"])
            op["result"] = result
            history.append(op)
            # Bloqueia o par por 3 candles
            blocked_pairs[op["pair"]] = current_time + BLOCK_DURATION
            print(f"Operação finalizada: {op['pair']} {op['direction']} {result}")
            active_operation = None
        else:
            # Ainda aguardando fechamento
            return None

    # Analisar todos os pares livres
    candidates = []
    for pair, data in pairs_data.items():
        if pair in blocked_pairs:
            continue  # par bloqueado

        candles = data.get("candles", [])
        if len(candles) < 15:
            continue  # dados insuficientes

        # Exemplo simplificado de cálculo de indicadores
        close_prices = [c["close"] for c in candles]
        rsi = calculate_rsi(close_prices[-15:])
        ema20 = calculate_ema(close_prices, 20)[-1]
        ema50 = calculate_ema(close_prices, 50)[-1]

        # Confluências
        confluences = []

        # RSI extremo
        if rsi < 30:
            confluences.append("RSI Oversold")
        elif rsi > 70:
            confluences.append("RSI Overbought")

        # EMA tendência
        if ema20 > ema50:
            trend = "CALL"
            confluences.append("Tendência de alta")
        else:
            trend = "PUT"
            confluences.append("Tendência de baixa")

        # Padrão candle (exemplo: pavio longo)
        last_candle = candles[-1]
        body = abs(last_candle["close"] - last_candle["open"])
        candle_range = last_candle["high"] - last_candle["low"]
        lower_wick = last_candle["open"] - last_candle["low"] if last_candle["close"] > last_candle["open"] else last_candle["close"] - last_candle["low"]
        upper_wick = last_candle["high"] - last_candle["close"] if last_candle["close"] > last_candle["open"] else last_candle["high"] - last_candle["open"]

        if trend == "CALL" and lower_wick > body * 2:
            confluences.append("Pavio inferior longo")
        elif trend == "PUT" and upper_wick > body * 2:
            confluences.append("Pavio superior longo")

        # Volume (exemplo simplificado)
        volume = data.get("volume", [])[-1] if data.get("volume") else 0
        if volume > 1000:  # valor arbitrário
            confluences.append("Volume alto")

        # Contar confluências
        if len(confluences) >= 3:
            # Calcular probabilidade (exemplo simples)
            probability = 0.7 + 0.05 * (len(confluences) - 3)
            probability = min(probability, 0.95)

            # Calcular horário da entrada: 1 min antes do próximo candle M5
            minute = (current_time.minute // 5 + 1) * 5
            if minute == 60:
                entry_time = current_time.replace(hour=current_time.hour + 1, minute=0, second=0, microsecond=0)
            else:
                entry_time = current_time.replace(minute=minute, second=0, microsecond=0)
            # Evitar enviar sinal se já passou do tempo para enviar (menos de 1 min antes)
            if (entry_time - current_time) > timedelta(seconds=30):
                candidates.append({
                    "pair": pair,
                    "direction": trend,
                    "entry_time": entry_time,
                    "probability": probability,
                    "reason": ", ".join(confluences)
                })

    if not candidates:
        return None

    # Selecionar o par com maior probabilidade
    best = max(candidates, key=lambda x: x["probability"])

    # Marcar operação ativa
    active_operation = {
        "pair": best["pair"],
        "direction": best["direction"],
        "entry_time": best["entry_time"],
        "probability": best["probability"],
        "reason": best["reason"],
        "start_time": current_time
    }

    print(f"Sinal enviado: {best['pair']} {best['direction']} às {best['entry_time'].strftime('%H:%M')} Prob: {best['probability']:.2f} Motivo: {best['reason']}")

    return best
