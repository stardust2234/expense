from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.models import Category
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


def test_seed_is_idempotent_and_preserves_existing_categories(session: Session) -> None:
    custom_housing = Category(name="Housing")
    session.add(custom_housing)
    session.commit()

    first_result = seed_categories(session)
    second_result = seed_categories(session)
    categories = session.scalars(select(Category)).all()

    assert first_result.created == 57
    assert second_result.created == 0
    assert len(categories) == 58
    assert len([category for category in categories if category.name == "Housing"]) == 1
    assert custom_housing.parent_category_id is None
