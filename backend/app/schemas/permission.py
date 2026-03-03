import uuid

from pydantic import BaseModel, Field, model_validator

from app.core.permission_catalog import is_known_permission, normalize_permission_name


class PermissionCatalogItem(BaseModel):
    key: str
    label: str
    description: str
    category: str


class PermissionPresetItem(BaseModel):
    key: str
    label: str
    description: str
    permissions: list[str]


class UserPermissionsUpdate(BaseModel):
    grants: list[str] = Field(default_factory=list)
    revokes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_permissions(self):
        grants = {normalize_permission_name(item) for item in self.grants if item}
        revokes = {normalize_permission_name(item) for item in self.revokes if item}
        if grants.intersection(revokes):
            raise ValueError("A permission cannot be granted and revoked at the same time")
        unknown = [perm for perm in sorted(grants | revokes) if not is_known_permission(perm)]
        if unknown:
            raise ValueError(f"Unknown permissions: {', '.join(unknown)}")
        self.grants = sorted(grants)
        self.revokes = sorted(revokes)
        return self


class UserPermissionsApplyPreset(BaseModel):
    preset_key: str = Field(min_length=1)

    @model_validator(mode="after")
    def normalize_key(self):
        self.preset_key = str(self.preset_key or "").strip().lower()
        return self


class UserPermissionsResponse(BaseModel):
    user_id: uuid.UUID
    role: str
    default_permissions: list[str]
    grants: list[str]
    revokes: list[str]
    effective_permissions: list[str]
