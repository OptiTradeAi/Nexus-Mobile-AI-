import base64
import io
from datetime import datetime
from PIL import Image
import numpy as np

# Histórico simples de frames e sinais (para debug)
FRAME_LOG = []
SIGNAL_LOG = []

# Limiar de detecção fictício — depois pode ser substituído por IA real
SIGNAL_THRESHOLD = 0.8


def analyze_frame(frame_b64: str, mime: str = "image/webp") -> dict:
    """
    Analisa o frame recebido e tenta gerar uma leitura básica.
    Aqui futuramente entra o módulo de IA real (CNN, OpenCV etc.)
    """
    try:
        img_data = base64.b64decode(frame_b64)
        image = Image.open(io.BytesIO(img_data)).convert("RGB")

        # Estatística simples (placeholder para IA real)
        np_img = np.array(image)
        brightness = np.mean(np_img)
        contrast = np.std(np_img)

        FRAME_LOG.append({
            "timestamp": datetime.now().isoformat(),
            "brightness": float(brightness),
            "contrast": float(contrast)
        })

        # Simulação: gera sinal aleatório baseado no contraste
        decision = "CALL" if contrast % 2 > 1 else "PUT"
        confidence = round(min(1.0, contrast / 120), 3)

        signal = {
            "pair": "AUTO",
            "type": decision,
            "confidence": confidence,
            "reason": "detecção visual primária (simulada)",
            "time": datetime.now().strftime("%H:%M:%S")
        }

        SIGNAL_LOG.append(signal)

        return {"ok": True, "signal": signal}

    except Exception as e:
        return {"ok": False, "error": str(e)}


def get_logs() -> dict:
    """Retorna histórico de frames e sinais para debug"""
    return {"frames": FRAME_LOG[-10:], "signals": SIGNAL_LOG[-10:]}
