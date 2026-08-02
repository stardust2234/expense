from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.models import Category, SpendingPriority
from app.services.category_seed_service import CATEGORY_TAXONOMY, seed_categories


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as database_session:
        yield database_session


def test_seed_creates_the_complete_hierarchy(session: Session) -> None:
    expected_count = sum(1 + len(children) for _, children in CATEGORY_TAXONOMY)

    result = seed_categories(session)

    assert result.created == expected_count
    assert result.existing == 0
    assert session.scalar(select(func.count()).select_from(Category)) == expected_count

    housing = session.scalar(select(Category).where(Category.name == "Housing"))
    rent = session.scalar(select(Category).where(Category.name == "Rent"))
    assert housing is not None
    assert rent is not None
    assert rent.parent_category_id == housing.id
    assert housing.code == "housing"
    assert rent.code == "housing.rent"
    assert housing.default_priority is SpendingPriority.PROTECTED
    assert rent.default_priority is SpendingPriority.PROTECTED
    groceries = session.scalar(select(Category).where(Category.name == "Groceries"))
    takeaway = session.scalar(select(Category).where(Category.name == "Takeaway"))
    transfers = session.scalar(select(Category).where(Category.name == "Transfers"))
    assert groceries is not None
    assert takeaway is not None
    assert transfers is not None
    assert groceries.default_priority is SpendingPriority.ESSENTIAL
    assert takeaway.default_priority is SpendingPriority.OPTIONAL
    assert transfers.default_priority is SpendingPriority.TRANSFER


def test_seed_is_idempotent_and_preserves_existing_categories(session: Session) -> None:
    expected_count = sum(1 + len(children) for _, children in CATEGORY_TAXONOMY)
    custom_housing = Category(name="Housing")
    session.add(custom_housing)
    session.commit()

    first_result = seed_categories(session)
    second_result = seed_categories(session)
    categories = session.scalars(select(Category)).all()

    assert first_result.created == expected_count - 1
    assert second_result.created == 0
    assert len(categories) == expected_count
    assert len([category for category in categories if category.name == "Housing"]) == 1
    assert custom_housing.parent_category_id is None
    assert custom_housing.default_priority is SpendingPriority.ADJUSTABLE


def test_seed_repairs_known_category_hierarchy_without_moving_custom_categories(
    session: Session,
) -> None:
    wrong_parent = Category(name="Wrong parent")
    rent = Category(name="Rent", code="housing.rent", parent=wrong_parent)
    custom = Category(name="Custom", parent=wrong_parent)
    session.add_all([rent, custom])
    session.commit()

    seed_categories(session)

    housing = session.scalar(select(Category).where(Category.code == "housing"))
    assert housing is not None
    assert rent.parent is housing
    assert custom.parent is wrong_parent
