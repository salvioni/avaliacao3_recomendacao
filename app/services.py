"""
Serviço que mantém o modelo treinado em memória.

Sempre que usuários, itens ou avaliações mudam, a API chama `invalidate()`.
O modelo é retreinado sob demanda (preguiçosamente) na próxima recomendação,
o que mantém as escritas rápidas e as recomendações sempre atualizadas.
"""
import threading

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Item, Rating
from app.recommender import HybridRecommender


class RecommenderService:
    def __init__(self) -> None:
        self._model: HybridRecommender | None = None
        self._dirty = True
        self._lock = threading.Lock()

    def invalidate(self) -> None:
        self._dirty = True

    def get_model(self, db: Session) -> HybridRecommender:
        with self._lock:
            if self._dirty or self._model is None:
                items = pd.DataFrame(
                    db.execute(select(Item.id, Item.title, Item.genres_raw)).all(),
                    columns=["item_id", "title", "genres"],
                )
                ratings = pd.DataFrame(
                    db.execute(select(Rating.user_id, Rating.item_id, Rating.rating)).all(),
                    columns=["user_id", "item_id", "rating"],
                )
                self._model = HybridRecommender(cf_full_weight_at=settings.cf_full_weight_at).fit(
                    items, ratings
                )
                self._dirty = False
            return self._model


recommender_service = RecommenderService()
