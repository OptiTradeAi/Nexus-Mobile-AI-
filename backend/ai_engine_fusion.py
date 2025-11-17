import time
from datetime import datetime, timedelta
import pytz

BR_TZ = pytz.timezone("America/Sao_Paulo")

active_operations = {}
entry_history = []

MIN_TIME_BETWEEN_SIGNALS = timedelta(minutes=5)

def analyze_frame_with_meta(payload):
    """
    Função principal de análise que recebe o payload com frame e metadados,
    retorna análise com possíveis sinais.
    """
    try:
        pair = payload.get("pair", "UNKNOWN")
        timestamp_str = payload.get("timestamp")
        timestamp = datetime.fromisoformat(timestamp_str) if timestamp_str else datetime.now(BR_TZ)
        
        # Simulação de indicadores e condições
        bollinger_break = True  # exemplo: rompimento banda de bollinger
        rsi_oversold = True     # exemplo: RSI em sobrevenda
        ema_cross = True        # exemplo: cruzamento de EMAs
        fluxo_compra = True     # exemplo: fluxo comprador forte
        
        # Confluências para sinal CALL
        confluences = []
        if bollinger_break:
            confluences.append("Bollinger Break")
        if rsi_oversold:
            confluences.append("RSI Oversold")
        if ema_cross:
            confluences.append("EMA Cross")
        if fluxo_compra:
            confluences.append("Fluxo Compra")
        
        now = datetime.now(BR_TZ)
        last_entry = active_operations.get(pair)
        if last_entry and (now - last_entry) < MIN_TIME_BETWEEN_SIGNALS:
            return {"ok": True, "analysis": {"signal": None, "reason": "Sinal bloqueado por cooldown"}}
        
        if len(confluences) >= 3:
            minute = (now.minute // 5 + 1) * 5
            if minute == 60:
                entry_time = now.replace(hour=now.hour+1, minute=0, second=0, microsecond=0)
            else:
                entry_time = now.replace(minute=minute, second=0, microsecond=0)
            
            probability = 0.80
            
            signal = {
                "pair": pair,
                "direction": "call",
                "entry_time": entry_time.isoformat(),
                "probability": probability,
                "reason": ", ".join(confluences),
                "timestamp": now.isoformat()
            }
            
            active_operations[pair] = now
            
            return {"ok": True, "analysis": {"signal": signal}}
        
        return {"ok": True, "analysis": {"signal": None, "reason": "Confluências insuficientes"}}
    
    except Exception as e:
        return {"ok": False, "error": str(e)}

def register_entry(payload):
    """
    Registra a entrada confirmada (ex: recebida do frontend ou do Navigator)
    para atualizar histórico e autoaprendizado.
    """
    try:
        pair = payload.get("pair")
        direction = payload.get("direction")
        entry_time_str = payload.get("entry_time")
        result = payload.get("result")  # "win", "loss", "draw"
        timestamp = datetime.now(BR_TZ)
        
        entry_time = datetime.fromisoformat(entry_time_str) if entry_time_str else None
        
        entry_record = {
            "pair": pair,
            "direction": direction,
            "entry_time": entry_time,
            "result": result,
            "timestamp": timestamp
        }
        
        entry_history.append(entry_record)
        
        if pair in active_operations:
            del active_operations[pair]
        
        return True
    except Exception as e:
        return False
