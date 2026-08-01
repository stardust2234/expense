from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.workspace_owned import WorkspaceOwned

if TYPE_CHECKING:
    from app.models.expense import Expense
    from app.models.merchant_alias import MerchantAlias


class Merchant(WorkspaceOwned, Base):
    __tablename__ = "merchants"
    __table_args__ = (UniqueConstraint("workspace_id", "name", name="uq_merchants_workspace_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.current_timestamp(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    expenses: Mapped[list[Expense]] = relationship(back_populates="merchant")
    aliases: Mapped[list[MerchantAlias]] = relationship(
        back_populates="merchant",
        cascade="all, delete-orphan",
        order_by="MerchantAlias.pattern",
    )
