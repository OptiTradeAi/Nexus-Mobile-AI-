# backend/ai_engine_fusion.py
"""
Kaon Precision 80 - Engine de análise
- Recebe frames (base64) + meta (price, next_candle_seconds)
- Mantém estado por par: candles, operações ativas, bloqueios
- Decide sinais M5: envia sinal 60s antes do próximo M5 open se >=3 confluências
- Aprende com resultado: registra WIN/LOSS e atualiza weights simples
"""

import os, json, time, math
from datetime import datetime, timezone, timedelta
import threading
from collections import defaultdict, deque

import numpy as np
import pandas as pd

# Requisitos: pandas, numpy, scipy, ta (opcional)
# pip install pandas numpy scipy ta python-dateutil pytz

DATA_DIR = os.environ.get("NEXUS_DATA_DIR", "backend/data")
os.makedirs(DATA_DIR, exist_ok=True)
HISTORY_PATH = os.path.join(DATA_DIR, "history.json")
STATE_PATH = os.path.join(DATA_DIR, "state.json")

# --- Parâmetros do sistema Kaon ---
M5_BLOCK_CANDLES = 3            # bloquear par por 3 candles M5
SIGNAL_LEAD_SECONDS = 60       # enviar sinal 60s antes da abertura M5
TIMEZONE = timezone(timedelta(hours=-3))  # Brasília (UTC-3) — ajustável

# tempo para considerar como "operação ativa" (espera resultado) = 5m
OPERATION_DURATION_SECONDS = 5 * 60

# mínimos para calcular indicadores
MIN_CANDLES_FOR_INDICATORS = 25

# guarda estado em memória
_state_lock = threading.Lock()
STATE = {
    "pairs": {},  # cada par => dict: ticks deque, m5_candles DataFrame (cached), blocked_until (iso), last_op (iso), active_op (dict)
    "global": {
        "last_signal": None
    }
}

# carrega histórico persistido
def _load_history():
    if os.path.isfile(HISTORY_PATH):
        try:
            with open(HISTORY_PATH, "r") as f:
                return json.load(f)
        except:
            return {"trades": []}
    return {"trades": []}

def _save_history(h):
    with open(HISTORY_PATH, "w") as f:
        json.dump(h, f, indent=2, default=str)

HISTORY = _load_history()

def _persist_state():
    try:
        with _state_lock:
            with open(STATE_PATH, "w") as f:
                json.dump(STATE, f, indent=2, default=str)
    except Exception as e:
        print("⚠️ Falha ao persistir state:", e)

# --- utilitários de tempo ---
def now_ts():
    return datetime.now(timezone.utc)

def to_local(dt):
    # retorna string ISO na timezone BR
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt)
    return dt.astimezone(TIMEZONE)

def start_of_m5(dt):
    # dt: datetime (aware)
    minute = (dt.minute // 5) * 5
    return dt.replace(minute=minute, second=0, microsecond=0)

def next_m5_open(dt):
    s = start_of_m5(dt)
    candidate = s + timedelta(minutes=5)
    return candidate

# --- estrutura de candles a partir de ticks simples ---
def _ensure_pair(pair):
    with _state_lock:
        if pair not in STATE["pairs"]:
            STATE["pairs"][pair] = {
                "ticks": deque(maxlen=10000),  # (ts_iso, price)
                "m5": None,   # pandas DataFrame of M5 candles (open,high,low,close,volume,dt_index)
                "blocked_until": None,
                "last_op": None,
                "active_op": None,
                "stats": {
                    "wins": 0, "losses": 0, "trades": 0
                }
            }

def add_tick(pair, ts, price):
    """Adiciona tick (ts: datetime aware)"""
    _ensure_pair(pair)
    with _state_lock:
        STATE["pairs"][pair]["ticks"].append((ts.isoformat(), float(price)))
        # não persistir aqui por performance; persistimos periodicamente se quiser

def build_m5_from_ticks(pair):
    _ensure_pair(pair)
    with _state_lock:
        ticks = list(STATE["pairs"][pair]["ticks"])
    if not ticks:
        return None
    df = pd.DataFrame(ticks, columns=["ts", "price"])
    df["ts"] = pd.to_datetime(df["ts"])
    df = df.set_index("ts").sort_index()
    # resample 1m for M1 then to 5m
    try:
        m1 = df['price'].resample('1T').ohlc()
        m5 = m1['close'].resample('5T').ohlc()
        # but better to compute open/high/low/close on 5T directly:
        m5_full = df['price'].resample('5T').ohlc()
        m5_full['volume'] = df['price'].resample('5T').count()
        m5_full = m5_full.dropna().rename(columns={'open':'o','high':'h','low':'l','close':'c','volume':'v'})
        m5_full = m5_full.reset_index().rename(columns={'ts':'time'})
        with _state_lock:
            STATE["pairs"][pair]["m5"] = m5_full
        return m5_full
    except Exception as e:
        print("⚠️ build_m5_from_ticks error", e)
        return None

# --- indicadores --- (implementações simples)
def compute_ema(series, span):
    return series.ewm(span=span, adjust=False).mean()

def compute_rsi(series, period=14):
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -1*delta.clip(upper=0)
    ma_up = up.rolling(period).mean()
    ma_down = down.rolling(period).mean()
    rsi = 100 - (100 / (1 + (ma_up/ma_down)))
    return rsi

def bollinger_bands(series, length=20, mult=2.0):
    ma = series.rolling(length).mean()
    std = series.rolling(length).std()
    upper = ma + mult*std
    lower = ma - mult*std
    return ma, upper, lower

# --- zonas SR (heurística simples de pivots locais) ---
def detect_sr_zones(m5_df, lookback=60):
    """
    Detecta zonas de suporte/resistência através de pivots.
    Retorna lista de zones: [{'type':'res','price':p,'weight':w}, ...]
    """
    if m5_df is None or len(m5_df) < 5:
        return []
    prices = m5_df['c']
    pivots = []
    for i in range(2, len(prices)-2):
        window = prices[i-2:i+3]
        center = prices.iloc[i]
        if center == window.max():
            pivots.append(('res', center, i))
        if center == window.min():
            pivots.append(('sup', center, i))
    zones = []
    for t, p, idx in pivots[-lookback:]:
        zones.append({'type': 'res' if t=='res' else 'sup', 'price': float(p), 'weight': 1})
    # agregação simples por proximidade
    merged = []
    while zones:
        base = zones.pop(0)
        cluster = [base]
        close_idxs = []
        for z in zones[:]:
            if abs(z['price'] - base['price']) <= (0.002 * base['price']):  # 0.2% proximity
                cluster.append(z); zones.remove(z)
        avg_price = sum([c['price'] for c in cluster])/len(cluster)
        merged.append({'type': cluster[0]['type'], 'price': avg_price, 'weight': len(cluster)})
    return merged

# --- regras Kaon: confluências ---
def evaluate_confluences(pair, m5_df):
    """
    Retorna dict:
      { 'confluences': n, 'details': {...}, 'probability': 0..1, 'direction': 'call'/'put' or None, 'reason': '...' }
    """
    if m5_df is None or len(m5_df) < MIN_CANDLES_FOR_INDICATORS:
        return {'confluences': 0, 'details': {}, 'probability': 0.0, 'direction': None, 'reason':'insufficient_data'}

    series = m5_df['c'].copy().reset_index(drop=True).astype(float)
    last_idx = len(series)-1
    last = series.iloc[last_idx]

    # EMA20 / EMA50 trend
    ema20 = compute_ema(series, 20).iloc[-1]
    ema50 = compute_ema(series, 50).iloc[-1]
    trend = 'bull' if ema20 > ema50 else 'bear'

    # RSI
    rsi = compute_rsi(series, 14).iloc[-1]

    # Bollinger
    ma, upper, lower = bollinger_bands(series, 20, 2)
    close_outside_upper = series.iloc[-1] > upper.iloc[-1] if not math.isnan(upper.iloc[-1]) else False
    close_outside_lower = series.iloc[-1] < lower.iloc[-1] if not math.isnan(lower.iloc[-1]) else False

    # Candle pattern heuristics (last two candles)
    # We'll measure wick sizes vs body
    def candle_props(i):
        o = m5_df.iloc[i]['o']
        h = m5_df.iloc[i]['h']
        l = m5_df.iloc[i]['l']
        c = m5_df.iloc[i]['c']
        body = abs(c - o)
        upper_wick = h - max(c,o)
        lower_wick = min(c,o) - l
        return {'o':o,'h':h,'l':l,'c':c,'body':body,'uw':upper_wick,'lw':lower_wick}

    p_last = candle_props(-1)
    p_prev = candle_props(-2)

    confluences = []
    details = {}

    # 1) Zone reversal - detect if last touched a SR zone and showed rejection
    zones = detect_sr_zones(m5_df, lookback=60)
    near_zone = None
    for z in zones:
        if abs(last - z['price']) <= (0.006 * z['price']):  # within 0.6% - treat as touch
            near_zone = z
            break
    if near_zone:
        # check rejection: candle with long opposite wick
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

    # 2) Candle rejection / pattern
    # Engulfing / long wick
    if (p_prev['c'] < p_prev['o'] and p_last['c'] > p_last['o'] and (p_last['c'] - p_last['o']) > (p_prev['o'] - p_prev['c']) * 0.8):
        # bullish engulfing-ish
        confluences.append('bull_engulf')
    if (p_prev['c'] > p_prev['o'] and p_last['c'] < p_last['o'] and (p_last['o'] - p_last['c']) > (p_prev['c'] - p_prev['o']) * 0.8):
        confluences.append('bear_engulf')

    # wick patterns
    if p_last['lw'] > p_last['body'] * 1.5:
        confluences.append('long_lower_wick')
    if p_last['uw'] > p_last['body'] * 1.5:
        confluences.append('long_upper_wick')

    # 3) RSI + Bollinger confirmation
    rsi_conf = False
    boll_conf = False
    if rsi < 30 and p_last['lw'] > p_last['body']*0.8:
        rsi_conf = True
    if rsi > 70 and p_last['uw'] > p_last['body']*0.8:
        rsi_conf = True
    if close_outside_lower:
        boll_conf = True
    if close_outside_upper:
        boll_conf = True
    if rsi_conf:
        confluences.append('rsi_extreme')
    if boll_conf:
        confluences.append('bollinger_touch')

    # 4) EMA alignment optional
    if (ema20 > ema50 and p_last['c'] > ema20) or (ema20 < ema50 and p_last['c'] < ema20):
        confluences.append('ema_alignment')

    # 5) Volume heuristic (we used m5.v)
    vol = m5_df.iloc[-1]['v'] if 'v' in m5_df.columns else 1
    if vol >= 1:
        # normalized
        confluences.append('volume_ok')

    # decide direction candidate
    direction = None
    if 'long_lower_wick' in confluences or 'bull_engulf' in confluences:
        direction = 'call'
    if 'long_upper_wick' in confluences or 'bear_engulf' in confluences:
        direction = 'put'
    # if both, prefer trend alignment
    if direction and ((trend == 'bull' and direction == 'call') or (trend == 'bear' and direction == 'put')):
        pass  # keep
    else:
        # prefer trend if ambiguous
        if trend == 'bull':
            direction = 'call'
        else:
            direction = 'put'

    # probability heuristic: base on count + quality weights
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
    # normalize (heuristic)
    probability = min(0.99, max(0.05, (score / 6.0)))

    return {
        'confluences': len(confluences),
        'details': {'list': confluences, 'trend': trend, 'rsi': float(rsi)},
        'probability': float(probability),
        'direction': direction,
        'reason': ' + '.join(confluences) if confluences else 'none'
    }

# --- AGREGADOR PRINCIPAL (função chamada por backend/main.py) ---
def analyze_frame(frame_b64, mime="image/webp"):
    """
    interface backward-compatible: older main.py enviava apenas frame_b64.
    We expect the main.py to pass meta via global temp or via frame_b64 wrapper.
    For compatibility, this function will just return a minimal analysis.
    """
    # Caso legacy: retorna apenas ok
    try:
        return {'ok': True, 'info': 'no meta provided'}
    except Exception as e:
        return {'ok': False, 'error': str(e)}

# Versão avançada: espera um dicionário com meta:
def analyze_frame_with_meta(payload):
    """
    payload: dict com chaves:
      - pair (str)
      - timestamp (ISO)
      - data (base64 image)
      - current_price (float)  <-- preferível
      - next_candle_seconds (int)
    Retorna análise dict. Se sinal gerado, inclui 'signal' sub-dict.
    """
    try:
        pair = payload.get('pair', 'UNKNOWN_PAIR')
        ts_iso = payload.get('timestamp')
        current_price = payload.get('current_price', None)
        next_seconds = int(payload.get('next_candle_seconds', 9999))
        ts = datetime.fromisoformat(ts_iso) if ts_iso else now_ts()
        # normalize timezone awareness
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        # add tick if price provided
        if current_price is not None:
            add_tick(pair, ts, float(current_price))
            m5 = build_m5_from_ticks(pair)
        else:
            # try to use cached m5 if exists
            with _state_lock:
                m5 = STATE["pairs"].get(pair, {}).get("m5", None)

        # load pair state
        _ensure_pair(pair)
        with _state_lock:
            pstate = STATE["pairs"][pair]

        # check active operation
        active = pstate.get('active_op')
        now = ts

        # if there's an active operation older than OPERATION_DURATION_SECONDS, close it and compute result
        if active:
            entry_ts = datetime.fromisoformat(active['entry_time'])
            if (now - entry_ts).total_seconds() >= OPERATION_DURATION_SECONDS:
                # evaluate result via price comparison (if we have price ticks)
                result = None
                if current_price is not None:
                    entry_price = active.get('entry_price')
                    dirc = active.get('direction')
                    if entry_price is not None:
                        # for CALL: win if later price > entry_price; for PUT: win if later price < entry_price
                        if dirc == 'call':
                            result = 'WIN' if current_price > entry_price else 'LOSS'
                        else:
                            result = 'WIN' if current_price < entry_price else 'LOSS'
                else:
                    # if no price info: unknown
                    result = 'UNKNOWN'

                # record trade result
                trade = {
                    'pair': pair,
                    'entry_time': active.get('entry_time'),
                    'direction': active.get('direction'),
                    'entry_price': active.get('entry_price'),
                    'close_time': now.isoformat(),
                    'close_price': current_price,
                    'result': result
                }
                HISTORY['trades'].append(trade)
                # update stats
                with _state_lock:
                    pstate['active_op'] = None
                    pstate['last_op'] = now.isoformat()
                    if result == 'WIN':
                        pstate['stats']['wins'] += 1
                        pstate['stats']['trades'] += 1
                    elif result == 'LOSS':
                        pstate['stats']['losses'] += 1
                        pstate['stats']['trades'] += 1
                    # block par for M5_BLOCK_CANDLES: compute blocked_until as now + (M5_BLOCK_CANDLES*5m)
                    pstate['blocked_until'] = (now + timedelta(minutes=5*M5_BLOCK_CANDLES)).isoformat()
                _save_history(HISTORY)
                _persist_state()
                return {'ok': True, 'analysis': {'trade_closed': trade}}

        # If no active op: check if time to prepare a signal (SIGNAL_LEAD_SECONDS before next M5 open)
        # compute next m5 open from now
        local_now = now.astimezone(TIMEZONE)
        nm5 = next_m5_open(local_now)
        seconds_to_open = (nm5 - local_now).total_seconds()
        # check block
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
            # pair is resting
            return {'ok': True, 'analysis': {'reason': 'pair_blocked', 'blocked_until': bu.isoformat()}}

        # Only consider when we are within the lead window (e.g. 50..70s before open)
        if seconds_to_open <= SIGNAL_LEAD_SECONDS + 5 and seconds_to_open >= SIGNAL_LEAD_SECONDS - 10:
            # compute confluences
            con = evaluate_confluences(pair, m5)
            # must have at least 3 confluences to be considered
            if con['confluences'] >= 3 and con['probability'] >= 0.5:
                # ensure no other active op globally
                with _state_lock:
                    any_active = any([STATE["pairs"][k].get('active_op') for k in STATE["pairs"]])
                if any_active:
                    return {'ok': True, 'analysis': {'reason': 'another_operation_active'}}
                # prepare signal payload
                entry_time_local = nm5.astimezone(TIMEZONE)  # time of entry
                # mark active op tentatively (until main executes real order)
                with _state_lock:
                    STATE["pairs"][pair]['active_op'] = {
                        'entry_time': nm5.astimezone(timezone.utc).isoformat(),
                        'direction': con['direction'],
                        'entry_price': current_price,
                        'probability': con['probability'],
                        'reason': con['reason']
                    }
                    STATE["global"]['last_signal'] = {'pair': pair, 'time': now.isoformat()}
                    _persist_state()

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
