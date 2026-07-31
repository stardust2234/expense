from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import CategorisationRule, Category, Expense, TransactionStatus
from app.services.commitment_reconciliation import reconcile_pending_commitments
from app.services.manual_categorisation_service import apply_manual_category


class ExpenseNotFoundError(LookupError):
    pass


class CategoryNotFoundError(LookupError):
    pass


class ExpenseNotReviewableError(ValueError):
    pass


@dataclass(frozen=True)
class ReviewResolution:
    expense_id: int
    category_id: int
    rule_id: int | None
    status: TransactionStatus


def resolve_review(
    session: Session,
    *,
    expense_id: int,
    category_id: int,
    save_rule: bool,
    match_pattern: str | None,
    priority: int,
) -> ReviewResolution:
    expense = session.get(Expense, expense_id)
    if expense is None:
        raise ExpenseNotFoundError(f"Expense {expense_id} was not found")
    if expense.status != TransactionStatus.NEEDS_REVIEW:
        raise ExpenseNotReviewableError(f"Expense {expense_id} is not awaiting review")

    category = session.get(Category, category_id)
    if category is None:
        raise CategoryNotFoundError(f"Category {category_id} was not found")

    rule: CategorisationRule | None = None
    if save_rule:
        pattern = match_pattern or (
            expense.merchant.name if expense.merchant else expense.normalised_description
        )
        pattern = " ".join(pattern.split())
        if not pattern:
            raise ValueError("A non-empty match pattern is required to save a rule")
        rule = session.scalar(
            select(CategorisationRule)
            .where(func.upper(CategorisationRule.match_pattern) == pattern.upper())
            .order_by(CategorisationRule.id)
        )
        if rule is None:
            rule = CategorisationRule(match_pattern=pattern)
            session.add(rule)
        rule.category = category
        rule.priority = priority
        rule.enabled = True

    apply_manual_category([expense], category=category, matched_rule=rule)
    reconcile_pending_commitments(
        session,
        payment_cycle_id=expense.payment_cycle_id,
    )
    session.commit()

    return ReviewResolution(
        expense_id=expense.id,
        category_id=category.id,
        rule_id=rule.id if rule else None,
        status=expense.status,
    )
