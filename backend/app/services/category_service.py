from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Category


def list_categories(session: Session) -> list[Category]:
    return list(
        session.scalars(
            select(Category).order_by(Category.name.collate("NOCASE"), Category.id)
        ).all()
    )


class CategoryNotFoundError(LookupError):
    pass


class CategoryConflictError(ValueError):
    pass


def create_category(
    session: Session,
    *,
    name: str,
    parent_category_id: int | None,
) -> Category:
    _ensure_name_available(session, name)
    parent = _get_parent(session, parent_category_id)
    category = Category(name=name, parent=parent)
    session.add(category)
    session.commit()
    return category


def update_category(
    session: Session,
    *,
    category_id: int,
    name: str | None,
    parent_category_id: int | None,
    parent_supplied: bool,
) -> Category:
    category = session.get(Category, category_id)
    if category is None:
        raise CategoryNotFoundError(f"Category {category_id} was not found")
    if name is not None and name.casefold() != category.name.casefold():
        _ensure_name_available(session, name)
        category.name = name
    if parent_supplied:
        if parent_category_id == category_id:
            raise CategoryConflictError("A category cannot be its own parent")
        parent = _get_parent(session, parent_category_id)
        ancestor = parent
        while ancestor is not None:
            if ancestor.id == category_id:
                raise CategoryConflictError("Category hierarchy cannot contain a cycle")
            ancestor = ancestor.parent
        category.parent = parent
    session.commit()
    return category


def delete_category(session: Session, *, category_id: int) -> None:
    category = session.get(Category, category_id)
    if category is None:
        raise CategoryNotFoundError(f"Category {category_id} was not found")
    if category.children or category.expenses or category.rules:
        raise CategoryConflictError("Category is in use and cannot be deleted")
    session.delete(category)
    session.commit()


def _get_parent(session: Session, parent_category_id: int | None) -> Category | None:
    if parent_category_id is None:
        return None
    parent = session.get(Category, parent_category_id)
    if parent is None:
        raise CategoryConflictError(f"Parent category {parent_category_id} was not found")
    return parent


def _ensure_name_available(session: Session, name: str) -> None:
    existing = session.scalar(select(Category.id).where(func.lower(Category.name) == name.lower()))
    if existing is not None:
        raise CategoryConflictError(f"Category {name!r} already exists")
