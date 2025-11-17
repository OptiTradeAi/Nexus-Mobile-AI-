# Dockerfile (root)
FROM python:3.11-slim

WORKDIR /app

# Copy only backend folder to reduce build size
COPY backend /app/backend

# Install dependencies
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r /app/backend/requirements.txt

ENV TZ=America/Sao_Paulo

EXPOSE 10000

# Start FastAPI
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "10000", "--log-level", "info"]
