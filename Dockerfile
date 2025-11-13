# ======================================================
# Nexus Mobile AI - Dockerfile (Root)
# Build otimizado para Render
# ======================================================

# Imagem base leve e compatível
FROM python:3.11-slim

# Define diretório de trabalho dentro do container
WORKDIR /app

# Copia tudo da raiz do projeto para dentro do container
COPY . .

# Instala dependências do backend
RUN pip install --no-cache-dir -r backend/requirements.txt

# Define timezone (Brasil)
ENV TZ=America/Sao_Paulo

# Expõe a porta usada pelo backend
EXPOSE 10000

# Comando padrão de inicialização do servidor
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "10000"]
