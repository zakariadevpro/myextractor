"""add_lead_consents_table

Revision ID: f5a1e9b4c3d7
Revises: d1f4a22a9b41
Create Date: 2026-03-01 00:45:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f5a1e9b4c3d7"
down_revision: Union[str, None] = "d1f4a22a9b41"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "lead_consents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("consent_status", sa.String(length=20), nullable=False, server_default="unknown"),
        sa.Column("consent_scope", sa.String(length=20), nullable=False, server_default="all"),
        sa.Column("consent_source", sa.String(length=50), nullable=True),
        sa.Column("consent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consent_text_version", sa.String(length=50), nullable=True),
        sa.Column("consent_proof_ref", sa.String(length=255), nullable=True),
        sa.Column("privacy_policy_version", sa.String(length=50), nullable=True),
        sa.Column("lawful_basis", sa.String(length=30), nullable=False, server_default="consent"),
        sa.Column("source_campaign", sa.String(length=255), nullable=True),
        sa.Column("source_channel", sa.String(length=50), nullable=True),
        sa.Column("ip_hash", sa.String(length=128), nullable=True),
        sa.Column("user_agent_hash", sa.String(length=128), nullable=True),
        sa.Column("double_opt_in", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("double_opt_in_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("purpose", sa.String(length=120), nullable=True),
        sa.Column("data_retention_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "consent_status IN ('granted', 'denied', 'revoked', 'unknown')",
            name="ck_lead_consents_status_valid",
        ),
        sa.CheckConstraint(
            "consent_scope IN ('email', 'phone', 'sms', 'whatsapp', 'all')",
            name="ck_lead_consents_scope_valid",
        ),
        sa.CheckConstraint(
            "lawful_basis IN ('consent', 'contract', 'legitimate_interest')",
            name="ck_lead_consents_lawful_basis_valid",
        ),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("lead_id", name="uq_lead_consents_lead_id"),
    )
    op.create_index("ix_lead_consents_lead_id", "lead_consents", ["lead_id"], unique=False)
    op.create_index(
        "ix_lead_consents_organization_id",
        "lead_consents",
        ["organization_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_lead_consents_organization_id", table_name="lead_consents")
    op.drop_index("ix_lead_consents_lead_id", table_name="lead_consents")
    op.drop_table("lead_consents")
