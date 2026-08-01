from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Category, SpendingPriority


def category_code(parent_name: str, name: str | None = None) -> str:
    def slug(value: str) -> str:
        return "_".join(value.casefold().replace("-", " ").split())

    parent_code = slug(parent_name)
    return parent_code if name is None else f"{parent_code}.{slug(name)}"


CATEGORY_TAXONOMY: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Housing", ("Rent", "Council tax", "Repairs")),
    ("Utilities", ("Electricity", "Water", "Internet", "Mobile")),
    ("Groceries", ("Supermarkets", "Food shops")),
    ("Transport", ("Public transport", "Fuel", "Taxi", "Maintenance")),
    ("Eating out", ("Restaurants", "Takeaway", "Cafés")),
    ("Shopping", ("Clothing", "Electronics", "Household items")),
    ("Health", ("Pharmacy", "Dentist", "Healthcare")),
    ("Personal care", ("Toiletries", "Haircare", "Beauty")),
    ("Entertainment", ("Streaming", "Games", "Events")),
    ("Financial", ("Bank fees", "Loan interest", "Insurance")),
    ("Subscriptions", ("Software", "Memberships")),
    ("Savings and investments", ("ISA", "SIPP", "Savings")),
    ("Income", ("Salary", "Refunds", "Benefits")),
    ("Transfers", ("Own-account transfers", "Credit-card payments")),
    ("Other", ("Uncategorized", "Exceptional expenses")),
)

CATEGORY_PRIORITIES: dict[str, SpendingPriority] = {
    "Housing": SpendingPriority.PROTECTED,
    "Rent": SpendingPriority.PROTECTED,
    "Council tax": SpendingPriority.PROTECTED,
    "Repairs": SpendingPriority.IRREGULAR_ESSENTIAL,
    "Utilities": SpendingPriority.ADJUSTABLE,
    "Electricity": SpendingPriority.PROTECTED,
    "Water": SpendingPriority.PROTECTED,
    "Internet": SpendingPriority.ADJUSTABLE,
    "Mobile": SpendingPriority.ADJUSTABLE,
    "Groceries": SpendingPriority.ESSENTIAL,
    "Supermarkets": SpendingPriority.ESSENTIAL,
    "Food shops": SpendingPriority.ESSENTIAL,
    "Transport": SpendingPriority.ESSENTIAL,
    "Public transport": SpendingPriority.ESSENTIAL,
    "Fuel": SpendingPriority.ESSENTIAL,
    "Taxi": SpendingPriority.ADJUSTABLE,
    "Maintenance": SpendingPriority.IRREGULAR_ESSENTIAL,
    "Eating out": SpendingPriority.OPTIONAL,
    "Restaurants": SpendingPriority.OPTIONAL,
    "Takeaway": SpendingPriority.OPTIONAL,
    "Cafés": SpendingPriority.OPTIONAL,
    "Shopping": SpendingPriority.ADJUSTABLE,
    "Clothing": SpendingPriority.IRREGULAR_ESSENTIAL,
    "Electronics": SpendingPriority.OPTIONAL,
    "Household items": SpendingPriority.IRREGULAR_ESSENTIAL,
    "Health": SpendingPriority.ESSENTIAL,
    "Pharmacy": SpendingPriority.ESSENTIAL,
    "Dentist": SpendingPriority.IRREGULAR_ESSENTIAL,
    "Healthcare": SpendingPriority.ESSENTIAL,
    "Personal care": SpendingPriority.ADJUSTABLE,
    "Toiletries": SpendingPriority.ESSENTIAL,
    "Haircare": SpendingPriority.ADJUSTABLE,
    "Beauty": SpendingPriority.OPTIONAL,
    "Entertainment": SpendingPriority.OPTIONAL,
    "Streaming": SpendingPriority.OPTIONAL,
    "Games": SpendingPriority.OPTIONAL,
    "Events": SpendingPriority.OPTIONAL,
    "Financial": SpendingPriority.ADJUSTABLE,
    "Bank fees": SpendingPriority.ADJUSTABLE,
    "Loan interest": SpendingPriority.PROTECTED,
    "Insurance": SpendingPriority.ADJUSTABLE,
    "Subscriptions": SpendingPriority.OPTIONAL,
    "Software": SpendingPriority.OPTIONAL,
    "Memberships": SpendingPriority.OPTIONAL,
    "Savings and investments": SpendingPriority.TRANSFER,
    "ISA": SpendingPriority.TRANSFER,
    "SIPP": SpendingPriority.TRANSFER,
    "Savings": SpendingPriority.TRANSFER,
    "Income": SpendingPriority.TRANSFER,
    "Salary": SpendingPriority.TRANSFER,
    "Refunds": SpendingPriority.TRANSFER,
    "Benefits": SpendingPriority.TRANSFER,
    "Transfers": SpendingPriority.TRANSFER,
    "Own-account transfers": SpendingPriority.TRANSFER,
    "Credit-card payments": SpendingPriority.TRANSFER,
    "Other": SpendingPriority.ADJUSTABLE,
    "Uncategorized": SpendingPriority.ADJUSTABLE,
    "Exceptional expenses": SpendingPriority.ADJUSTABLE,
}


@dataclass(frozen=True)
class CategorySeedResult:
    created: int
    existing: int


def seed_categories(session: Session, *, commit: bool = True) -> CategorySeedResult:
    """Create missing taxonomy entries without changing existing categories."""
    categories = session.scalars(select(Category).order_by(Category.id)).all()
    categories_by_name = {category.name.casefold(): category for category in categories}
    created = 0
    existing = 0

    for parent_name, child_names in CATEGORY_TAXONOMY:
        parent = categories_by_name.get(parent_name.casefold())
        if parent is None:
            parent = Category(
                code=category_code(parent_name),
                name=parent_name,
                default_priority=CATEGORY_PRIORITIES[parent_name],
            )
            session.add(parent)
            session.flush()
            categories_by_name[parent_name.casefold()] = parent
            created += 1
        else:
            if parent.code is None:
                parent.code = category_code(parent_name)
            if parent.code == category_code(parent_name) and parent.parent_category_id is not None:
                parent.parent = None
            existing += 1

        for child_name in child_names:
            child = categories_by_name.get(child_name.casefold())
            if child is None:
                child = Category(
                    code=category_code(parent_name, child_name),
                    name=child_name,
                    parent=parent,
                    default_priority=CATEGORY_PRIORITIES[child_name],
                )
                session.add(child)
                session.flush()
                categories_by_name[child_name.casefold()] = child
                created += 1
            else:
                expected_code = category_code(parent_name, child_name)
                if child.code is None:
                    child.code = expected_code
                if child.code == expected_code and child.parent is not parent:
                    child.parent = parent
                existing += 1

    if commit:
        session.commit()
    else:
        session.flush()
    return CategorySeedResult(created=created, existing=existing)
