"""add_leads_dedup_unique_index

Revision ID: d3e8f5a1b7c9
Revises: c2f9d7e6b1aa
Create Date: 2026-03-25 12:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d3e8f5a1b7c9"
down_revision: str | None = "c2f9d7e6b1aa"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Unique index for deduplication: prevents race conditions when
    # concurrent workers insert leads for the same organization.
    op.create_index(
        "uq_leads_org_name_city",
        "leads",
        [
            "organization_id",
            sa.text("LOWER(company_name)"),
            sa.text("LOWER(COALESCE(city, ''))"),
        ],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_leads_org_name_city", table_name="leads")
