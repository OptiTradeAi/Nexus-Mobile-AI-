# ======================================================
# Nexus Mobile AI - Dockerfile (Root)
# Build otimizado para Render
# ======================================================

FROM python:3.11-slim
WORKDIR /app

# Copia tudo para dentro do container
COPY . .

# Instala dependências
RUN pip install --no-cache-dir -r ./backend/requirements.txt

# Define timezone
ENV TZ=America/Sao_Paulo

# Porta padrão
EXPOSE 10000

# Comando padrão
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "10000"]
