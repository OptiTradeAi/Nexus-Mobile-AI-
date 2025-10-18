"""
backend/__init__.py
---------------------------------
Este arquivo marca a pasta 'backend' como um módulo Python válido.

📌 Funções principais:
- Permite que o Python e a Render encontrem e importem o módulo 'backend.main'.
- Garante que o FastAPI (via Uvicorn) consiga inicializar corretamente o app.

⚙️ Estrutura esperada:
Nexus-Mobile-AI-main/
│
├── backend/
│   ├── __init__.py        ✅ (este arquivo)
│   ├── main.py            # Arquivo principal do backend
│   ├── ai_analyzer.py     # Módulo de IA
│   └── static/
│       └── viewer.html    # Interface visual do stream
│
└── render.yaml
"""

# Pode ficar vazio ou conter inicializações globais do backend.
# Aqui deixamos preparado para inicializações futuras (ex: logs ou IA).
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("backend")

logger.info("Backend module initialized successfully ✅")
