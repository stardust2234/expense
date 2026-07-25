from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import ImportBatch, TransactionStatus


class ImportBatchNotFoundError(LookupError):
    pass


class ImportBatchConflictError(ValueError):
    pass


@dataclass(frozen=True)
class ImportBatchPage:
    items: list[ImportBatch]
    total: int


def list_import_batches(
    session: Session,
    *,
    limit: int,
    offset: int,
) -> ImportBatchPage:
    total = session.scalar(select(func.count()).select_from(ImportBatch)) or 0
    items = session.scalars(
        select(ImportBatch)
        .options(
            selectinload(ImportBatch.raw_transactions),
            selectinload(ImportBatch.expenses),
        )
        .execution_options(populate_existing=True)
        .order_by(ImportBatch.imported_at.desc(), ImportBatch.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return ImportBatchPage(items=list(items), total=total)


def get_import_batch(session: Session, *, batch_id: int) -> ImportBatch:
    batch = session.scalar(
        select(ImportBatch)
        .where(ImportBatch.id == batch_id)
        .options(
            selectinload(ImportBatch.raw_transactions),
            selectinload(ImportBatch.expenses),
        )
        .execution_options(populate_existing=True)
    )
    if batch is None:
        raise ImportBatchNotFoundError(f"Import batch {batch_id} was not found")
    return batch


def find_duplicate_batch(session: Session, *, content_sha256: str) -> ImportBatch | None:
    return session.scalar(
        select(ImportBatch)
        .where(ImportBatch.content_sha256 == content_sha256)
        .order_by(ImportBatch.id)
    )


def batch_counts(batch: ImportBatch) -> tuple[int, int, int, int]:
    failed = sum(row.normalisation_error is not None for row in batch.raw_transactions)
    normalised = len(batch.expenses)
    categorised = sum(expense.status is TransactionStatus.CATEGORISED for expense in batch.expenses)
    needs_review = sum(
        expense.status is TransactionStatus.NEEDS_REVIEW for expense in batch.expenses
    )
    return normalised, failed, categorised, needs_review


def batch_status(batch: ImportBatch) -> str:
    return batch.processing_status
