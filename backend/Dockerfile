# backend/Dockerfile
FROM python:3.11-slim

# ===============================================
# Etapa 1: Instala dependências do sistema
# ===============================================
# Inclui pacotes necessários para Pillow, SSL, criptografia, etc.
RUN apt-get update && apt-get install -y \
    build-essential \
    libjpeg-dev \
    zlib1g-dev \
    libpng-dev \
    libfreetype6-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Define o diretório de trabalho
WORKDIR /app

# ===============================================
# Etapa 2: Instala dependências Python
# ===============================================
# Copia apenas o requirements primeiro (cache eficiente)
COPY backend/requirements.txt /app/backend/requirements.txt

# Atualiza pip e instala dependências
RUN pip install --upgrade pip setuptools wheel \
    && pip install -r /app/backend/requirements.txt --no-cache-dir

# ===============================================
# Etapa 3: Copia o restante do código
# ===============================================
COPY . /app

# ===============================================
# Etapa 4: Segurança e execução
# ===============================================
# Cria um usuário não-root (boa prática de segurança)
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# Expõe a porta 8000 (Render usará automaticamente a variável $PORT)
EXPOSE 8000

# ===============================================
# Etapa 5: Comando de inicialização
# ===============================================
# Inicia o servidor FastAPI/Starlette com Uvicorn
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
