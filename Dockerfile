# ======================================================
# Nexus Mobile AI - Dockerfile (Root)
# Build otimizado para Render
# ======================================================

# Imagem base leve e compatível
FROM python:3.11-slim

# Define diretório de trabalho dentro do container
WORKDIR /app

# Copia todos os arquivos da raiz (inclui /backend e outros)
COPY . .

# Instala dependências do backend
RUN pip install --no-cache-dir -r backend/requirements.txt

# Define a variável de ambiente de timezone (Brasil)
ENV TZ=America/Sao_Paulo

# Expõe a porta usada pela aplicação
EXPOSE 10000

# Comando de inicialização padrão do servidor Uvicorn
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "10000"]
