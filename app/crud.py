"""Operações de banco usadas pelos endpoints."""
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Item, Rating, User
from app.schemas import RatingIn, UserOut


def get_user_or_404(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Usuário {user_id} não encontrado")
    return user


def get_item_or_404(db: Session, item_id: int) -> Item:
    item = db.get(Item, item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Item {item_id} não encontrado")
    return item


def count_ratings(db: Session, user_id: int) -> int:
    return db.scalar(select(func.count()).select_from(Rating).where(Rating.user_id == user_id)) or 0


def user_out(db: Session, user: User) -> UserOut:
    return UserOut(
        id=user.id, name=user.name, favorite_genres=user.favorite_genres, n_ratings=count_ratings(db, user.id)
    )


def upsert_rating(db: Session, user_id: int, data: RatingIn) -> Rating:
    """Insere a avaliação ou atualiza a nota se o usuário já avaliou o item."""
    get_item_or_404(db, data.item_id)
    rating = db.scalar(select(Rating).where(Rating.user_id == user_id, Rating.item_id == data.item_id))
    if rating is None:
        rating = Rating(user_id=user_id, item_id=data.item_id, rating=data.rating)
        db.add(rating)
    else:
        rating.rating = data.rating
    return rating
