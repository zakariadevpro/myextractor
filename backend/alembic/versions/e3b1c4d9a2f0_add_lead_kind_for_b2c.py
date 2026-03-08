"""add lead kind for b2c

Revision ID: e3b1c4d9a2f0
Revises: f5a1e9b4c3d7
Create Date: 2026-03-01 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e3b1c4d9a2f0"
down_revision: str | None = "f5a1e9b4c3d7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "leads",
        sa.Column("lead_kind", sa.String(length=10), nullable=False, server_default="b2b"),
    )
    op.create_check_constraint(
        "ck_leads_kind_valid",
        "leads",
        "lead_kind IN ('b2b', 'b2c')",
    )
    op.create_index("idx_leads_org_kind", "leads", ["organization_id", "lead_kind"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_leads_org_kind", table_name="leads")
    op.drop_constraint("ck_leads_kind_valid", "leads", type_="check")
    op.drop_column("leads", "lead_kind")

