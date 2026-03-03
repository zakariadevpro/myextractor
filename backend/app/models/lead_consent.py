import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class LeadConsent(Base):
    __tablename__ = "lead_consents"
    __table_args__ = (
        CheckConstraint(
            "consent_status IN ('granted', 'denied', 'revoked', 'unknown')",
            name="ck_lead_consents_status_valid",
        ),
        CheckConstraint(
            "consent_scope IN ('email', 'phone', 'sms', 'whatsapp', 'all')",
            name="ck_lead_consents_scope_valid",
        ),
        CheckConstraint(
            "lawful_basis IN ('consent', 'contract', 'legitimate_interest')",
            name="ck_lead_consents_lawful_basis_valid",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("leads.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    consent_status: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown")
    consent_scope: Mapped[str] = mapped_column(String(20), nullable=False, default="all")
    consent_source: Mapped[str | None] = mapped_column(String(50))
    consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consent_text_version: Mapped[str | None] = mapped_column(String(50))
    consent_proof_ref: Mapped[str | None] = mapped_column(String(255))
    privacy_policy_version: Mapped[str | None] = mapped_column(String(50))
    lawful_basis: Mapped[str] = mapped_column(String(30), nullable=False, default="consent")
    source_campaign: Mapped[str | None] = mapped_column(String(255))
    source_channel: Mapped[str | None] = mapped_column(String(50))
    ip_hash: Mapped[str | None] = mapped_column(String(128))
    user_agent_hash: Mapped[str | None] = mapped_column(String(128))
    double_opt_in: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    double_opt_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    purpose: Mapped[str | None] = mapped_column(String(120))
    data_retention_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    lead = relationship("Lead", back_populates="consent")
