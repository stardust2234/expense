from enum import Enum

from app.models import Category


class CashFlowKind(str, Enum):
    SPENDING = "spending"
    INCOME = "income"
    TRANSFER = "transfer"


def root_category_name(category: Category) -> str:
    """Return the top-level category name, guarding against malformed cycles."""
    current = category
    visited: set[int] = set()
    while current.parent is not None and current.id not in visited:
        visited.add(current.id)
        current = current.parent
    return current.name


def root_category_code(category: Category) -> str | None:
    current = category
    visited: set[int] = set()
    while current.parent is not None and current.id not in visited:
        visited.add(current.id)
        current = current.parent
    return current.code


def cash_flow_kind(category: Category) -> CashFlowKind:
    root_code = root_category_code(category)
    root_identity = root_code or root_category_name(category).casefold()
    if root_identity == "income":
        return CashFlowKind.INCOME
    if root_identity in {"transfers", "savings_and_investments", "savings and investments"}:
        return CashFlowKind.TRANSFER
    return CashFlowKind.SPENDING


def spending_contribution(amount: int, category: Category) -> int | None:
    """Convert a signed bank amount to positive net spending, excluding non-spending."""
    if cash_flow_kind(category) is not CashFlowKind.SPENDING:
        return None
    return -amount
