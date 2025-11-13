# Usa imagem base do Python
FROM python:3.11-slim

# Define o diretório de trabalho dentro do container
WORKDIR /app

# Copia todo o conteúdo do projeto (inclusive backend, static, etc)
COPY . .

# Instala as dependências
RUN pip install --no-cache-dir -r backend/requirements.txt

# Expõe a porta padrão usada pela Render
EXPOSE 10000

# Comando para iniciar o app
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "10000"]
