# backend/Dockerfile
FROM python:3.11-slim

# Dependências do sistema necessárias para compilar/instalar Pillow e outras libs nativas
RUN apt-get update && apt-get install -y \
    build-essential \
    libjpeg-dev \
    zlib1g-dev \
    libpng-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copia o requirements primeiro para aproveitar cache de camadas
COPY backend/requirements.txt /app/backend/requirements.txt

# Atualiza pip/setuptools/wheel e instala requirements
RUN pip install --upgrade pip setuptools wheel && pip install -r /app/backend/requirements.txt

# Copia o restante do código
COPY . /app

# Expor porta (o Render vai mapear $PORT)
EXPOSE 8000

# Comando padrão: usa $PORT se o Render passar via variável de ambiente
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
