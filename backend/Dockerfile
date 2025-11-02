# backend/Dockerfile
FROM python:3.11-slim

# instalar dependências de sistema necessárias para compilar/rodar Pillow e bibliotecas nativas
RUN apt-get update && apt-get install -y \
    build-essential \
    libjpeg-dev \
    zlib1g-dev \
    libpng-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# copiar requirements para cache de camada
COPY backend/requirements.txt /app/backend/requirements.txt

# atualizar pip/setuptools/wheel e instalar requirements
RUN pip install --upgrade pip setuptools wheel && pip install -r backend/requirements.txt

# copiar todo o projeto
COPY . /app

# expor porta (opcional, usado no container)
EXPOSE 8000

# comando padrão — Render vai usar a porta que você definir (ou $PORT se usar startCommand)
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
