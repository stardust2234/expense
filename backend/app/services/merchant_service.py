from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import Expense, Merchant, MerchantAlias, RecurringCostOpportunity
from app.services.recurring_identity import merchant_identity


class MerchantNotFoundError(LookupError):
    pass


class MerchantConflictError(ValueError):
    pass


def list_merchants(session: Session) -> list[Merchant]:
    return list(
        session.scalars(
            select(Merchant)
            .options(selectinload(Merchant.aliases))
            .order_by(Merchant.name.collate("NOCASE"), Merchant.id)
        ).all()
    )


def create_merchant(
    session: Session,
    *,
    name: str,
    aliases: list[str],
) -> Merchant:
    if session.scalar(select(Merchant.id).where(func.lower(Merchant.name) == name.lower())):
        raise MerchantConflictError(f"Merchant {name!r} already exists")
    _ensure_aliases_available(session, aliases)

    merchant = Merchant(
        name=name,
        aliases=[MerchantAlias(pattern=pattern) for pattern in aliases],
    )
    session.add(merchant)
    session.commit()
    session.refresh(merchant)
    return merchant


def add_merchant_alias(
    session: Session,
    *,
    merchant_id: int,
    pattern: str,
) -> MerchantAlias:
    merchant = session.get(Merchant, merchant_id)
    if merchant is None:
        raise MerchantNotFoundError(f"Merchant {merchant_id} was not found")
    _ensure_aliases_available(session, [pattern])

    alias = MerchantAlias(merchant=merchant, pattern=pattern)
    session.add(alias)
    session.commit()
    session.refresh(alias)
    return alias


def delete_merchant_alias(
    session: Session,
    *,
    merchant_id: int,
    alias_id: int,
) -> None:
    alias = session.get(MerchantAlias, alias_id)
    if alias is None or alias.merchant_id != merchant_id:
        raise MerchantNotFoundError(f"Alias {alias_id} was not found for merchant {merchant_id}")
    session.delete(alias)
    session.commit()


def merge_merchants(
    session: Session,
    *,
    target_merchant_id: int,
    source_merchant_id: int,
) -> Merchant:
    if target_merchant_id == source_merchant_id:
        raise MerchantConflictError("Source and target merchants must be different")
    target = session.get(Merchant, target_merchant_id)
    source = session.get(Merchant, source_merchant_id)
    if target is None or source is None:
        raise MerchantNotFoundError("Source or target merchant was not found")

    existing_patterns = {alias.pattern.casefold() for alias in target.aliases}
    for alias in list(source.aliases):
        if alias.pattern.casefold() in existing_patterns:
            session.delete(alias)
        else:
            alias.merchant = target
            existing_patterns.add(alias.pattern.casefold())

    for expense in session.scalars(select(Expense).where(Expense.merchant_id == source.id)).all():
        expense.merchant = target
    source_identity = merchant_identity(source.id)
    target_identity = merchant_identity(target.id)
    source_opportunities = session.scalars(
        select(RecurringCostOpportunity).where(
            RecurringCostOpportunity.identity_key == source_identity
        )
    ).all()
    target_currencies = set(
        session.scalars(
            select(RecurringCostOpportunity.currency).where(
                RecurringCostOpportunity.identity_key == target_identity
            )
        ).all()
    )
    for opportunity in source_opportunities:
        if opportunity.currency in target_currencies:
            session.delete(opportunity)
        else:
            opportunity.identity_key = target_identity
            opportunity.description = target.name
            target_currencies.add(opportunity.currency)
    session.delete(source)
    session.commit()
    return target


def _ensure_aliases_available(session: Session, aliases: list[str]) -> None:
    for pattern in aliases:
        existing = session.scalar(
            select(MerchantAlias.id).where(func.lower(MerchantAlias.pattern) == pattern.lower())
        )
        if existing is not None:
            raise MerchantConflictError(f"Alias {pattern!r} already exists")
