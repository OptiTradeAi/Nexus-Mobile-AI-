# backend/ai_engine_fusion.py
"""
Kaon Precision 80 - Engine de análise (corrigido)
- Recebe ticks/frames + meta (price, next_candle_seconds)
- Mantém estado por par: ticks, m5 candles, operações ativas, bloqueios
- Decide sinais M5: envia sinal SIGNAL_LEAD_SECONDS antes da próxima M5 open se >=3 confluências
- Permite registro explícito de entry via register_entry()
"""

import os
import json
import math
import threading
from datetime import datetime, timezone, timedelta
from collections import deque

import numpy as np
import pandas as pd

DATA_DIR = os.environ.get("NEXUS_DATA_DIR", "backend/data")
os.makedirs(DATA_DIR, exist_ok=True)
HISTORY_PATH = os.path.join(DATA_DIR, "history.json")
STATE_PATH = os.path.join(DATA_DIR, "state.json")

# Parâmetros Kaon
M5_BLOCK_CANDLES = 3
SIGNAL_LEAD_SECONDS = 60
TIMEZONE = timezone(timedelta(hours=-3))  # Brasília (UTC-3)
OPERATION_DURATION_SECONDS = 5 * 60
MIN_CANDLES_FOR_INDICATORS = 25

_state_lock = threading.Lock()
STATE = {
    "pairs": {},
    "global": {"last_signal": None}
}


def _load_history():
    if os.path.isfile(HISTORY_PATH):
        try:
            with open(HISTORY_PATH, "r") as f:
                return json.load(f)
        except Exception:
            return {"trades": []}
    return {"trades": []}


def _save_history(h):
    try:
        with open(HISTORY_PATH, "w") as f:
            json.dump(h, f, indent=2, default=str)
    except Exception as e:
        print("⚠️ Falha ao salvar history:", e)


HISTORY = _load_history()


def _persist_state():
    try:
        with _state_lock:
            with open(STATE_PATH, "w") as f:
                json.dump(STATE, f, indent=2, default=str)
    except Exception as e:
        print("⚠️ Falha ao persistir state:", e)


def now_ts():
    return datetime.now(timezone.utc)


def start_of_m5(dt):
    minute = (dt.minute // 5) * 5
    return dt.replace(minute=minute, second=0, microsecond=0)


def next_m5_open(dt):
    s = start_of_m5(dt)
    candidate = s + timedelta(minutes=5)
    return candidate


def _ensure_pair(pair):
    with _state_lock:
        if pair not in STATE["pairs"]:
            STATE["pairs"][pair] = {
                "ticks": deque(maxlen=10000),
                "m5": None,
                "blocked_until": None,
                "last_op": None,
                "active_op": None,
                "stats": {"wins": 0, "losses": 0, "trades": 0}
            }


def add_tick(pair, ts, price):
    """ts: datetime (aware)"""
    _ensure_pair(pair)
    with _state_lock:
        STATE["pairs"][pair]["ticks"].append((ts.isoformat(), float(price)))


def build_m5_from_ticks(pair):
    _ensure_pair(pair)
    with _state_lock:
        ticks = list(STATE["pairs"][pair]["ticks"])
    if not ticks:
        return None
    df = pd.DataFrame(ticks, columns=["ts", "price"])
    df["ts"] = pd.to_datetime(df["ts"])
    df = df.set_index("ts").sort_index()
    try:
        m5 = df['price'].resample('5T').ohlc()
        m5['v'] = df['price'].resample('5T').count()
        m5 = m5.dropna().reset_index().rename(columns={'open': 'o', 'high': 'h', 'low': 'l', 'close': 'c', 'volume': 'v', 'ts': 'time'})
        with _state_lock:
            STATE["pairs"][pair]["m5"] = m5
        return m5
    except Exception as e:
        print("⚠️ build_m5_from_ticks error", e)
        return None


# indicadores
def compute_ema(series, span):
    return series.ewm(span=span, adjust=False).mean()


def compute_rsi(series, period=14):
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    ma_up = up.rolling(period).mean()
    ma_down = down.rolling(period).mean()
    rsi = 100 - (100 / (1 + (ma_up / ma_down)))
    return rsi


def bollinger_bands(series, length=20, mult=2.0):
    ma = series.rolling(length).mean()
    std = series.rolling(length).std()
    upper = ma + mult * std
    lower = ma - mult * std
    return ma, upper, lower


def detect_sr_zones(m5_df, lookback=60):
    if m5_df is None or len(m5_df) < 5:
        return []
    prices = m5_df['c']
    pivots = []
    for i in range(2, len(prices) - 2):
        window = prices[i - 2:i + 3]
        center = prices.iloc[i]
        if center == window.max():
            pivots.append(('res', center, i))
        if center == window.min():
            pivots.append(('sup', center, i))
    zones = []
    for t, p, idx in pivots[-lookback:]:
        zones.append({'type': 'res' if t == 'res' else 'sup', 'price': float(p), 'weight': 1})
    # merge clusters by proximity
    merged = []
    while zones:
        base = zones.pop(0)
        cluster = [base]
        for z in zones[:]:
            if abs(z['price'] - base['price']) <= (0.002 * base['price']):
                cluster.append(z)
                zones.remove(z)
        avg_price = sum([c['price'] for c in cluster]) / len(cluster)
        merged.append({'type': cluster[0]['type'], 'price': avg_price, 'weight': len(cluster)})
    return merged


def evaluate_confluences(pair, m5_df):
    if m5_df is None or len(m5_df) < MIN_CANDLES_FOR_INDICATORS:
        return {'confluences': 0, 'details': {}, 'probability': 0.0, 'direction': None, 'reason': 'insufficient_data'}
    series = m5_df['c'].copy().reset_index(drop=True).astype(float)
    ema20 = compute_ema(series, 20).iloc[-1]
    ema50 = compute_ema(series, 50).iloc[-1]
    trend = 'bull' if ema20 > ema50 else 'bear'
    rsi = compute_rsi(series, 14).iloc[-1]
    ma, upper, lower = bollinger_bands(series, 20, 2)
    close_outside_upper = False
    close_outside_lower = False
    if not pd.isna(upper.iloc[-1]):
        close_outside_upper = series.iloc[-1] > upper.iloc[-1]
    if not pd.isna(lower.iloc[-1]):
        close_outside_lower = series.iloc[-1] < lower.iloc[-1]

    def candle_props(i):
        o = m5_df.iloc[i]['o']
        h = m5_df.iloc[i]['h']
        l = m5_df.iloc[i]['l']
        c = m5_df.iloc[i]['c']
        body = abs(c - o)
        upper_wick = h - max(c, o)
        lower_wick = min(c, o) - l
        return {'o': o, 'h': h, 'l': l, 'c': c, 'body': body, 'uw': upper_wick, 'lw': lower_wick}

    p_last = candle_props(-1)
    p_prev = candle_props(-2)

    confluences = []
    details = {}

    zones = detect_sr_zones(m5_df, lookback=60)
    near_zone = None
    last = series.iloc[-1]
    for z in zones:
        if abs(last - z['price']) <= (0.006 * z['price']):
            near_zone = z
            break
    if near_zone:
        rej = False
        if near_zone['type'] == 'res':
            if p_last['uw'] > p_last['body'] * 1.2:
                rej = True
        else:
            if p_last['lw'] > p_last['body'] * 1.2:
                rej = True
        if rej:
            confluences.append('zone_rejection')
            details['zone'] = near_zone

    # engulfing
    if (p_prev['c'] < p_prev['o'] and p_last['c'] > p_last['o'] and (p_last['c'] - p_last['o']) > (p_prev['o'] - p_prev['c']) * 0.8):
        confluences.append('bull_engulf')
    if (p_prev['c'] > p_prev['o'] and p_last['c'] < p_last['o'] and (p_last['o'] - p_last['c']) > (p_prev['c'] - p_prev['o']) * 0.8):
        confluences.append('bear_engulf')

    if p_last['lw'] > p_last['body'] * 1.5:
        confluences.append('long_lower_wick')
    if p_last['uw'] > p_last['body'] * 1.5:
        confluences.append('long_upper_wick')

    rsi_conf = False
    boll_conf = False
    if rsi < 30 and p_last['lw'] > p_last['body'] * 0.8:
        rsi_conf = True
    if rsi > 70 and p_last['uw'] > p_last['body'] * 0.8:
        rsi_conf = True
    if close_outside_lower:
        boll_conf = True
    if close_outside_upper:
        boll_conf = True
    if rsi_conf:
        confluences.append('rsi_extreme')
    if boll_conf:
        confluences.append('bollinger_touch')

    if (ema20 > ema50 and p_last['c'] > ema20) or (ema20 < ema50 and p_last['c'] < ema20):
        confluences.append('ema_alignment')

    vol = m5_df.iloc[-1]['v'] if 'v' in m5_df.columns else 1
    if vol >= 1:
        confluences.append('volume_ok')

    direction = None
    if 'long_lower_wick' in confluences or 'bull_engulf' in confluences:
        direction = 'call'
    if 'long_upper_wick' in confluences or 'bear_engulf' in confluences:
        direction = 'put'
    if direction:
        if not ((trend == 'bull' and direction == 'call') or (trend == 'bear' and direction == 'put')):
            # prefer trend when ambiguous
            direction = 'call' if trend == 'bull' else 'put'
    else:
        direction = 'call' if trend == 'bull' else 'put'

    weights = {
        'zone_rejection': 1.6,
        'bull_engulf': 1.3,
        'bear_engulf': 1.3,
        'long_lower_wick': 1.2,
        'long_upper_wick': 1.2,
        'rsi_extreme': 1.4,
        'bollinger_touch': 1.3,
        'ema_alignment': 1.1,
        'volume_ok': 1.0
    }
    score = sum([weights.get(c, 0.5) for c in confluences])
    probability = min(0.99, max(0.05, (score / 6.0)))

    return {
        'confluences': len(confluences),
        'details': {'list': confluences, 'trend': trend, 'rsi': float(rsi)},
        'probability': float(probability),
        'direction': direction,
        'reason': ' + '.join(confluences) if confluences else 'none'
    }


def analyze_frame(frame_b64, mime="image/webp"):
    try:
        return {'ok': True, 'info': 'no meta provided'}
    except Exception as e:
        return {'ok': False, 'error': str(e)}


def register_entry(payload):
    """
    payload must contain: pair, entry_time (ISO), entry_price, direction, agent_id (optional)
    This function sets active_op for the pair (used later to compute result)
    """
    try:
        pair = payload.get('pair', 'UNKNOWN_PAIR')
        entry_price = float(payload.get('entry_price')) if payload.get('entry_price') is not None else None
        entry_time_iso = payload.get('entry_time') or now_ts().isoformat()
        direction = payload.get('direction')
        _ensure_pair(pair)
        with _state_lock:
            STATE["pairs"][pair]['active_op'] = {
                'entry_time': entry_time_iso,
                'direction': direction,
                'entry_price': entry_price
            }
            STATE["global"]['last_signal'] = {'pair': pair, 'time': now_ts().isoformat()}
            _persist_state()
        return {'ok': True, 'registered': True, 'pair': pair}
    except Exception as e:
        return {'ok': False, 'error': str(e)}


def analyze_frame_with_meta(payload):
    """
    payload: dict with keys:
     - pair
     - timestamp (ISO)
     - data (base64 image)
     - current_price or price (float)
     - next_candle_seconds (int)
    Returns: dict with analysis; if signal generated, includes analysis['signal'].
    """
    try:
        pair = payload.get('pair', 'UNKNOWN_PAIR')
        ts_iso = payload.get('timestamp')
        current_price = payload.get('current_price', payload.get('price', None))
        next_seconds = int(payload.get('next_candle_seconds', 9999)) if payload.get('next_candle_seconds') is not None else 9999
        ts = None
        if ts_iso:
            try:
                ts = datetime.fromisoformat(ts_iso)
            except:
                ts = now_ts()
        else:
            ts = now_ts()
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        if current_price is not None:
            add_tick(pair, ts, float(current_price))
            m5 = build_m5_from_ticks(pair)
        else:
            with _state_lock:
                m5 = STATE["pairs"].get(pair, {}).get("m5", None)

        _ensure_pair(pair)
        with _state_lock:
            pstate = STATE["pairs"][pair]

        active = pstate.get('active_op')
        now = ts

        # close active op by time if older than duration
        if active:
            try:
                entry_ts = datetime.fromisoformat(active['entry_time'])
                if entry_ts.tzinfo is None:
                    entry_ts = entry_ts.replace(tzinfo=timezone.utc)
            except:
                entry_ts = None
            if entry_ts and (now - entry_ts).total_seconds() >= OPERATION_DURATION_SECONDS:
                result = 'UNKNOWN'
                if current_price is not None and active.get('entry_price') is not None:
                    entry_price = active.get('entry_price')
                    dirc = active.get('direction')
                    if dirc == 'call':
                        result = 'WIN' if float(current_price) > float(entry_price) else 'LOSS'
                    else:
                        result = 'WIN' if float(current_price) < float(entry_price) else 'LOSS'
                trade = {
                    'pair': pair,
                    'entry_time': active.get('entry_time'),
                    'direction': active.get('direction'),
                    'entry_price': active.get('entry_price'),
                    'close_time': now.isoformat(),
                    'close_price': current_price,
                    'result': result
                }
                HISTORY.setdefault('trades', []).append(trade)
                with _state_lock:
                    STATE["pairs"][pair]['active_op'] = None
                    STATE["pairs"][pair]['last_op'] = now.isoformat()
                    if result == 'WIN':
                        STATE["pairs"][pair]['stats']['wins'] += 1
                        STATE["pairs"][pair]['stats']['trades'] += 1
                    elif result == 'LOSS':
                        STATE["pairs"][pair]['stats']['losses'] += 1
                        STATE["pairs"][pair]['stats']['trades'] += 1
                    STATE["pairs"][pair]['blocked_until'] = (now + timedelta(minutes=5 * M5_BLOCK_CANDLES)).isoformat()
                _save_history(HISTORY)
                _persist_state()
                return {'ok': True, 'analysis': {'trade_closed': trade}}

        # check blocked
        blocked_until = pstate.get('blocked_until')
        if blocked_until:
            try:
                bu = datetime.fromisoformat(blocked_until)
                if bu.tzinfo is None:
                    bu = bu.replace(tzinfo=timezone.utc)
            except:
                bu = None
        else:
            bu = None
        if bu and now < bu:
            return {'ok': True, 'analysis': {'reason': 'pair_blocked', 'blocked_until': bu.isoformat()}}

        # time window check for signal
        local_now = now.astimezone(TIMEZONE)
        nm5 = next_m5_open(local_now)
        seconds_to_open = (nm5 - local_now).total_seconds()

        if seconds_to_open <= SIGNAL_LEAD_SECONDS + 5 and seconds_to_open >= SIGNAL_LEAD_SECONDS - 10:
            con = evaluate_confluences(pair, m5)
            if con['confluences'] >= 3 and con['probability'] >= 0.5:
                # ensure no global active op
                with _state_lock:
                    any_active = any([STATE["pairs"][k].get('active_op') for k in STATE["pairs"]])
                    if any_active:
                        return {'ok': True, 'analysis': {'reason': 'another_operation_active'}}
                    # mark active op tentatively (entry_time stored in UTC iso)
                    STATE["pairs"][pair]['active_op'] = {
                        'entry_time': nm5.astimezone(timezone.utc).isoformat(),
                        'direction': con['direction'],
                        'entry_price': current_price,
                        'probability': con['probability'],
                        'reason': con['reason']
                    }
                    STATE["global"]['last_signal'] = {'pair': pair, 'time': now.isoformat()}
                    _persist_state()

                entry_time_local = nm5.astimezone(TIMEZONE)
                signal = {
                    'pair': pair,
                    'direction': con['direction'],
                    'entry_time': entry_time_local.isoformat(),
                    'probability': con['probability'],
                    'confluences': con['details'],
                    'reason': con['reason'],
                    'time_now': now.isoformat()
                }
                return {'ok': True, 'analysis': {'signal': signal}}
            else:
                return {'ok': True, 'analysis': {'reason': 'not_enough_confluences', 'con': con}}
        else:
            return {'ok': True, 'analysis': {'reason': 'not_time_yet', 'seconds_to_open': seconds_to_open}}
    except Exception as e:
        return {'ok': False, 'error': str(e)}
