from datetime import date

from pydantic import BaseModel


class CategoryTotal(BaseModel):
    category_id: int
    category_name: str
    currency: str
    total_amount: int
    transaction_count: int


class CategoryTotalsResponse(BaseModel):
    date_from: date | None
    date_to: date | None
    items: list[CategoryTotal]


class MonthlyTotal(BaseModel):
    month: str
    currency: str
    total_amount: int
    transaction_count: int


class MonthlyReportResponse(BaseModel):
    date_from: date | None
    date_to: date | None
    items: list[MonthlyTotal]


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
