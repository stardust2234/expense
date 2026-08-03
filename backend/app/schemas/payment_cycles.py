from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models import AllowanceType, CommitmentStatus, PaymentCycleStatus, SpendingPriority


class PaymentCycleCreateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    next_payment_date: date
    expected_income_amount: int = Field(ge=0)
    currency: str = Field(default="GBP", min_length=3, max_length=3)
    opening_balance: int
    current_balance: int | None = None
    status: PaymentCycleStatus = PaymentCycleStatus.PLANNED

    @field_validator("name")
    @classmethod
    def clean_optional_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.split())
        return cleaned or None

    @field_validator("currency")
    @classmethod
    def normalise_currency(cls, value: str) -> str:
        if not value.isalpha():
            raise ValueError("currency must contain three letters")
        return value.upper()


class PaymentCycleUpdateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    next_payment_date: date | None = None
    expected_income_amount: int | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    opening_balance: int | None = None
    current_balance: int | None = None
    status: PaymentCycleStatus | None = None

    @model_validator(mode="after")
    def reject_null_required_fields(self) -> "PaymentCycleUpdateRequest":
        for field in self.model_fields_set - {"name", "current_balance"}:
            if getattr(self, field) is None:
                raise ValueError(f"{field} must not be null")
        return self

    @field_validator("name")
    @classmethod
    def clean_optional_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.split())
        return cleaned or None

    @field_validator("currency")
    @classmethod
    def normalise_currency(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not value.isalpha():
            raise ValueError("currency must contain three letters")
        return value.upper()


class PaymentCycleItem(BaseModel):
    id: int
    name: str | None
    start_date: date
    end_date: date
    next_payment_date: date
    expected_income_amount: int
    currency: str
    opening_balance: int
    current_balance: int | None
    status: PaymentCycleStatus
    created_at: datetime
    updated_at: datetime


class PaymentCycleListResponse(BaseModel):
    items: list[PaymentCycleItem]
    total: int
    limit: int
    offset: int


class CommitmentCreateRequest(BaseModel):
    name: str = Field(max_length=150)
    amount: int = Field(ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    due_date: date
    priority: SpendingPriority = SpendingPriority.PROTECTED
    category_id: int | None = Field(default=None, gt=0)
    status: CommitmentStatus = CommitmentStatus.PENDING
    recurrence: str | None = Field(default=None, max_length=50)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("name must not be empty")
        return cleaned

    @field_validator("currency")
    @classmethod
    def normalise_currency(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not value.isalpha():
            raise ValueError("currency must contain three letters")
        return value.upper()

    @field_validator("recurrence")
    @classmethod
    def clean_recurrence(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.split())
        return cleaned or None


class CommitmentUpdateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=150)
    amount: int | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    due_date: date | None = None
    priority: SpendingPriority | None = None
    category_id: int | None = Field(default=None, gt=0)
    status: CommitmentStatus | None = None
    recurrence: str | None = Field(default=None, max_length=50)

    @model_validator(mode="after")
    def reject_null_required_fields(self) -> "CommitmentUpdateRequest":
        for field in self.model_fields_set - {"category_id", "recurrence"}:
            if getattr(self, field) is None:
                raise ValueError(f"{field} must not be null")
        return self

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("name must not be empty")
        return cleaned

    @field_validator("currency")
    @classmethod
    def normalise_currency(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not value.isalpha():
            raise ValueError("currency must contain three letters")
        return value.upper()

    @field_validator("recurrence")
    @classmethod
    def clean_recurrence(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.split())
        return cleaned or None


class CommitmentItem(BaseModel):
    id: int
    payment_cycle_id: int
    funding_payment_date: date
    name: str
    amount: int
    currency: str
    due_date: date
    priority: SpendingPriority
    category_id: int | None
    status: CommitmentStatus
    recurrence: str | None
    matched_expense_id: int | None
    created_at: datetime
    updated_at: datetime


class CommitmentListResponse(BaseModel):
    items: list[CommitmentItem]
    total: int


class AllowanceCreateRequest(BaseModel):
    name: str = Field(max_length=100)
    allowance_type: AllowanceType
    amount: int = Field(ge=0)
    priority: SpendingPriority = SpendingPriority.ESSENTIAL
    category_id: int | None = Field(default=None, gt=0)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("name must not be empty")
        return cleaned


class AllowanceUpdateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    allowance_type: AllowanceType | None = None
    amount: int | None = Field(default=None, ge=0)
    priority: SpendingPriority | None = None
    category_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def reject_null_required_fields(self) -> "AllowanceUpdateRequest":
        for field in self.model_fields_set - {"category_id"}:
            if getattr(self, field) is None:
                raise ValueError(f"{field} must not be null")
        return self

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("name must not be empty")
        return cleaned


class AllowanceItem(BaseModel):
    id: int
    payment_cycle_id: int
    name: str
    allowance_type: AllowanceType
    amount: int
    priority: SpendingPriority
    category_id: int | None


class AllowanceListResponse(BaseModel):
    items: list[AllowanceItem]
    total: int


class AllowanceForecastItem(BaseModel):
    id: int
    name: str
    allowance_type: AllowanceType
    priority: SpendingPriority
    amount: int
    spent_amount: int
    remaining_amount: int


class SafeSpendingForecastResponse(BaseModel):
    payment_cycle_id: int
    as_of_date: date
    funding_start_date: date
    funding_end_date: date
    funding_income_amount: int
    next_payment_date: date
    next_income_amount: int
    currency: str
    balance_source: str
    usable_balance: int
    pending_commitments: int
    allowance_reserves: int
    safe_to_spend: int
    shortfall: int
    projected_balance: int
    days_remaining: int
    safe_daily_amount: int
    safe_weekly_amount: int
    essential_cost_coverage: float | None
    allowances: list[AllowanceForecastItem]
    risks: list[str]
