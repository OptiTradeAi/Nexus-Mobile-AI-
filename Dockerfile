# Use imagem oficial Python slim
FROM python:3.11-slim

# Define diretório de trabalho
WORKDIR /app

# Instala dependências do sistema necessárias para Playwright e Chrome headless
RUN apt-get update && apt-get install -y \
    curl \
    libnss3 \
    libatk1.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpangocairo-1.0-0 \
    libpango-1.0-0 \
    libxshmfence1 \
    libgtk-3-0 \
    libx11-xcb1 \
    libxcb-dri3-0 \
    libxcb-dri2-0 \
    libxcb-glx0 \
    libxcb-present0 \
    libxcb-sync1 \
    libxext6 \
    libxfixes3 \
    libxrender1 \
    libx11-6 \
    libatk-bridge2.0-0 \
    libxss1 \
    libxtst6 \
    && rm -rf /var/lib/apt/lists/*

# Copia os arquivos do projeto para dentro do container
COPY backend/ ./backend/
COPY requirements.txt .

# Instala as dependências Python
RUN pip install --no-cache-dir -r requirements.txt

# Instala Playwright e seus navegadores
RUN pip install --no-cache-dir playwright
RUN playwright install

# Define timezone para Brasília
ENV TZ=America/Sao_Paulo

# Expõe a porta padrão do backend
EXPOSE 10000

# Comando padrão para iniciar o backend FastAPI
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "10000"]
