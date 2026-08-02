from datetime import date

from pydantic import BaseModel, Field, field_validator


class InferredIncomeItem(BaseModel):
    proposal_id: str
    identity_key: str
    description: str
    expected_amount: int
    nominal_payment_date: date
    payment_date: date
    date_adjusted: bool
    occurrence_count: int
    confidence: float
    evidence_transaction_ids: list[int]
    state: str


class InferredCommitmentItem(BaseModel):
    proposal_id: str
    identity_key: str
    name: str
    amount: int
    due_date: date
    category_id: int
    category_name: str
    priority: str
    recurrence: str
    occurrence_count: int
    confidence: float
    evidence_transaction_ids: list[int]
    state: str
    existing_id: int | None


class InferredAllowanceItem(BaseModel):
    proposal_id: str
    identity_key: str
    name: str
    allowance_type: str
    amount: int
    category_id: int
    category_name: str
    priority: str
    months_observed: int
    confidence: float
    evidence_transaction_ids: list[int]
    state: str
    existing_id: int | None


class InferredPlanImpact(BaseModel):
    expected_income: int
    commitments: int
    essential_allowances: int
    net_before_balance: int
    period_days: int


class PlanInferencePreviewResponse(BaseModel):
    target_month: date
    end_date: date
    currency: str
    incomes: list[InferredIncomeItem]
    commitments: list[InferredCommitmentItem]
    allowances: list[InferredAllowanceItem]
    impact: InferredPlanImpact


class PlanInferenceConfirmRequest(BaseModel):
    target_month: date
    currency: str = Field(default="GBP", min_length=3, max_length=3)
    opening_balance: int
    current_balance: int | None = None
    income_proposal_ids: list[str] = Field(default_factory=list)
    commitment_proposal_ids: list[str] = Field(default_factory=list)
    allowance_proposal_ids: list[str] = Field(default_factory=list)

    @field_validator("target_month")
    @classmethod
    def require_first_of_month(cls, value: date) -> date:
        if value.day != 1:
            raise ValueError("target_month must be the first day of a month")
        return value

    @field_validator("currency")
    @classmethod
    def normalise_currency(cls, value: str) -> str:
        if not value.isalpha():
            raise ValueError("currency must contain three letters")
        return value.upper()


class PlanInferenceConfirmationResponse(BaseModel):
    payment_cycle_id: int
    created_cycle: bool
    created_commitment_ids: list[int]
    updated_commitment_ids: list[int]
    created_allowance_ids: list[int]
    updated_allowance_ids: list[int]
