from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.expense import Expense
    from app.models.raw_transaction import RawTransaction


class ImportBatch(Base):
    __tablename__ = "import_batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    content_sha256: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
    )
    default_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    processing_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="queued",
        server_default="queued",
        index=True,
    )
    processing_error: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    processing_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    processing_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    total_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.current_timestamp(),
    )

    expenses: Mapped[list[Expense]] = relationship(back_populates="import_batch")
    raw_transactions: Mapped[list[RawTransaction]] = relationship(
        back_populates="import_batch",
        cascade="all, delete-orphan",
    )
