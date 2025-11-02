# backend/Dockerfile
FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive

# Instala dependências do sistema necessárias para Pillow e builds nativos
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libjpeg-dev \
    zlib1g-dev \
    libpng-dev \
    libtiff5-dev \
    libopenjp2-7-dev \
    libwebp-dev \
    libfreetype6-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copia requirements primeiro para aproveitar cache de camadas
COPY backend/requirements.txt /app/backend/requirements.txt

# Atualiza pip/setuptools/wheel e instala as dependências
RUN pip install --upgrade pip setuptools wheel && pip install -r /app/backend/requirements.txt

# Copia todo o código
COPY . /app

EXPOSE 8000

# Usa $PORT se o Render fornecer, senão 8000
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
