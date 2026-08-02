from datetime import date

import pytest

from app.services.plan_inference import (
    InsufficientPlanEvidenceError,
    TransactionEvidence,
    infer_plan,
)
from app.services.recurring_identity import normalise_payer_identity


def _evidence(
    transaction_id: int,
    transaction_date: date,
    identity: str,
    amount: int,
    *,
    category_id: int,
    category_name: str,
    root_category_name: str,
    priority: str,
    kind: str,
) -> TransactionEvidence:
    return TransactionEvidence(
        transaction_id=transaction_id,
        transaction_date=transaction_date,
        identity_key=identity,
        payer_key=normalise_payer_identity(identity.removeprefix("description:")),
        description=identity.replace("description:", "").title(),
        amount=amount,
        currency="GBP",
        category_id=category_id,
        category_code=f"category.{category_id}",
        category_name=category_name,
        root_category_code=root_category_name.casefold().replace(" ", "_"),
        root_category_name=root_category_name,
        priority=priority,
        cash_flow_kind=kind,
    )


def test_infers_income_commitments_and_variable_essential_allowance() -> None:
    evidence = (
        *(
            _evidence(
                index,
                transaction_date,
                "description:universal credit",
                amount,
                category_id=1,
                category_name="Benefits",
                root_category_name="Income",
                priority="adjustable",
                kind="income",
            )
            for index, transaction_date, amount in (
                (1, date(2026, 5, 29), 90000),
                (2, date(2026, 6, 29), 90100),
                (3, date(2026, 7, 29), 90000),
            )
        ),
        *(
            _evidence(
                index,
                transaction_date,
                "description:rent",
                amount,
                category_id=2,
                category_name="Rent",
                root_category_name="Housing",
                priority="protected",
                kind="spending",
            )
            for index, transaction_date, amount in (
                (4, date(2026, 5, 27), -50000),
                (5, date(2026, 6, 27), -50000),
                (6, date(2026, 7, 27), -50000),
            )
        ),
        _evidence(
            7,
            date(2026, 5, 8),
            "description:food shop one",
            -4500,
            category_id=3,
            category_name="Supermarkets",
            root_category_name="Groceries",
            priority="essential",
            kind="spending",
        ),
        _evidence(
            8,
            date(2026, 6, 12),
            "description:food shop two",
            -5200,
            category_id=3,
            category_name="Supermarkets",
            root_category_name="Groceries",
            priority="essential",
            kind="spending",
        ),
        _evidence(
            9,
            date(2026, 7, 18),
            "description:food shop three",
            -4800,
            category_id=3,
            category_name="Supermarkets",
            root_category_name="Groceries",
            priority="essential",
            kind="spending",
        ),
        _evidence(
            10,
            date(2026, 7, 20),
            "description:own account",
            -10000,
            category_id=4,
            category_name="Own-account transfers",
            root_category_name="Transfers",
            priority="transfer",
            kind="transfer",
        ),
    )

    preview = infer_plan(
        evidence,
        target_month=date(2026, 8, 1),
        currency="gbp",
    )

    assert preview.incomes[0].expected_amount == 90000
    assert preview.incomes[0].payment_date == date(2026, 8, 28)
    assert preview.incomes[0].nominal_payment_date == date(2026, 8, 29)
    assert preview.incomes[0].date_adjusted is True
    assert preview.incomes[0].evidence_transaction_ids == (1, 2, 3)
    assert len(preview.commitments) == 1
    assert preview.commitments[0].name == "Rent"
    assert preview.commitments[0].amount == 50000
    assert preview.commitments[0].due_date == date(2026, 8, 27)
    assert preview.commitments[0].priority == "protected"
    assert len(preview.allowances) == 1
    assert preview.allowances[0].allowance_type == "food"
    assert preview.allowances[0].amount == 4800
    assert preview.allowances[0].evidence_transaction_ids == (7, 8, 9)


def test_requires_repeated_monthly_income() -> None:
    evidence = (
        _evidence(
            1,
            date(2026, 7, 29),
            "description:benefit",
            90000,
            category_id=1,
            category_name="Benefits",
            root_category_name="Income",
            priority="adjustable",
            kind="income",
        ),
    )

    with pytest.raises(InsufficientPlanEvidenceError, match="At least two recurring"):
        infer_plan(
            evidence,
            target_month=date(2026, 8, 1),
            currency="GBP",
        )


def test_groups_changing_income_references_by_category_and_stable_pattern() -> None:
    common = {
        "category_id": 1,
        "category_name": "Benefits",
        "root_category_name": "Income",
        "priority": "transfer",
        "kind": "income",
    }
    evidence = (
        _evidence(1, date(2026, 4, 29), "description:201w94e0h dwp uc", 90014, **common),
        _evidence(2, date(2026, 5, 28), "description:202x13840 dwp uc", 92490, **common),
        _evidence(3, date(2026, 6, 24), "description:hmrc paye", 81560, **common),
        _evidence(4, date(2026, 6, 29), "description:202y23335 dwp uc", 92490, **common),
        _evidence(5, date(2026, 7, 30), "description:202y25x4b dwp uc", 92490, **common),
    )

    preview = infer_plan(evidence, target_month=date(2026, 8, 1), currency="GBP")

    assert len(preview.incomes) == 1
    assert preview.incomes[0].expected_amount == 92490
    assert preview.incomes[0].payment_date == date(2026, 8, 28)
    assert preview.incomes[0].evidence_transaction_ids == (1, 2, 4, 5)


def test_ignores_stale_recurrence_and_nets_refunds_from_allowances() -> None:
    common_income = {
        "category_id": 1,
        "category_name": "Benefits",
        "root_category_name": "Income",
        "priority": "adjustable",
        "kind": "income",
    }
    common_food = {
        "category_id": 3,
        "category_name": "Groceries",
        "root_category_name": "Groceries",
        "priority": "essential",
        "kind": "spending",
    }
    evidence = (
        _evidence(1, date(2026, 6, 29), "description:benefit", 90000, **common_income),
        _evidence(2, date(2026, 7, 29), "description:benefit", 90000, **common_income),
        *(
            _evidence(
                index,
                transaction_date,
                "description:old subscription",
                -1000,
                category_id=2,
                category_name="Subscription",
                root_category_name="Utilities",
                priority="essential",
                kind="spending",
            )
            for index, transaction_date in (
                (3, date(2026, 2, 10)),
                (4, date(2026, 3, 10)),
                (5, date(2026, 4, 10)),
            )
        ),
        _evidence(6, date(2026, 6, 5), "description:food", -5000, **common_food),
        _evidence(7, date(2026, 6, 8), "description:food refund", 1000, **common_food),
        _evidence(8, date(2026, 7, 5), "description:food", -6000, **common_food),
        _evidence(9, date(2026, 7, 8), "description:food refund", 1000, **common_food),
    )

    preview = infer_plan(evidence, target_month=date(2026, 8, 1), currency="GBP")

    assert preview.commitments == ()
    assert len(preview.allowances) == 1
    assert preview.allowances[0].amount == 4500


def test_infers_multiple_stable_income_sources() -> None:
    common = {
        "category_id": 1,
        "category_name": "Benefits",
        "root_category_name": "Income",
        "priority": "transfer",
        "kind": "income",
    }
    evidence = (
        _evidence(1, date(2026, 6, 29), "description:dwp uc", 92490, **common),
        _evidence(2, date(2026, 7, 29), "description:dwp uc", 92490, **common),
        _evidence(3, date(2026, 6, 12), "description:pip", 30000, **common),
        _evidence(4, date(2026, 7, 12), "description:pip", 30000, **common),
    )

    preview = infer_plan(evidence, target_month=date(2026, 8, 1), currency="GBP")

    assert len(preview.incomes) == 2
    assert {item.expected_amount for item in preview.incomes} == {92490, 30000}
    assert preview.impact.expected_income == 122490


def test_refund_does_not_hide_a_stable_commitment() -> None:
    income = {
        "category_id": 1,
        "category_name": "Benefits",
        "root_category_name": "Income",
        "priority": "transfer",
        "kind": "income",
    }
    bill = {
        "category_id": 2,
        "category_name": "Internet",
        "root_category_name": "Utilities",
        "priority": "essential",
        "kind": "spending",
    }
    evidence = (
        _evidence(1, date(2026, 6, 29), "description:dwp uc", 92490, **income),
        _evidence(2, date(2026, 7, 29), "description:dwp uc", 92490, **income),
        _evidence(3, date(2026, 5, 10), "description:isp", -3000, **bill),
        _evidence(4, date(2026, 6, 10), "description:isp", -3000, **bill),
        _evidence(5, date(2026, 7, 10), "description:isp", -3000, **bill),
        _evidence(6, date(2026, 7, 11), "description:isp", 500, **bill),
    )

    preview = infer_plan(evidence, target_month=date(2026, 8, 1), currency="GBP")

    assert len(preview.commitments) == 1
    assert preview.commitments[0].amount == 3000
    assert preview.commitments[0].evidence_transaction_ids == (3, 4, 5)
