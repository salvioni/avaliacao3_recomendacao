"""Configurações da aplicação, lidas de variáveis de ambiente."""
import os
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "sim"}


@dataclass(frozen=True)
class Settings:
    # SQLite por padrão (execução local); no Docker Compose aponta para o PostgreSQL.
    database_url: str = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'recsys.db'}")
    # Popula o banco na inicialização se ele estiver vazio.
    seed_on_startup: bool = _bool(os.getenv("SEED_ON_STARTUP"), True)
    # Pasta com movies.csv e ratings.csv no formato MovieLens.
    seed_dir: Path = Path(os.getenv("SEED_DIR", str(BASE_DIR / "data" / "sample")))
    # Nº de avaliações a partir do qual a filtragem colaborativa tem peso total no modo híbrido.
    cf_full_weight_at: int = int(os.getenv("CF_FULL_WEIGHT_AT", "20"))


settings = Settings()
