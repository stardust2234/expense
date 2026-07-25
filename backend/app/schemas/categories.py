from pydantic import BaseModel, Field, field_validator

from app.models import SpendingPriority


class CategoryItem(BaseModel):
    id: int
    name: str
    parent_category_id: int | None
    default_priority: SpendingPriority


class CategoryListResponse(BaseModel):
    items: list[CategoryItem]


class CategoryWriteRequest(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    parent_category_id: int | None = Field(default=None, gt=0)
    default_priority: SpendingPriority | None = None

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("name must not be empty")
        return cleaned
