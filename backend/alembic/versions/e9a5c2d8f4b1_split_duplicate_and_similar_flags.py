"""split_duplicate_and_similar_flags

Revision ID: e9a5c2d8f4b1
Revises: d3e8f5a1b7c9
Create Date: 2026-04-29 09:30:00.000000

Drop the strict unique index so identical rows can co-exist (so the user can
SEE doublons), and split the previous combined is_duplicate flag into:
  - is_duplicate (bool): exact same LOWER(name)+LOWER(city) as another lead.
  - is_similar (bool): same aggressive-normalized key (suffixes/accents
    stripped) but raw form differs. Both flags are recomputed by the worker
    after every extraction.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e9a5c2d8f4b1"
down_revision: str | None = "d3e8f5a1b7c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("uq_leads_org_name_city", table_name="leads")
    op.add_column(
        "leads",
        sa.Column(
            "is_similar",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.create_index(
        "idx_leads_org_dup_similar",
        "leads",
        ["organization_id", "is_duplicate", "is_similar"],
    )


def downgrade() -> None:
    op.drop_index("idx_leads_org_dup_similar", table_name="leads")
    op.drop_column("leads", "is_similar")
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
