from fastapi import FastAPI
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import os

# Inicializa o app
app = FastAPI(title="Nexus Mobile AI")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Monta pasta estática
static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Página principal
@app.get("/", response_class=HTMLResponse)
async def root():
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return HTMLResponse("<h1>Nexus Mobile AI is running 🚀</h1><p>Backend ativo com sucesso.</p>", status_code=200)

# Rota exemplo (candles)
@app.get("/api/candles")
async def get_candles():
    return {"status": "ok", "data": "Espelhamento futuro aqui"}
