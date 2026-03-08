from typing import Literal, TypeAlias

ROLE_SUPER_ADMIN = "super_admin"
ROLE_ADMIN = "admin"
ROLE_MANAGER = "manager"
ROLE_USER = "user"

RoleName: TypeAlias = Literal["super_admin", "admin", "manager", "user"]
ROLE_HIERARCHY: dict[str, int] = {
    ROLE_SUPER_ADMIN: 4,
    ROLE_ADMIN: 3,
    ROLE_MANAGER: 2,
    ROLE_USER: 1,
}


def has_minimum_role(user_role: str, minimum_role: RoleName) -> bool:
    user_level = ROLE_HIERARCHY.get(user_role.lower(), 0)
    min_level = ROLE_HIERARCHY[minimum_role]
    return user_level >= min_level
