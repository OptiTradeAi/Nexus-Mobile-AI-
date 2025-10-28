# /backend/ai_analyzer.py
import datetime, math
from typing import List, Dict, Any

# Configurações de análise
TIMEFRAME_MINUTES = 5            # M5
LEAD_TIME_SECONDS = 30          # enviar sinal X segundos antes da abertura do próximo candle
CONFIDENCE_THRESHOLD = 0.80     # só enviar sinal se >= 0.8

def next_candle_open_from_iso(ts_iso: str) -> datetime.datetime:
    """Dado timestamp ISO da vela atual (assume que corresponde ao início da vela atual),
    calcula o próximo momento de abertura (start) da próxima vela M5."""
    dt = datetime.datetime.fromisoformat(ts_iso.replace("Z", "+00:00"))
    # normalize minute to multiple of TIMEFRAME_MINUTES
    minute = (dt.minute // TIMEFRAME_MINUTES) * TIMEFRAME_MINUTES
    base = dt.replace(minute=minute, second=0, microsecond=0)
    next_open = base + datetime.timedelta(minutes=TIMEFRAME_MINUTES)
    return next_open

def compute_momentum(candles: List[Dict[str, Any]], lookback: int = 3) -> float:
    """Momentum simples: normalized difference between last and lookback close."""
    if not candles or len(candles) < 2:
        return 0.0
    lookback = min(lookback, len(candles)-1)
    last = candles[-1]['close']
    prev = candles[-1-lookback]['close']
    if prev == 0:
        return 0.0
    return (last - prev) / abs(prev)

def compute_volatility(candles: List[Dict[str, Any]], lookback: int = 5) -> float:
    """Volatility as stddev of returns (approx)."""
    if not candles or len(candles) < 2:
        return 0.0
    returns = []
    for i in range(1, min(len(candles), lookback+1)):
        a = candles[-i]['close']
        b = candles[-i-1]['close']
        if b != 0:
            returns.append((a - b) / abs(b))
    if not returns:
        return 0.0
    mean = sum(returns) / len(returns)
    var = sum((r-mean)**2 for r in returns) / len(returns)
    return math.sqrt(var)

def analyze_candles(history: List[Dict[str, Any]], current: Dict[str, Any]) -> Dict[str, Any]:
    """
    history: list of previous candles for the same pair (each a dict with keys at least 'open','high','low','close','timestamp')
    current: the latest candle snapshot received (dict)
    Returns: {decision: 'CALL'|'PUT'|'NONE', confidence: float, explanation: str, time_to_open: seconds}
    """
    # Build local list including the current as last
    candles = history.copy() if history else []
    # ensure current close present (may be repeating single-price snapshot)
    candles.append(current)

    # compute features
    momentum = compute_momentum(candles, lookback=3)
    vol = compute_volatility(candles, lookback=5)
    # normalize momentum into [-1,1] but limit by large moves
    mscore = max(-1.0, min(1.0, momentum * 5))  # sensitivity factor

    # base confidence: depends on magnitude of momentum and inverse volatility
    base_conf = min(0.99, max(0.0, abs(mscore) * (1.0 / (0.5 + vol)) ))  # heuristic

    # pattern boosting (3 rising closes or 3 falling)
    decision = "NONE"
    explanation = []
    n = len(candles)
    if n >= 4:
        closes = [c['close'] for c in candles[-4:]]
        if closes[0] < closes[1] < closes[2] < closes[3]:
            # consistent rise
            decision = "CALL"
            base_conf *= 1.15
            explanation.append("4-green momentum")
        elif closes[0] > closes[1] > closes[2] > closes[3]:
            decision = "PUT"
            base_conf *= 1.15
            explanation.append("4-red momentum")

    # fallback: use last 2-3 candles momentum
    if decision == "NONE":
        if mscore > 0.02:  # small positive momentum
            decision = "CALL"
            explanation.append("positive momentum")
        elif mscore < -0.02:
            decision = "PUT"
            explanation.append("negative momentum")
        else:
            decision = "NONE"
            explanation.append("insufficient momentum")

    # confidence clamp
    confidence = min(0.999, max(0.0, base_conf))
    explanation_text = "; ".join(explanation) if explanation else "heuristic"

    # compute time to next candle open
    # `current['timestamp']` should be ISO string marking start of current candle (or snapshot time)
    try:
        next_open = next_candle_open_from_iso(current['timestamp'])
        now = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)
        time_to_open = (next_open - now).total_seconds()
    except Exception:
        time_to_open = 9999

    # should we send now? only if confidence >= threshold and within lead time
    send_recommendation = (confidence >= CONFIDENCE_THRESHOLD) and (time_to_open <= LEAD_TIME_SECONDS)

    return {
        "decision": decision,
        "confidence": round(confidence, 3),
        "explanation": explanation_text,
        "time_to_open": int(time_to_open),
        "send": bool(send_recommendation),
        "threshold": CONFIDENCE_THRESHOLD,
        "lead_time_seconds": LEAD_TIME_SECONDS
    }
