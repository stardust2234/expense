from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    CategorisationRule,
    Expense,
    Merchant,
    RawTransaction,
    TransactionStatus,
)
from app.services.matching import (
    MerchantCandidate,
    RuleCandidate,
    evaluate_rules,
    identify_merchant,
)
from app.services.transaction_normaliser import NormalisationError, normalise_transaction


@dataclass(frozen=True)
class NormalisationResult:
    normalised: int
    failed: int


@dataclass(frozen=True)
class CategorisationResult:
    categorised: int
    needs_review: int


def normalise_pending_transactions(
    session: Session,
    *,
    default_currency: str | None = None,
    import_batch_id: int | None = None,
    retry_failed: bool = False,
) -> NormalisationResult:
    statement = select(RawTransaction).where(~RawTransaction.expense.has())
    if not retry_failed:
        statement = statement.where(RawTransaction.normalisation_error.is_(None))
    statement = statement.order_by(RawTransaction.id)
    if import_batch_id is not None:
        statement = statement.where(RawTransaction.import_batch_id == import_batch_id)
    pending = session.scalars(statement).all()

    normalised_count = 0
    failed_count = 0
    for raw_transaction in pending:
        try:
            values = normalise_transaction(
                raw_transaction.raw_data,
                default_currency=default_currency,
            )
        except NormalisationError as error:
            raw_transaction.normalisation_error = str(error)
            failed_count += 1
            continue

        session.add(
            Expense(
                transaction_date=values.transaction_date,
                description=values.description,
                normalised_description=values.normalised_description,
                amount=values.amount,
                currency=values.currency,
                import_batch=raw_transaction.import_batch,
                raw_transaction=raw_transaction,
                status=TransactionStatus.NORMALISED,
            )
        )
        raw_transaction.normalisation_error = None
        normalised_count += 1

    session.commit()
    return NormalisationResult(normalised=normalised_count, failed=failed_count)


def categorise_normalised_transactions(
    session: Session,
    *,
    confidence_threshold: Decimal = Decimal("0.9000"),
    import_batch_id: int | None = None,
) -> CategorisationResult:
    if not Decimal(0) <= confidence_threshold <= Decimal(1):
        raise ValueError("confidence_threshold must be between 0 and 1")

    expense_statement = (
        select(Expense).where(Expense.status == TransactionStatus.NORMALISED).order_by(Expense.id)
    )
    if import_batch_id is not None:
        expense_statement = expense_statement.where(Expense.import_batch_id == import_batch_id)
    expenses = session.scalars(expense_statement).all()
    merchants = session.scalars(
        select(Merchant).options(selectinload(Merchant.aliases)).order_by(Merchant.id)
    ).all()
    rules = session.scalars(
        select(CategorisationRule)
        .where(CategorisationRule.enabled.is_(True))
        .order_by(CategorisationRule.priority.desc(), CategorisationRule.id)
    ).all()

    merchant_by_id = {merchant.id: merchant for merchant in merchants}
    rule_by_id = {rule.id: rule for rule in rules}
    merchant_candidates = [
        MerchantCandidate(
            id=merchant.id,
            name=merchant.name,
            aliases=tuple(alias.pattern for alias in merchant.aliases),
        )
        for merchant in merchants
    ]
    rule_candidates = [
        RuleCandidate(
            id=rule.id,
            match_pattern=rule.match_pattern,
            category_id=rule.category_id,
            priority=rule.priority,
        )
        for rule in rules
    ]

    categorised_count = 0
    review_count = 0
    for expense in expenses:
        merchant_match = identify_merchant(expense.normalised_description, merchant_candidates)
        if merchant_match is not None and merchant_match.confidence >= confidence_threshold:
            expense.merchant = merchant_by_id[merchant_match.merchant_id]

        rule_match = evaluate_rules(expense.normalised_description, rule_candidates)
        if rule_match is not None and rule_match.confidence >= confidence_threshold:
            rule = rule_by_id[rule_match.rule_id]
            expense.category = rule.category
            expense.matched_rule = rule
            expense.categorisation_source = "rule"
            expense.confidence_score = rule_match.confidence
            expense.status = TransactionStatus.CATEGORISED
            categorised_count += 1
        else:
            expense.status = TransactionStatus.NEEDS_REVIEW
            review_count += 1

    session.commit()
    return CategorisationResult(
        categorised=categorised_count,
        needs_review=review_count,
    )
