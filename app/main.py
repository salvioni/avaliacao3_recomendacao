"""Ponto de entrada da API. Documentação interativa em /docs (Swagger UI) e /redoc."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.routers import items, users
from app.seed import seed_if_empty

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    if settings.seed_on_startup:
        with SessionLocal() as db:
            seed_if_empty(db, settings.seed_dir)
    yield


app = FastAPI(
    title="Próxima Sessão — Recomendação de Filmes",
    description=(
        "API de recomendação híbrida (filtragem colaborativa item-item + baseada em conteúdo), "
        "com explicação de cada recomendação e tratamento de cold start."
    ),
    version="1.0.0",
    lifespan=lifespan,
    openapi_tags=[
        {"name": "Usuários", "description": "Cadastro, preferências, avaliações e recomendações"},
        {"name": "Itens", "description": "Catálogo de filmes e itens similares"},
        {"name": "Sistema", "description": "Saúde da aplicação"},
    ],
)
app.include_router(users.router)
app.include_router(items.router)


@app.get("/health", tags=["Sistema"], summary="Verifica se a API e o banco estão no ar")
def health():
    with SessionLocal() as db:
        db.execute(text("SELECT 1"))
    return {"status": "ok"}
