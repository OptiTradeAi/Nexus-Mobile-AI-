# Imagem base leve do Python 3.11
FROM python:3.11-slim

# Define o diretório principal
WORKDIR /app

# Copia todo o conteúdo do projeto (incluindo backend e static)
COPY . .

# Instala as dependências da pasta backend
RUN pip install --no-cache-dir -r backend/requirements.txt

# Expõe a porta padrão usada pela Render
EXPOSE 10000

# Comando de inicialização — apontando corretamente para o backend.main
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "10000"]
