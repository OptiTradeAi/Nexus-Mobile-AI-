import base64
import io
from datetime import datetime
from PIL import Image
import numpy as np
import random # Adicionado para simulação de sinal

# Histórico simples de frames e sinais (para debug)
FRAME_LOG = []
SIGNAL_LOG = []

# Limiar de detecção fictício — depois pode ser substituído por IA real
SIGNAL_THRESHOLD = 0.8

def analyze_frame(frame_b64: str, mime: str = "image/webp") -> dict:
    """
    Analisa o frame recebido (já em base64) e tenta gerar uma leitura básica.
    Aqui futuramente entra o módulo de IA real (CNN, OpenCV etc.)
    """
    try:
        img_data = base64.b64decode(frame_b64)
        image = Image.open(io.BytesIO(img_data)).convert("RGB")

        # Estatística simples (placeholder para IA real)
        np_img = np.array(image)
        brightness = np.mean(np_img)
        contrast = np.std(np_img)

        current_timestamp = datetime.now().isoformat()

        FRAME_LOG.append({
            "timestamp": current_timestamp,
            "brightness": float(brightness),
            "contrast": float(contrast)
        })
        # Limita o log para não consumir muita memória
        if len(FRAME_LOG) > 100:
            FRAME_LOG.pop(0)

        # Simulação: gera sinal aleatório baseado no contraste e um pouco de aleatoriedade
        # Isso é um placeholder para sua lógica de IA real
        decision = "CALL" if random.random() > 0.5 else "PUT"
        # A confiança pode ser baseada em algo mais complexo do que apenas contraste
        confidence = round(min(1.0, max(0.5, contrast / 150 + random.uniform(-0.1, 0.1))), 3)

        signal = {
            "pair": "AUTO_DETECT", # O userscript tentará enviar o par
            "type": decision,
            "confidence": confidence,
            "reason": "detecção visual primária (simulada)",
            "time": datetime.now().strftime("%H:%M:%S")
        }

        SIGNAL_LOG.append(signal)
        # Limita o log de sinais
        if len(SIGNAL_LOG) > 50:
            SIGNAL_LOG.pop(0)

        return {"ok": True, "signal": signal, "brightness": float(brightness), "contrast": float(contrast)}

    except Exception as e:
        print(f"Erro na análise do frame: {e}")
        return {"ok": False, "error": str(e)}

def get_logs() -> dict:
    """Retorna histórico de frames e sinais para debug"""
    return {"frames": FRAME_LOG, "signals": SIGNAL_LOG}
