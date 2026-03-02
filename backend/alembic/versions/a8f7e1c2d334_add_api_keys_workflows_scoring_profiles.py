"""add api keys workflows and scoring profiles

Revision ID: a8f7e1c2d334
Revises: e3b1c4d9a2f0
Create Date: 2026-03-01 05:20:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a8f7e1c2d334"
down_revision: str | None = "e3b1c4d9a2f0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "api_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("key_prefix", sa.String(length=24), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "scopes",
            postgresql.ARRAY(sa.String(length=50)),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key_hash", name="uq_api_keys_key_hash"),
    )
    op.create_index("ix_api_keys_key_prefix", "api_keys", ["key_prefix"], unique=False)
    op.create_index(
        "idx_api_keys_org_active",
        "api_keys",
        ["organization_id", "is_active"],
        unique=False,
    )

    op.create_table(
        "automation_workflows",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column(
            "trigger_event",
            sa.String(length=30),
            nullable=False,
            server_default="post_extraction",
        ),
        sa.Column("conditions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("actions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "trigger_event IN ('post_extraction', 'manual')",
            name="ck_workflows_trigger_event_valid",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_workflows_org_active",
        "automation_workflows",
        ["organization_id", "is_active"],
        unique=False,
    )
    op.create_index(
        "idx_workflows_org_trigger",
        "automation_workflows",
        ["organization_id", "trigger_event"],
        unique=False,
    )

    op.create_table(
        "scoring_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=80), nullable=False, server_default="default"),
        sa.Column("high_threshold", sa.Integer(), nullable=False, server_default="80"),
        sa.Column("medium_threshold", sa.Integer(), nullable=False, server_default="55"),
        sa.Column("weights", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "high_threshold >= 0 AND high_threshold <= 100",
            name="ck_scoring_high_threshold_range",
        ),
        sa.CheckConstraint(
            "medium_threshold >= 0 AND medium_threshold <= 100 AND medium_threshold < high_threshold",
            name="ck_scoring_medium_threshold_range",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_scoring_profiles_org",
        "scoring_profiles",
        ["organization_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_scoring_profiles_org", table_name="scoring_profiles")
    op.drop_table("scoring_profiles")

    op.drop_index("idx_workflows_org_trigger", table_name="automation_workflows")
    op.drop_index("idx_workflows_org_active", table_name="automation_workflows")
    op.drop_table("automation_workflows")

    op.drop_index("idx_api_keys_org_active", table_name="api_keys")
    op.drop_index("ix_api_keys_key_prefix", table_name="api_keys")
    op.drop_table("api_keys")
