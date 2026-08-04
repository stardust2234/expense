from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class RegistrationRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    display_name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=12, max_length=128)

    @field_validator("email")
    @classmethod
    def normalise_email(cls, value: str) -> str:
        normalised = value.strip().casefold()
        if normalised.count("@") != 1 or normalised.startswith("@") or normalised.endswith("@"):
            raise ValueError("enter a valid email address")
        return normalised

    @field_validator("display_name")
    @classmethod
    def clean_display_name(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("display name must not be empty")
        return cleaned


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def normalise_email(cls, value: str) -> str:
        return value.strip().casefold()


class AuthenticatedUser(BaseModel):
    id: int
    email: str
    display_name: str
    workspace_id: int
    email_verified: bool
    trial_ends_at: datetime
    access_expires_at: datetime | None
    access_active: bool


class AuthSessionResponse(BaseModel):
    user: AuthenticatedUser
    expires_at: datetime
    csrf_token: str | None = None


class CsrfResponse(BaseModel):
    csrf_token: str


class BootstrapStatusResponse(BaseModel):
    required: bool


class TokenRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)


class TokenConfirmation(BaseModel):
    token: str = Field(min_length=32, max_length=200)


class PasswordResetConfirmation(TokenConfirmation):
    new_password: str = Field(min_length=12, max_length=128)


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)


class EmailChangeRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    current_password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def normalise_email(cls, value: str) -> str:
        normalised = value.strip().casefold()
        if normalised.count("@") != 1 or normalised.startswith("@") or normalised.endswith("@"):
            raise ValueError("enter a valid email address")
        return normalised


class AccountDeletionRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    confirmation: Literal["DELETE"]


class SessionItem(BaseModel):
    id: int
    created_at: datetime
    last_used_at: datetime
    expires_at: datetime
    current: bool
