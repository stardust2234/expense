from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.expense import Expense
    from app.models.import_batch import ImportBatch


class RawTransaction(Base):
    __tablename__ = "raw_transactions"
    __table_args__ = (
        UniqueConstraint(
            "import_batch_id",
            "source_row_number",
            name="uq_raw_transactions_batch_row",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    import_batch_id: Mapped[int] = mapped_column(
        ForeignKey("import_batches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_data: Mapped[dict[str, str | None]] = mapped_column(JSON, nullable=False)
    normalisation_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.current_timestamp(),
    )

    import_batch: Mapped[ImportBatch] = relationship(back_populates="raw_transactions")
    expense: Mapped[Expense | None] = relationship(back_populates="raw_transaction")
