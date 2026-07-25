from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import Expense, RawTransaction, TransactionStatus


@dataclass(frozen=True)
class ReviewQueuePage:
    items: list[Expense]
    total: int


def get_review_queue(
    session: Session,
    *,
    limit: int,
    offset: int,
) -> ReviewQueuePage:
    queue_filter = Expense.status == TransactionStatus.NEEDS_REVIEW
    total = session.scalar(select(func.count()).select_from(Expense).where(queue_filter))
    items = session.scalars(
        select(Expense)
        .where(queue_filter)
        .options(
            selectinload(Expense.merchant),
            selectinload(Expense.category),
            selectinload(Expense.raw_transaction).selectinload(RawTransaction.import_batch),
        )
        .order_by(Expense.created_at, Expense.id)
        .offset(offset)
        .limit(limit)
    ).all()
    return ReviewQueuePage(items=list(items), total=total or 0)
