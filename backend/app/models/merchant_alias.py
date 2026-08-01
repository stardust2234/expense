from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.workspace_owned import WorkspaceOwned

if TYPE_CHECKING:
    from app.models.merchant import Merchant


class MerchantAlias(WorkspaceOwned, Base):
    __tablename__ = "merchant_aliases"
    __table_args__ = (
        UniqueConstraint("workspace_id", "pattern", name="uq_aliases_workspace_pattern"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(
        ForeignKey("merchants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    pattern: Mapped[str] = mapped_column(String(200), nullable=False)

    merchant: Mapped[Merchant] = relationship(back_populates="aliases")
