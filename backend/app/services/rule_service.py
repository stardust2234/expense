from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import CategorisationRule, Category, Expense


class RuleNotFoundError(LookupError):
    pass


class RuleConflictError(ValueError):
    pass


def list_rules(session: Session) -> list[tuple[CategorisationRule, int]]:
    counts = (
        select(Expense.matched_rule_id, func.count(Expense.id).label("match_count"))
        .where(Expense.matched_rule_id.is_not(None))
        .group_by(Expense.matched_rule_id)
        .subquery()
    )
    rows = session.execute(
        select(CategorisationRule, func.coalesce(counts.c.match_count, 0))
        .outerjoin(counts, counts.c.matched_rule_id == CategorisationRule.id)
        .options(selectinload(CategorisationRule.category))
        .order_by(CategorisationRule.priority.desc(), CategorisationRule.id)
    ).all()
    return [(rule, count) for rule, count in rows]


def update_rule(
    session: Session,
    *,
    rule_id: int,
    match_pattern: str | None,
    category_id: int | None,
    priority: int | None,
    enabled: bool | None,
) -> CategorisationRule:
    rule = session.get(CategorisationRule, rule_id)
    if rule is None:
        raise RuleNotFoundError(f"Rule {rule_id} was not found")
    if category_id is not None:
        category = session.get(Category, category_id)
        if category is None:
            raise RuleConflictError(f"Category {category_id} was not found")
        rule.category = category
    if match_pattern is not None:
        rule.match_pattern = match_pattern
    if priority is not None:
        rule.priority = priority
    if enabled is not None:
        rule.enabled = enabled
    session.commit()
    return rule


def delete_rule(session: Session, *, rule_id: int) -> None:
    rule = session.get(CategorisationRule, rule_id)
    if rule is None:
        raise RuleNotFoundError(f"Rule {rule_id} was not found")
    session.delete(rule)
    session.commit()
