from decimal import Decimal

from app.models import CategorisationRule, Category, Expense, TransactionStatus


def apply_manual_category(
    expenses: list[Expense],
    *,
    category: Category,
    matched_rule: CategorisationRule | None = None,
) -> None:
    """Apply the shared manual categorisation state without committing."""
    for expense in expenses:
        expense.category = category
        expense.matched_rule = matched_rule
        expense.categorisation_source = "manual"
        expense.confidence_score = Decimal("1.0000")
        expense.status = TransactionStatus.CATEGORISED
