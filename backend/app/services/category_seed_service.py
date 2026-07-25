from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Category

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


@dataclass(frozen=True)
class CategorySeedResult:
    created: int
    existing: int


def seed_categories(session: Session) -> CategorySeedResult:
    """Create missing taxonomy entries without changing existing categories."""
    categories = session.scalars(select(Category).order_by(Category.id)).all()
    categories_by_name = {category.name.casefold(): category for category in categories}
    created = 0
    existing = 0

    for parent_name, child_names in CATEGORY_TAXONOMY:
        parent = categories_by_name.get(parent_name.casefold())
        if parent is None:
            parent = Category(name=parent_name)
            session.add(parent)
            session.flush()
            categories_by_name[parent_name.casefold()] = parent
            created += 1
        else:
            existing += 1

        for child_name in child_names:
            child = categories_by_name.get(child_name.casefold())
            if child is None:
                child = Category(name=child_name, parent=parent)
                session.add(child)
                session.flush()
                categories_by_name[child_name.casefold()] = child
                created += 1
            else:
                existing += 1

    session.commit()
    return CategorySeedResult(created=created, existing=existing)
