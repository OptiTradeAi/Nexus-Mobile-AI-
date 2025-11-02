# backend/Dockerfile
FROM python:3.11-slim

# dependências de sistema necessárias para Pillow e builds nativos
RUN apt-get update && apt-get install -y \
    build-essential \
    libjpeg-dev \
    zlib1g-dev \
    libpng-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# copiar requirements para cache de camada (ajusta se seu requirements estiver em outro lugar)
COPY backend/requirements.txt /app/backend/requirements.txt

# atualizar pip/setuptools/wheel e instalar requirements
RUN pip install --upgrade pip setuptools wheel && pip install -r backend/requirements.txt

# copiar todo o projeto
COPY . /app

EXPOSE 8000

# comando padrão (o Render pode passar a porta via $PORT se você configurar startCommand)
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
