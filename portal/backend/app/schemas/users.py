"""Schema cho auth, users, audit (openapi: LoginRequest, TokenResponse, User, UserCreate, UserUpdate, AuditEntry)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.common import ORMModel

Role = Literal["admin", "operator"]


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class User(ORMModel):
    id: int
    username: str
    role: Role
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_at: datetime
    user: User


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class UserCreate(BaseModel):
    username: str = Field(pattern=r"^[a-z0-9_.-]{3,64}$")
    password: str = Field(min_length=8, max_length=128)
    role: Role


class UserUpdate(BaseModel):
    role: Role | None = None
    is_active: bool | None = None
    password: str | None = Field(None, min_length=8, max_length=128)

    @model_validator(mode="after")
    def _at_least_one(self) -> "UserUpdate":
        if not self.model_fields_set:
            raise ValueError("Cần ít nhất một trường để sửa")
        return self


class AuditEntry(BaseModel):
    id: int
    at: datetime
    user: str | None
    action: str
    object_type: str | None
    object_id: str | None
    detail: dict[str, Any] | None
    client_ip: str | None
