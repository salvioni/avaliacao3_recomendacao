"""Tabelas do banco: usuários, itens (filmes) e avaliações."""
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

SEP = "|"  # separador de gêneros, igual ao MovieLens


def split_genres(value: str | None) -> list[str]:
    if not value or value == "(no genres listed)":
        return []
    return [g for g in value.split(SEP) if g]


def join_genres(genres: list[str]) -> str:
    # remove duplicados preservando a ordem
    return SEP.join(dict.fromkeys(g.strip() for g in genres if g.strip()))


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    favorite_genres_raw: Mapped[str] = mapped_column("favorite_genres", String(500), default="")

    ratings: Mapped[list["Rating"]] = relationship(back_populates="user", cascade="all, delete-orphan")

    @property
    def favorite_genres(self) -> list[str]:
        return split_genres(self.favorite_genres_raw)

    @favorite_genres.setter
    def favorite_genres(self, genres: list[str]) -> None:
        self.favorite_genres_raw = join_genres(genres)


class Item(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(300), index=True)
    genres_raw: Mapped[str] = mapped_column("genres", String(500), default="")

    ratings: Mapped[list["Rating"]] = relationship(back_populates="item", cascade="all, delete-orphan")

    @property
    def genres(self) -> list[str]:
        return split_genres(self.genres_raw)

    @genres.setter
    def genres(self, genres: list[str]) -> None:
        self.genres_raw = join_genres(genres)


class Rating(Base):
    __tablename__ = "ratings"
    __table_args__ = (UniqueConstraint("user_id", "item_id", name="uq_user_item"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id", ondelete="CASCADE"), index=True)
    rating: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    user: Mapped[User] = relationship(back_populates="ratings")
    item: Mapped[Item] = relationship(back_populates="ratings")
