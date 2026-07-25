from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.categorisation_rule import CategorisationRule
    from app.models.expense import Expense


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    parent_category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    parent: Mapped[Category | None] = relationship(
        remote_side="Category.id",
        back_populates="children",
    )
    children: Mapped[list[Category]] = relationship(back_populates="parent")
    expenses: Mapped[list[Expense]] = relationship(back_populates="category")
    rules: Mapped[list[CategorisationRule]] = relationship(
        back_populates="category",
        cascade="all, delete-orphan",
    )
