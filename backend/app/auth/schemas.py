
import json
import re
import uuid
from datetime import datetime

from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.auth.models import Role


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=255)

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        return v


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class GoogleAuthRequest(BaseModel):
    code: str
    redirect_uri: str | None = None
    state: str | None = None


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: Role
    is_active: bool
    auth_provider: str = "local"
    created_at: datetime
    feature_access: dict[str, bool] | None = None
    org_id: uuid.UUID | None = None
    cashbook_access: str = "personal"
    fallback_phone: str | None = None
    voicemail_mode: str = "cell_then_voicemail"
    # API-facing name is 'status' (derived state) but underlying column is
    # 'voicemail_greeting_type'. validation_alias lets model_validate(user)
    # pull from the SA attribute named voicemail_greeting_type.
    voicemail_greeting_status: str | None = Field(
        None, validation_alias="voicemail_greeting_type"
    )
    booking_link: str | None = None

    model_config = {"from_attributes": True, "populate_by_name": True}


class UserUpdate(BaseModel):
    full_name: str | None = Field(None, min_length=1, max_length=255)
    password: str | None = Field(None, min_length=8, max_length=128)
    fallback_phone: str | None = Field(None, max_length=20)
    voicemail_mode: str | None = Field(
        None, pattern="^(cell_then_voicemail|voicemail_only|cell_only)$"
    )
    booking_link: str | None = Field(None, max_length=500)


class VoicemailGreetingPreview(BaseModel):
    """Returned by GET /auth/me/voicemail-greeting for in-place editing."""
    type: str | None = None        # 'audio' | 'text' | None
    text: str | None = None        # populated when type='text'
    storage_key: str | None = None # populated when type='audio'


class UserRoleUpdate(BaseModel):
    role: Role


class AdminUserCreate(BaseModel):
    email: EmailStr
    password: Optional[str] = Field(None, min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=255)
    role: Role = Role.VIEWER
    feature_access: Optional[dict[str, bool]] = None
    send_invite: bool = False

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        return v

    @model_validator(mode="after")
    def require_password_or_invite(self):
        if not self.send_invite and not self.password:
            raise ValueError("Password is required when send_invite is false")
        return self


class AdminUserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(None, min_length=8, max_length=128)
    full_name: Optional[str] = Field(None, min_length=1, max_length=255)
    role: Optional[Role] = None
    feature_access: Optional[dict[str, bool]] = None
    is_active: Optional[bool] = None
    cashbook_access: Optional[str] = Field(None, pattern=r"^(personal|org)$")


class InviteCompleteRequest(BaseModel):
    token: str
    password: str = Field(min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        return v


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenRefreshRequest(BaseModel):
    refresh_token: str
