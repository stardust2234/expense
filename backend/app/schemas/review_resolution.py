from pydantic import BaseModel, Field, field_validator

from app.models import TransactionStatus


class ReviewResolutionRequest(BaseModel):
    category_id: int = Field(gt=0)
    save_rule: bool = True
    match_pattern: str | None = Field(default=None, max_length=500)
    priority: int = 0

    @field_validator("match_pattern")
    @classmethod
    def clean_match_pattern(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("match_pattern must not be empty")
        return cleaned


class ReviewResolutionResponse(BaseModel):
    expense_id: int
    category_id: int
    rule_id: int | None
    status: TransactionStatus
