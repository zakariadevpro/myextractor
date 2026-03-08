import pytest
from pydantic import ValidationError

from app.core.roles import has_minimum_role
from app.schemas.user import UserCreate


class TestRoles:
    def test_has_minimum_role(self):
        assert has_minimum_role("super_admin", "admin")
        assert has_minimum_role("super_admin", "manager")
        assert has_minimum_role("admin", "manager")
        assert has_minimum_role("manager", "user")
        assert not has_minimum_role("admin", "super_admin")
        assert not has_minimum_role("user", "manager")
        assert not has_minimum_role("unknown", "user")

    def test_user_create_role_validation(self):
        with pytest.raises(ValidationError):
            UserCreate(
                email="test@example.com",
                first_name="Test",
                last_name="User",
                role="owner",
            )
