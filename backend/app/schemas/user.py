import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr

from app.core.roles import ROLE_USER, RoleName


class UserBase(BaseModel):
    email: EmailStr
    first_name: str | None = None
    last_name: str | None = None
    role: RoleName = ROLE_USER


class UserCreate(BaseModel):
    email: EmailStr
    first_name: str
    last_name: str
    role: RoleName = ROLE_USER


class UserUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    role: RoleName | None = None
    is_active: bool | None = None


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    first_name: str | None
    last_name: str | None
    role: RoleName
    is_active: bool
    organization_id: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class UserMeResponse(UserResponse):
    organization_name: str | None = None


class UserCreateResponse(UserResponse):
    temporary_password: str
