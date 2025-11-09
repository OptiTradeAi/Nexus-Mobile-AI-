# backend/ai_engine.py
import datetime, zoneinfo, math
from typing import Dict, Any, List, Optional

TZ = zoneinfo.ZoneInfo("America/Sao_Paulo")
HISTORY: List[Dict[str,Any]] = []   # list of signals + results
PENDING_SIGNALS: List[Dict[str,Any]] = []
SIGNAL_THRESHOLD = 0.80

# simple store of last frame/candle
LAST_FRAME = None
LAST_TICKS = []  # keep recent ticks

def register_frame(msg: Dict[str,Any]):
    global LAST_FRAME
    LAST_FRAME = {"pair": msg.get("pair"), "data": msg.get("data"), "ts": datetime.datetime.datetime.now(TZ)} if False else {"pair": msg.get("pair"), "data": msg.get("data"), "ts": datetime.datetime.datetime.now(TZ)}
    # we keep as placeholder; vision analysis can read LAST_FRAME

def _next_m5_open(dt: datetime.datetime) -> datetime.datetime:
    # returns next M5 candle open datetime in TZ
    # example: if time is 10:03 -> next m5 starts at 10:05:00
    dt = dt.astimezone(TZ).replace(second=0, microsecond=0)
    minute = dt.minute
    next_minute = ((minute // 5) + 1) * 5
    hour = dt.hour
    day = dt.day
    mon = dt.month
    year = dt.year
    if next_minute >= 60:
        next_minute = 0
        dt = dt + datetime.timedelta(hours=1)
        dt = dt.replace(minute=0, second=0, microsecond=0)
    else:
        dt = dt.replace(minute=next_minute, second=0, microsecond=0)
    return dt

def analyze_and_maybe_signal(tick: Dict[str,Any]) -> Optional[Dict[str,Any]]:
    """
    tick expected: {pair, timestamp (ISO), open, high, low, close, volume}
    This function is a rule-based stub:
     - uses simple momentum and last candle to propose a signal
     - only triggers for M5 timeframe signals scheduled 60s before next M5 open.
    """
    import datetime
    from dateutil import parser
    ts = parser.isoparse(tick.get("timestamp"))
    now = ts.astimezone(TZ)
    # store tick
    LAST_TICKS.append(tick)
    if len(LAST_TICKS) > 200:
        LAST_TICKS.pop(0)
    # Determine candidate time to act: 60s before next M5 open
    next_open = _next_m5_open(now)
    delta = (next_open - now).total_seconds()
    # Only when delta between 55 and 65 seconds (allow small jitter)
    if 50 <= delta <= 70:
        # Basic heuristic: recent closes trend
        closes = [c.get("close", 0) for c in LAST_TICKS[-6:]]
        if len(closes) < 3: return None
        avg_recent = sum(closes)/len(closes)
        last = closes[-1]
        # simple momentum
        if last > avg_recent * 1.0005:
            side = "CALL"
            confidence = 0.82
            reason = "momentum_up"
        elif last < avg_recent * 0.9995:
            side = "PUT"
            confidence = 0.82
            reason = "momentum_down"
        else:
            return None
        if confidence >= SIGNAL_THRESHOLD:
            signal = {
                "pair": tick.get("pair"),
                "sent_at": datetime.datetime.datetime.now(TZ).isoformat(),
                "expected_candle_start": next_open.isoformat(),
                "side": side,
                "confidence": confidence,
                "reason": reason,
                "result": "PENDING"
            }
            HISTORY.append(signal)
            PENDING_SIGNALS.append({"signal": signal, "expected_candle_start": next_open})
            return signal
    return None

async def evaluate_pending_signals():
    """
    Check PENDING_SIGNALS: when expected_candle_start has passed and candle closed,
    determine WIN/LOSS using LAST_TICKS (matching candle close).
    """
    import datetime
    to_remove = []
    for entry in list(PENDING_SIGNALS):
        expected = entry["expected_candle_start"]
        if isinstance(expected, str):
            expected = datetime.datetime.fromisoformat(expected)
        now = datetime.datetime.now(TZ)
        if now >= expected + datetime.timedelta(seconds=65):  # make sure candle closed
            # find the tick whose timestamp equals expected (approx)
            # fallback: look for tick with timestamp within expected..expected+70s
            target = None
            for t in reversed(LAST_TICKS):
                try:
                    import dateutil.parser as dp
                    tts = dp.isoparse(t.get("timestamp")).astimezone(TZ)
                    if expected <= tts <= expected + datetime.timedelta(seconds=70):
                        target = t
                        break
                except:
                    continue
            signal = entry["signal"]
            if target:
                # evaluate: if side CALL and close > open => win
                if signal["side"] == "CALL":
                    win = (target.get("close",0) > target.get("open",0))
                else:
                    win = (target.get("close",0) < target.get("open",0))
                signal["result"] = "WIN" if win else "LOSS"
                signal["closed_at"] = datetime.datetime.now(TZ).isoformat()
                HISTORY.append({"evaluation": signal})
            else:
                signal["result"] = "UNKNOWN"
                signal["closed_at"] = datetime.datetime.now(TZ).isoformat()
                HISTORY.append({"evaluation": signal})
            to_remove.append(entry)
    for r in to_remove:
        try:
            PENDING_SIGNALS.remove(r)
        except:
            pass
