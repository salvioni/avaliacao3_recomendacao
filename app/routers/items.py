from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crud import get_item_or_404
from app.database import get_db
from app.models import Item
from app.schemas import ItemCreate, ItemOut, Message, SimilarItemsResponse, RecommendationOut
from app.services import recommender_service

router = APIRouter(prefix="/items", tags=["Itens"])


@router.post("", response_model=ItemOut, status_code=status.HTTP_201_CREATED, summary="Adicionar um novo item")
def create_item(payload: ItemCreate, db: Session = Depends(get_db)):
    item = Item(title=payload.title)
    item.genres = payload.genres
    db.add(item)
    db.commit()
    recommender_service.invalidate()
    return item


@router.get("", response_model=list[ItemOut], summary="Listar/buscar itens")
def list_items(
    q: str | None = Query(None, description="Trecho do título"),
    genre: str | None = Query(None, description="Filtra por gênero, ex.: Comedy"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    stmt = select(Item).order_by(Item.id)
    if q:
        stmt = stmt.where(Item.title.ilike(f"%{q}%"))
    if genre:
        stmt = stmt.where(Item.genres_raw.ilike(f"%{genre}%"))
    return db.scalars(stmt.offset(skip).limit(limit)).all()


@router.get("/{item_id}", response_model=ItemOut, responses={404: {"model": Message}}, summary="Detalhar item")
def get_item(item_id: int, db: Session = Depends(get_db)):
    return get_item_or_404(db, item_id)


@router.get(
    "/{item_id}/similar",
    response_model=SimilarItemsResponse,
    responses={404: {"model": Message}},
    summary="Itens similares (\"quem viu este também viu\")",
)
def similar_items(item_id: int, n: int = Query(10, ge=1, le=50), db: Session = Depends(get_db)):
    get_item_or_404(db, item_id)
    model = recommender_service.get_model(db)
    recs = model.similar_items(item_id, n)
    items = {i.id: i for i in db.scalars(select(Item).where(Item.id.in_([r.item_id for r in recs])))}
    return SimilarItemsResponse(
        item_id=item_id,
        similar=[
            RecommendationOut(item=ItemOut.model_validate(items[r.item_id]), score=r.score, reason=r.reason)
            for r in recs
        ],
    )
