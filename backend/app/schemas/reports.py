from datetime import date

from pydantic import BaseModel, Field, field_validator

from app.models import OpportunityDecision, OpportunityDifficulty


class CategoryTotal(BaseModel):
    category_id: int
    category_code: str | None
    category_name: str
    currency: str
    total_amount: int
    transaction_count: int


class CategoryTotalsResponse(BaseModel):
    date_from: date | None
    date_to: date | None
    items: list[CategoryTotal]


class PriorityTotal(BaseModel):
    priority: str
    currency: str
    total_amount: int
    transaction_count: int


class PriorityReportResponse(BaseModel):
    date_from: date | None
    date_to: date | None
    items: list[PriorityTotal]


class RecurringExpense(BaseModel):
    description: str
    currency: str
    average_amount: int
    occurrence_count: int
    cadence: str
    typical_interval_days: int
    last_seen: date


class RecurringReportResponse(BaseModel):
    items: list[RecurringExpense]


class PaymentPeriod(BaseModel):
    payment_cycle_id: int
    name: str | None
    start_date: date
    end_date: date
    next_payment_date: date
    currency: str
    status: str
    income: int
    spending: int
    net: int
    transaction_count: int
    protected_spending: int
    essential_spending: int
    adjustable_spending: int
    optional_spending: int
    irregular_essential_spending: int


class PaymentPeriodReportResponse(BaseModel):
    items: list[PaymentPeriod]


class RecurringOpportunity(BaseModel):
    opportunity_id: int | None
    identity_key: str
    description: str
    currency: str
    cadence: str
    occurrence_count: int
    last_seen: date
    current_monthly_cost: int
    replacement_monthly_cost: int | None
    one_off_switching_cost: int
    monthly_saving: int | None
    first_year_saving: int | None
    difficulty: OpportunityDifficulty
    decision: OpportunityDecision
    notes: str | None


class RecurringOpportunityResponse(BaseModel):
    items: list[RecurringOpportunity]


class RecurringOpportunityWriteRequest(BaseModel):
    identity_key: str | None = Field(default=None, max_length=600)
    description: str = Field(max_length=500)
    currency: str = Field(min_length=3, max_length=3)
    current_monthly_cost: int = Field(ge=0)
    replacement_monthly_cost: int | None = Field(default=None, ge=0)
    one_off_switching_cost: int = Field(default=0, ge=0)
    difficulty: OpportunityDifficulty = OpportunityDifficulty.MODERATE
    decision: OpportunityDecision = OpportunityDecision.REVIEW
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("description")
    @classmethod
    def clean_description(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("description must not be empty")
        return cleaned

    @field_validator("currency")
    @classmethod
    def normalise_currency(cls, value: str) -> str:
        if not value.isalpha():
            raise ValueError("currency must contain three letters")
        return value.upper()


class SavedRecurringOpportunity(BaseModel):
    opportunity_id: int
    identity_key: str
    description: str
    currency: str
    current_monthly_cost: int
    replacement_monthly_cost: int | None
    one_off_switching_cost: int
    monthly_saving: int | None
    first_year_saving: int | None
    difficulty: OpportunityDifficulty
    decision: OpportunityDecision
    notes: str | None
