from pydantic import BaseModel, Field, field_validator


def _clean_text(value: str) -> str:
    cleaned = " ".join(value.split())
    if not cleaned:
        raise ValueError("must not be empty")
    return cleaned


class MerchantAliasItem(BaseModel):
    id: int
    pattern: str


class MerchantItem(BaseModel):
    id: int
    name: str
    aliases: list[MerchantAliasItem]


class MerchantListResponse(BaseModel):
    items: list[MerchantItem]


class MerchantCreateRequest(BaseModel):
    name: str = Field(max_length=200)
    aliases: list[str] = Field(default_factory=list, max_length=50)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return _clean_text(value)

    @field_validator("aliases")
    @classmethod
    def clean_aliases(cls, values: list[str]) -> list[str]:
        cleaned = [_clean_text(value) for value in values]
        if len({value.casefold() for value in cleaned}) != len(cleaned):
            raise ValueError("aliases must be unique")
        return cleaned


class MerchantAliasCreateRequest(BaseModel):
    pattern: str = Field(max_length=200)

    @field_validator("pattern")
    @classmethod
    def clean_pattern(cls, value: str) -> str:
        return _clean_text(value)


class MerchantMergeRequest(BaseModel):
    source_merchant_id: int = Field(gt=0)
