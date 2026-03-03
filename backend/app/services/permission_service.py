import uuid

from sqlalchemy import delete, select
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, ForbiddenError
from app.core.permission_catalog import (
    get_role_default_permissions,
    is_known_permission,
    list_permission_catalog,
    normalize_permission_name,
    resolve_effective_permissions,
)
from app.models.user import User
from app.models.user_permission import UserPermission
from app.schemas.permission import PermissionCatalogItem, UserPermissionsResponse


class PermissionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _is_missing_table_error(exc: Exception) -> bool:
        text = str(exc).lower()
        return "user_permissions" in text and ("does not exist" in text or "undefinedtable" in text)

    async def _fetch_overrides(self, user: User) -> tuple[set[str], set[str]]:
        try:
            result = await self.db.execute(
                select(UserPermission.permission, UserPermission.is_granted).where(
                    UserPermission.organization_id == user.organization_id,
                    UserPermission.user_id == user.id,
                )
            )
        except ProgrammingError as exc:
            if self._is_missing_table_error(exc):
                return set(), set()
            raise

        grants: set[str] = set()
        revokes: set[str] = set()
        for permission, is_granted in result.all():
            normalized = normalize_permission_name(permission)
            if not normalized:
                continue
            if is_granted:
                grants.add(normalized)
            else:
                revokes.add(normalized)
        return grants, revokes

    async def get_effective_permissions(self, user: User) -> set[str]:
        grants, revokes = await self._fetch_overrides(user)
        return resolve_effective_permissions(user.role, grants, revokes)

    async def require_user_permission(self, user: User, permission: str) -> None:
        requested = normalize_permission_name(permission)
        if not requested or not is_known_permission(requested):
            raise BadRequestError(f"Unknown permission '{permission}'")
        effective = await self.get_effective_permissions(user)
        if requested not in effective:
            raise ForbiddenError(f"Permission required: {requested}")

    async def get_user_permissions_snapshot(self, user: User) -> UserPermissionsResponse:
        grants, revokes = await self._fetch_overrides(user)
        defaults = get_role_default_permissions(user.role)
        effective = resolve_effective_permissions(user.role, grants, revokes)
        return UserPermissionsResponse(
            user_id=user.id,
            role=user.role,
            default_permissions=sorted(defaults),
            grants=sorted(grants),
            revokes=sorted(revokes),
            effective_permissions=sorted(effective),
        )

    async def replace_user_permissions(
        self,
        *,
        target_user: User,
        grants: list[str],
        revokes: list[str],
    ) -> UserPermissionsResponse:
        normalized_grants = {normalize_permission_name(item) for item in grants if item}
        normalized_revokes = {normalize_permission_name(item) for item in revokes if item}
        if normalized_grants.intersection(normalized_revokes):
            raise BadRequestError("A permission cannot be granted and revoked at the same time")

        unknown = [
            perm
            for perm in sorted(normalized_grants | normalized_revokes)
            if not is_known_permission(perm)
        ]
        if unknown:
            raise BadRequestError(f"Unknown permissions: {', '.join(unknown)}")

        await self.db.execute(
            delete(UserPermission).where(
                UserPermission.organization_id == target_user.organization_id,
                UserPermission.user_id == target_user.id,
            )
        )

        rows: list[UserPermission] = []
        for permission in sorted(normalized_grants):
            rows.append(
                UserPermission(
                    organization_id=target_user.organization_id,
                    user_id=target_user.id,
                    permission=permission,
                    is_granted=True,
                )
            )
        for permission in sorted(normalized_revokes):
            rows.append(
                UserPermission(
                    organization_id=target_user.organization_id,
                    user_id=target_user.id,
                    permission=permission,
                    is_granted=False,
                )
            )
        self.db.add_all(rows)
        await self.db.flush()

        return await self.get_user_permissions_snapshot(target_user)

    @staticmethod
    def get_permission_catalog() -> list[PermissionCatalogItem]:
        return [PermissionCatalogItem(**item) for item in list_permission_catalog()]

    async def count_active_super_admins(self, organization_id: uuid.UUID) -> int:
        result = await self.db.execute(
            select(User).where(
                User.organization_id == organization_id,
                User.role == "super_admin",
                User.is_active.is_(True),
            )
        )
        users = result.scalars().all()
        count = 0
        for user in users:
            effective = await self.get_effective_permissions(user)
            if "access.super_admin" in effective:
                count += 1
        return count
