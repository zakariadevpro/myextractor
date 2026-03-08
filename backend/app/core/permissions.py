from app.core.exceptions import ForbiddenError
from app.core.roles import ROLE_HIERARCHY


def require_role(minimum_role: str):
    """Dependency factory to check minimum role level."""
    min_level = ROLE_HIERARCHY.get(minimum_role, 0)

    def checker(current_user):
        user_level = ROLE_HIERARCHY.get(current_user.role, 0)
        if user_level < min_level:
            raise ForbiddenError(
                f"Role '{minimum_role}' or higher required. You have '{current_user.role}'."
            )
        return current_user

    return checker
