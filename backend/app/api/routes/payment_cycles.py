from datetime import date, datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.database.session import get_database_session
from app.models import PaymentCycleStatus
from app.schemas.payment_cycles import (
    AllowanceCreateRequest,
    AllowanceForecastItem,
    AllowanceItem,
    AllowanceListResponse,
    AllowanceUpdateRequest,
    CommitmentCreateRequest,
    CommitmentItem,
    CommitmentListResponse,
    CommitmentUpdateRequest,
    PaymentCycleCreateRequest,
    PaymentCycleItem,
    PaymentCycleListResponse,
    PaymentCycleUpdateRequest,
    SafeSpendingForecastResponse,
)
from app.schemas.plan_inference import (
    InferredAllowanceItem,
    InferredCommitmentItem,
    InferredIncomeItem,
    InferredPlanImpact,
    PlanInferenceConfirmationResponse,
    PlanInferenceConfirmRequest,
    PlanInferencePreviewResponse,
)
from app.services.allowance_service import (
    AllowanceNotFoundError,
    build_cycle_forecast,
    create_allowance,
    delete_allowance,
    get_allowance,
    list_allowances,
    update_allowance,
)
from app.services.payment_cycle_service import (
    CommitmentNotFoundError,
    FinancialPlanConflictError,
    PaymentCycleNotFoundError,
    create_commitment,
    create_payment_cycle,
    delete_commitment,
    delete_payment_cycle,
    get_payment_cycle,
    list_commitments,
    list_payment_cycles,
    update_commitment,
    update_payment_cycle,
)
from app.services.plan_inference import InsufficientPlanEvidenceError
from app.services.plan_inference_service import (
    PlanProposalNotFoundError,
    confirm_inferred_plan,
    preview_inferred_plan,
)

router = APIRouter(tags=["payment cycles"])
DatabaseSession = Annotated[Session, Depends(get_database_session)]


def cycle_item(cycle) -> PaymentCycleItem:
    return PaymentCycleItem.model_validate(cycle, from_attributes=True)


def commitment_item(commitment) -> CommitmentItem:
    return CommitmentItem.model_validate(commitment, from_attributes=True)


def allowance_item(allowance) -> AllowanceItem:
    return AllowanceItem.model_validate(allowance, from_attributes=True)


def _preview_response(preview) -> PlanInferencePreviewResponse:
    return PlanInferencePreviewResponse(
        target_month=preview.target_month,
        end_date=preview.end_date,
        currency=preview.currency,
        incomes=[
            InferredIncomeItem.model_validate(item, from_attributes=True)
            for item in preview.incomes
        ],
        commitments=[
            InferredCommitmentItem.model_validate(item, from_attributes=True)
            for item in preview.commitments
        ],
        allowances=[
            InferredAllowanceItem.model_validate(item, from_attributes=True)
            for item in preview.allowances
        ],
        impact=InferredPlanImpact.model_validate(preview.impact, from_attributes=True),
    )


@router.get("/plan-inference/preview", response_model=PlanInferencePreviewResponse)
async def get_plan_inference_preview(
    session: DatabaseSession,
    target_month: date | None = None,
    currency: Annotated[str, Query(min_length=3, max_length=3)] = "GBP",
) -> PlanInferencePreviewResponse:
    effective_month = target_month or datetime.now(ZoneInfo("Europe/London")).date().replace(day=1)
    if effective_month.day != 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="target_month must be the first day of a month",
        )
    try:
        preview = preview_inferred_plan(
            session,
            target_month=effective_month,
            currency=currency.upper(),
        )
    except InsufficientPlanEvidenceError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error
    return _preview_response(preview)


@router.post(
    "/plan-inference/confirm",
    response_model=PlanInferenceConfirmationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_plan_inference_confirmation(
    request: PlanInferenceConfirmRequest,
    session: DatabaseSession,
) -> PlanInferenceConfirmationResponse:
    try:
        confirmation = confirm_inferred_plan(
            session,
            **request.model_dump(),
        )
    except (InsufficientPlanEvidenceError, PlanProposalNotFoundError) as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error
    return PlanInferenceConfirmationResponse(
        payment_cycle_id=confirmation.payment_cycle_id,
        created_cycle=confirmation.created_cycle,
        created_commitment_ids=list(confirmation.created_commitment_ids),
        updated_commitment_ids=list(confirmation.updated_commitment_ids),
        created_allowance_ids=list(confirmation.created_allowance_ids),
        updated_allowance_ids=list(confirmation.updated_allowance_ids),
    )


@router.get("/payment-cycles", response_model=PaymentCycleListResponse)
async def get_payment_cycles(
    session: DatabaseSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
    cycle_status: Annotated[PaymentCycleStatus | None, Query(alias="status")] = None,
) -> PaymentCycleListResponse:
    cycles, total = list_payment_cycles(
        session,
        limit=limit,
        offset=offset,
        status=cycle_status,
    )
    return PaymentCycleListResponse(
        items=[cycle_item(cycle) for cycle in cycles],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/payment-cycles",
    response_model=PaymentCycleItem,
    status_code=status.HTTP_201_CREATED,
)
async def post_payment_cycle(
    request: PaymentCycleCreateRequest,
    session: DatabaseSession,
) -> PaymentCycleItem:
    try:
        cycle = create_payment_cycle(session, **request.model_dump())
    except FinancialPlanConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    return cycle_item(cycle)


@router.get("/payment-cycles/{payment_cycle_id}", response_model=PaymentCycleItem)
async def get_payment_cycle_by_id(
    payment_cycle_id: int,
    session: DatabaseSession,
) -> PaymentCycleItem:
    try:
        return cycle_item(get_payment_cycle(session, payment_cycle_id))
    except PaymentCycleNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.patch("/payment-cycles/{payment_cycle_id}", response_model=PaymentCycleItem)
async def patch_payment_cycle(
    payment_cycle_id: int,
    request: PaymentCycleUpdateRequest,
    session: DatabaseSession,
) -> PaymentCycleItem:
    try:
        cycle = update_payment_cycle(
            session,
            payment_cycle_id=payment_cycle_id,
            changes=request.model_dump(exclude_unset=True),
        )
    except PaymentCycleNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except FinancialPlanConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    return cycle_item(cycle)


@router.delete("/payment-cycles/{payment_cycle_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_payment_cycle(
    payment_cycle_id: int,
    session: DatabaseSession,
) -> Response:
    try:
        delete_payment_cycle(session, payment_cycle_id=payment_cycle_id)
    except PaymentCycleNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/payment-cycles/{payment_cycle_id}/commitments",
    response_model=CommitmentListResponse,
)
async def get_commitments(
    payment_cycle_id: int,
    session: DatabaseSession,
) -> CommitmentListResponse:
    try:
        commitments = list_commitments(session, payment_cycle_id=payment_cycle_id)
    except PaymentCycleNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return CommitmentListResponse(
        items=[commitment_item(commitment) for commitment in commitments],
        total=len(commitments),
    )


@router.post(
    "/payment-cycles/{payment_cycle_id}/commitments",
    response_model=CommitmentItem,
    status_code=status.HTTP_201_CREATED,
)
async def post_commitment(
    payment_cycle_id: int,
    request: CommitmentCreateRequest,
    session: DatabaseSession,
) -> CommitmentItem:
    try:
        commitment = create_commitment(
            session,
            payment_cycle_id=payment_cycle_id,
            **request.model_dump(),
        )
    except PaymentCycleNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except FinancialPlanConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    return commitment_item(commitment)


@router.patch("/commitments/{commitment_id}", response_model=CommitmentItem)
async def patch_commitment(
    commitment_id: int,
    request: CommitmentUpdateRequest,
    session: DatabaseSession,
) -> CommitmentItem:
    try:
        commitment = update_commitment(
            session,
            commitment_id=commitment_id,
            changes=request.model_dump(exclude_unset=True),
        )
    except CommitmentNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except FinancialPlanConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    return commitment_item(commitment)


@router.delete("/commitments/{commitment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_commitment(
    commitment_id: int,
    session: DatabaseSession,
) -> Response:
    try:
        delete_commitment(session, commitment_id=commitment_id)
    except CommitmentNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/payment-cycles/{payment_cycle_id}/allowances",
    response_model=AllowanceListResponse,
)
async def get_allowances(
    payment_cycle_id: int,
    session: DatabaseSession,
) -> AllowanceListResponse:
    try:
        allowances = list_allowances(session, payment_cycle_id=payment_cycle_id)
    except PaymentCycleNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return AllowanceListResponse(
        items=[allowance_item(allowance) for allowance in allowances],
        total=len(allowances),
    )


@router.post(
    "/payment-cycles/{payment_cycle_id}/allowances",
    response_model=AllowanceItem,
    status_code=status.HTTP_201_CREATED,
)
async def post_allowance(
    payment_cycle_id: int,
    request: AllowanceCreateRequest,
    session: DatabaseSession,
) -> AllowanceItem:
    try:
        allowance = create_allowance(
            session,
            payment_cycle_id=payment_cycle_id,
            **request.model_dump(),
        )
    except PaymentCycleNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except FinancialPlanConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    return allowance_item(allowance)


@router.patch("/allowances/{allowance_id}", response_model=AllowanceItem)
async def patch_allowance(
    allowance_id: int,
    request: AllowanceUpdateRequest,
    session: DatabaseSession,
) -> AllowanceItem:
    try:
        allowance = update_allowance(
            session,
            allowance_id=allowance_id,
            changes=request.model_dump(exclude_unset=True),
        )
    except AllowanceNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except FinancialPlanConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    return allowance_item(allowance)


@router.get("/allowances/{allowance_id}", response_model=AllowanceItem)
async def get_allowance_by_id(
    allowance_id: int,
    session: DatabaseSession,
) -> AllowanceItem:
    try:
        return allowance_item(get_allowance(session, allowance_id))
    except AllowanceNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.delete("/allowances/{allowance_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_allowance(
    allowance_id: int,
    session: DatabaseSession,
) -> Response:
    try:
        delete_allowance(session, allowance_id=allowance_id)
    except AllowanceNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/payment-cycles/{payment_cycle_id}/forecast",
    response_model=SafeSpendingForecastResponse,
)
async def get_safe_spending_forecast(
    payment_cycle_id: int,
    session: DatabaseSession,
    as_of: date | None = None,
) -> SafeSpendingForecastResponse:
    try:
        built = build_cycle_forecast(
            session,
            payment_cycle_id=payment_cycle_id,
            as_of_date=as_of,
        )
    except PaymentCycleNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    forecast = built.forecast
    return SafeSpendingForecastResponse(
        payment_cycle_id=payment_cycle_id,
        as_of_date=forecast.as_of_date,
        funding_start_date=built.funding_window.start_date,
        funding_end_date=built.funding_window.end_date,
        funding_income_amount=built.funding_window.funding_amount,
        next_payment_date=forecast.next_payment_date,
        next_income_amount=built.funding_window.next_income_amount,
        currency=built.currency,
        balance_source=built.balance_source,
        usable_balance=forecast.usable_balance,
        pending_commitments=forecast.pending_commitments,
        allowance_reserves=forecast.allowance_reserves,
        safe_to_spend=forecast.safe_to_spend,
        shortfall=forecast.shortfall,
        projected_balance=forecast.projected_balance,
        days_remaining=forecast.days_remaining,
        safe_daily_amount=forecast.safe_daily_amount,
        safe_weekly_amount=forecast.safe_weekly_amount,
        essential_cost_coverage=forecast.essential_cost_coverage,
        allowances=[
            AllowanceForecastItem(
                id=allowance.id,
                name=allowance.name,
                allowance_type=allowance.allowance_type,
                priority=allowance.priority,
                amount=allowance.amount,
                spent_amount=allowance.spent_amount,
                remaining_amount=allowance.remaining_amount,
            )
            for allowance in forecast.allowances
        ],
        risks=list(forecast.risks),
    )
