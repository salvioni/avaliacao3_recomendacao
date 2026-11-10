"""Schemas Pydantic: definem o formato de entrada/saída da API (e aparecem no Swagger)."""
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class Strategy(str, Enum):
    hybrid = "hybrid"
    collaborative = "collaborative"
    content = "content"
    popular = "popular"


# ---------- Itens ----------
class ItemCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=300, examples=["Interestelar (2014)"])
    genres: list[str] = Field(default_factory=list, examples=[["Sci-Fi", "Drama"]])


class ItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    genres: list[str]


# ---------- Avaliações ----------
class RatingIn(BaseModel):
    item_id: int
    rating: float = Field(..., ge=0.5, le=5.0, description="Nota de 0.5 a 5.0", examples=[4.5])


class RatingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    item_id: int
    rating: float


# ---------- Usuários ----------
class UserCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120, examples=["Cele"])
    favorite_genres: list[str] = Field(
        default_factory=list,
        description="Gêneros preferidos; usados para recomendar mesmo sem avaliações (cold start).",
        examples=[["Comedy", "Romance"]],
    )


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    favorite_genres: list[str]
    n_ratings: int = 0


class PreferencesUpdate(BaseModel):
    favorite_genres: list[str] | None = Field(
        default=None, description="Se enviado, substitui a lista de gêneros preferidos."
    )
    ratings: list[RatingIn] = Field(
        default_factory=list, description="Avaliações a inserir ou atualizar (upsert)."
    )


# ---------- Recomendações ----------
class RecommendationOut(BaseModel):
    item: ItemOut
    score: float = Field(..., description="Pontuação normalizada entre 0 e 1")
    reason: str = Field(..., description="Explicação em linguagem natural do porquê da recomendação")


class RecommendationsResponse(BaseModel):
    user_id: int
    strategy: Strategy
    strategy_used: str = Field(..., description="Estratégia efetivamente aplicada (pode cair para fallback)")
    recommendations: list[RecommendationOut]


class SimilarItemsResponse(BaseModel):
    item_id: int
    similar: list[RecommendationOut]


class Message(BaseModel):
    detail: str
