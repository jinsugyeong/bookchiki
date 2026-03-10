import re
import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator


class UserResponse(BaseModel):
    """사용자 정보 응답 스키마."""

    id: uuid.UUID
    email: str
    name: str
    profile_image: str | None = None
    instagram_username: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class UserUpdateRequest(BaseModel):
    """사용자 프로필 업데이트 요청 스키마."""

    instagram_username: str | None = None

    @field_validator("instagram_username")
    @classmethod
    def validate_instagram_username(cls, v: str | None) -> str | None:
        """인스타그램 계정명 유효성 검사 — @는 자동 제거, 영숫자/밑줄/점/최대 30자."""
        if v is None:
            return None
        v = v.strip().lstrip("@")
        if not v:
            return None
        if len(v) > 30:
            raise ValueError("인스타그램 계정명은 30자 이하여야 합니다.")
        if not re.match(r"^[a-zA-Z0-9_.]+$", v):
            raise ValueError("인스타그램 계정명은 영문자, 숫자, 밑줄(_), 점(.)만 사용할 수 있습니다.")
        return v


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse


class RefreshRequest(BaseModel):
    refresh_token: str


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
