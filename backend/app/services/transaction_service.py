from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import Category, Expense, Merchant, TransactionStatus
from app.services.commitment_reconciliation import reconcile_pending_commitments
from app.services.manual_categorisation_service import apply_manual_category


class TransactionConflictError(ValueError):
    pass


@dataclass(frozen=True)
class TransactionPage:
    items: list[Expense]
    total: int


def list_transactions(
    session: Session,
    *,
    search: str | None,
    status: TransactionStatus | None,
    category_id: int | None,
    merchant_id: int | None,
    import_batch_id: int | None,
    currency: str | None,
    date_from: date | None,
    date_to: date | None,
    limit: int,
    offset: int,
) -> TransactionPage:
    filters = []
    if search:
        pattern = f"%{search.strip()}%"
        filters.append(
            or_(
                Expense.description.ilike(pattern),
                Expense.normalised_description.ilike(pattern),
                Expense.merchant.has(Merchant.name.ilike(pattern)),
            )
        )
    if status:
        filters.append(Expense.status == status)
    if category_id:
        filters.append(Expense.category_id == category_id)
    if merchant_id:
        filters.append(Expense.merchant_id == merchant_id)
    if import_batch_id:
        filters.append(Expense.import_batch_id == import_batch_id)
    if currency:
        filters.append(Expense.currency == currency.upper())
    if date_from:
        filters.append(Expense.transaction_date >= date_from)
    if date_to:
        filters.append(Expense.transaction_date <= date_to)

    total = session.scalar(select(func.count()).select_from(Expense).where(*filters)) or 0
    items = session.scalars(
        select(Expense)
        .where(*filters)
        .options(selectinload(Expense.merchant), selectinload(Expense.category))
        .order_by(Expense.transaction_date.desc(), Expense.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return TransactionPage(items=list(items), total=total)


def bulk_assign_category(
    session: Session,
    *,
    transaction_ids: list[int],
    category_id: int,
) -> int:
    category = session.get(Category, category_id)
    if category is None:
        raise TransactionConflictError(f"Category {category_id} was not found")

    expenses = session.scalars(select(Expense).where(Expense.id.in_(transaction_ids))).all()
    if len(expenses) != len(set(transaction_ids)):
        raise TransactionConflictError("One or more transactions were not found")

    apply_manual_category(list(expenses), category=category)
    cycle_ids = {expense.payment_cycle_id for expense in expenses if expense.payment_cycle_id}
    for cycle_id in cycle_ids:
        reconcile_pending_commitments(session, payment_cycle_id=cycle_id)
    session.commit()
    return len(expenses)
