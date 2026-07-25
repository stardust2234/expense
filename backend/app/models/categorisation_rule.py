from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.category import Category
    from app.models.expense import Expense


class CategorisationRule(Base):
    __tablename__ = "categorisation_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    match_pattern: Mapped[str] = mapped_column(String(500), nullable=False)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("1"),
        index=True,
    )

    category: Mapped[Category] = relationship(back_populates="rules")
    matched_expenses: Mapped[list[Expense]] = relationship(back_populates="matched_rule")
