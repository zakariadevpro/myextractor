"""allow_super_admin_role

Revision ID: d1f4a22a9b41
Revises: b7c3f4e1d2aa
Create Date: 2026-02-28 15:10:00.000000
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d1f4a22a9b41"
down_revision: Union[str, None] = "b7c3f4e1d2aa"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE users SET role = lower(role) WHERE role IS NOT NULL")
    op.execute(
        """
        UPDATE users
        SET role = 'user'
        WHERE role IS NULL OR role NOT IN ('super_admin', 'admin', 'manager', 'user')
        """
    )
    op.drop_constraint("ck_users_role_valid", "users", type_="check")
    op.create_check_constraint(
        "ck_users_role_valid",
        "users",
        "role IN ('super_admin', 'admin', 'manager', 'user')",
    )


def downgrade() -> None:
    op.execute("UPDATE users SET role = 'admin' WHERE role = 'super_admin'")
    op.drop_constraint("ck_users_role_valid", "users", type_="check")
    op.create_check_constraint(
        "ck_users_role_valid",
        "users",
        "role IN ('admin', 'manager', 'user')",
    )
