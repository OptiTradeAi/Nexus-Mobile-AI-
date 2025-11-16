# ====
# Nexus Mobile AI - Dockerfile (Root)
# Build otimizado para Render
# ====

FROM python:3.11-slim
WORKDIR /app

# Instala dependências do sistema necessárias para Playwright
RUN apt-get update && apt-get install -y \
    curl \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
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
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libnss3 \
    libxss1 \
    libxtst6 \
    libx11-xcb1 \
    libxcb1 \
    libx11-6 \
    libxext6 \
    libxfixes3 \
    libxrender1 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libnss3 \
    libxss1 \
    libxtst6 \
    && rm -rf /var/lib/apt/lists/*

# Copia tudo para dentro do container
COPY . .

# Instala dependências Python
RUN pip install --no-cache-dir -r ./backend/requirements.txt

# Instala Playwright e navegadores
RUN pip install --no-cache-dir playwright websockets
RUN playwright install

# Define timezone
ENV TZ=America/Sao_Paulo

# Porta padrão
EXPOSE 10000

# Comando padrão para rodar o backend FastAPI
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "10000"]
