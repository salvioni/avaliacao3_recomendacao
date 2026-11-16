from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crud import get_item_or_404, get_user_or_404, upsert_rating, user_out
from app.database import get_db
from app.models import Item, Rating, User
from app.schemas import (
    ItemOut,
    Message,
    PreferencesUpdate,
    RatingIn,
    RatingOut,
    RecommendationOut,
    RecommendationsResponse,
    Strategy,
    UserCreate,
    UserOut,
)
from app.services import recommender_service

router = APIRouter(prefix="/users", tags=["Usuários"])
NOT_FOUND = {404: {"model": Message}}


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED, summary="Adicionar um novo usuário")
def create_user(payload: UserCreate, db: Session = Depends(get_db)):
    user = User(name=payload.name)
    user.favorite_genres = payload.favorite_genres
    db.add(user)
    db.commit()
    recommender_service.invalidate()
    return user_out(db, user)


@router.get("", response_model=list[UserOut], summary="Listar usuários")
def list_users(skip: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    users = db.scalars(select(User).order_by(User.id).offset(skip).limit(limit)).all()
    return [user_out(db, u) for u in users]


@router.get("/{user_id}", response_model=UserOut, responses=NOT_FOUND, summary="Detalhar usuário")
def get_user(user_id: int, db: Session = Depends(get_db)):
    return user_out(db, get_user_or_404(db, user_id))


@router.put(
    "/{user_id}/preferences",
    response_model=UserOut,
    responses=NOT_FOUND,
    summary="Atualizar as preferências de um usuário",
    description="Substitui os gêneros favoritos (se enviados) e insere/atualiza várias avaliações de uma vez.",
)
def update_preferences(user_id: int, payload: PreferencesUpdate, db: Session = Depends(get_db)):
    user = get_user_or_404(db, user_id)
    if payload.favorite_genres is not None:
        user.favorite_genres = payload.favorite_genres
    for r in payload.ratings:
        upsert_rating(db, user_id, r)
    db.commit()
    recommender_service.invalidate()
    return user_out(db, user)


@router.post(
    "/{user_id}/ratings",
    response_model=RatingOut,
    status_code=status.HTTP_201_CREATED,
    responses=NOT_FOUND,
    summary="Avaliar um item",
)
def rate_item(user_id: int, payload: RatingIn, db: Session = Depends(get_db)):
    get_user_or_404(db, user_id)
    rating = upsert_rating(db, user_id, payload)
    db.commit()
    recommender_service.invalidate()
    return rating


@router.get("/{user_id}/ratings", response_model=list[RatingOut], responses=NOT_FOUND, summary="Avaliações do usuário")
def list_ratings(user_id: int, db: Session = Depends(get_db)):
    get_user_or_404(db, user_id)
    return db.scalars(select(Rating).where(Rating.user_id == user_id).order_by(Rating.item_id)).all()


@router.delete(
    "/{user_id}/ratings/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=NOT_FOUND,
    summary="Remover uma avaliação",
)
def delete_rating(user_id: int, item_id: int, db: Session = Depends(get_db)):
    get_user_or_404(db, user_id)
    get_item_or_404(db, item_id)
    rating = db.scalar(select(Rating).where(Rating.user_id == user_id, Rating.item_id == item_id))
    if rating is not None:
        db.delete(rating)
        db.commit()
        recommender_service.invalidate()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{user_id}/recommendations",
    response_model=RecommendationsResponse,
    responses=NOT_FOUND,
    summary="Obter recomendações para um usuário",
    description=(
        "Estratégias: **hybrid** (padrão) combina colaborativa e conteúdo, com o peso da colaborativa "
        "crescendo conforme o usuário avalia mais itens; **collaborative**; **content**; **popular**. "
        "Itens já avaliados nunca são recomendados."
    ),
)
def recommendations(
    user_id: int,
    n: int = Query(10, ge=1, le=50, description="Quantidade de recomendações"),
    strategy: Strategy = Query(Strategy.hybrid),
    db: Session = Depends(get_db),
):
    user = get_user_or_404(db, user_id)
    model = recommender_service.get_model(db)
    recs, used = model.recommend(user_id, n=n, strategy=strategy.value, favorite_genres=user.favorite_genres)
    items = {i.id: i for i in db.scalars(select(Item).where(Item.id.in_([r.item_id for r in recs])))}
    return RecommendationsResponse(
        user_id=user_id,
        strategy=strategy,
        strategy_used=used,
        recommendations=[
            RecommendationOut(item=ItemOut.model_validate(items[r.item_id]), score=r.score, reason=r.reason)
            for r in recs
        ],
    )
