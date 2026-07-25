from pydantic import BaseModel

from app.schemas.reports import CategoryTotal


class DashboardSummary(BaseModel):
    month: str
    spending: int
    income: int
    net: int
    currency: str
    review_count: int
    transaction_count: int
    category_totals: list[CategoryTotal]
