from pydantic import BaseModel, Field, field_validator


class RuleItem(BaseModel):
    id: int
    match_pattern: str
    category_id: int
    category_name: str
    priority: int
    enabled: bool
    match_count: int


class RuleListResponse(BaseModel):
    items: list[RuleItem]


class RuleUpdateRequest(BaseModel):
    match_pattern: str | None = Field(default=None, max_length=500)
    category_id: int | None = Field(default=None, gt=0)
    priority: int | None = None
    enabled: bool | None = None

    @field_validator("match_pattern")
    @classmethod
    def clean_pattern(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("match_pattern must not be empty")
        return cleaned
