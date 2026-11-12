"""Carga inicial do banco a partir de CSVs no formato MovieLens (movies.csv e ratings.csv)."""
import logging
from pathlib import Path

import pandas as pd
from sqlalchemy import func, insert, select, text
from sqlalchemy.orm import Session

from app.models import Item, Rating, User

log = logging.getLogger(__name__)


def _reset_sequences(db: Session) -> None:
    """No PostgreSQL, inserir IDs explícitos não avança a sequência; corrigimos aqui."""
    if db.bind.dialect.name != "postgresql":
        return
    for table in ("users", "items", "ratings"):
        db.execute(
            text(
                f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
                f"COALESCE((SELECT MAX(id) FROM {table}), 1))"
            )
        )


def seed_from_csv(db: Session, data_dir: Path) -> dict[str, int]:
    movies = pd.read_csv(data_dir / "movies.csv")
    ratings = pd.read_csv(data_dir / "ratings.csv")
    ratings = ratings[ratings["movieId"].isin(movies["movieId"])]

    db.execute(
        insert(Item),
        [
            {"id": int(r.movieId), "title": str(r.title), "genres_raw": "" if r.genres == "(no genres listed)" else str(r.genres)}
            for r in movies.itertuples()
        ],
    )
    user_ids = sorted(ratings["userId"].unique())
    db.execute(insert(User), [{"id": int(u), "name": f"Usuário {u}", "favorite_genres_raw": ""} for u in user_ids])
    db.execute(
        insert(Rating),
        [
            {"user_id": int(r.userId), "item_id": int(r.movieId), "rating": float(r.rating)}
            for r in ratings.itertuples()
        ],
    )
    _reset_sequences(db)
    db.commit()
    counts = {"items": len(movies), "users": len(user_ids), "ratings": len(ratings)}
    log.info("Banco populado a partir de %s: %s", data_dir, counts)
    return counts


def seed_if_empty(db: Session, data_dir: Path) -> dict[str, int] | None:
    if db.scalar(select(func.count()).select_from(Item)):
        return None
    if not (data_dir / "movies.csv").exists():
        log.warning("Pasta de seed %s sem movies.csv; banco iniciará vazio.", data_dir)
        return None
    return seed_from_csv(db, data_dir)
