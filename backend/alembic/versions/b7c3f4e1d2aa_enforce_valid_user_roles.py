"""enforce_valid_user_roles

Revision ID: b7c3f4e1d2aa
Revises: 9f2d1a4c77e3
Create Date: 2026-02-28 00:20:00.000000
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7c3f4e1d2aa"
down_revision: Union[str, None] = "9f2d1a4c77e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE users SET role = lower(role) WHERE role IS NOT NULL")
    op.execute(
        """
        UPDATE users
        SET role = 'user'
        WHERE role IS NULL OR role NOT IN ('admin', 'manager', 'user')
        """
    )
    op.create_check_constraint(
        "ck_users_role_valid",
        "users",
        "role IN ('admin', 'manager', 'user')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_users_role_valid", "users", type_="check")
