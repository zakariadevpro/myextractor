import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    extraction_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("extraction_jobs.id")
    )

    # Company info
    company_name: Mapped[str] = mapped_column(String(500), nullable=False)
    siren: Mapped[str | None] = mapped_column(String(9))
    siret: Mapped[str | None] = mapped_column(String(14))
    naf_code: Mapped[str | None] = mapped_column(String(10))
    sector: Mapped[str | None] = mapped_column(String(255))
    website: Mapped[str | None] = mapped_column(String(500))

    # Address
    address: Mapped[str | None] = mapped_column(String(500))
    postal_code: Mapped[str | None] = mapped_column(String(10))
    city: Mapped[str | None] = mapped_column(String(255))
    department: Mapped[str | None] = mapped_column(String(5))
    region: Mapped[str | None] = mapped_column(String(100))
    country: Mapped[str] = mapped_column(String(2), default="FR")

    # Scoring
    quality_score: Mapped[int] = mapped_column(SmallInteger, default=0)

    # Source
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(1000))
    lead_kind: Mapped[str] = mapped_column(String(10), nullable=False, default="b2b")

    # Dedup
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    organization = relationship("Organization", back_populates="leads")
    extraction_job = relationship("ExtractionJob", back_populates="leads")
    emails = relationship("LeadEmail", back_populates="lead", cascade="all, delete-orphan")
    phones = relationship("LeadPhone", back_populates="lead", cascade="all, delete-orphan")
    consent = relationship(
        "LeadConsent",
        back_populates="lead",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    @property
    def consent_status(self) -> str:
        if not self.consent or not self.consent.consent_status:
            return "unknown"
        return self.consent.consent_status

    __table_args__ = (
        CheckConstraint("lead_kind IN ('b2b', 'b2c')", name="ck_leads_kind_valid"),
        Index("idx_leads_org", "organization_id"),
        Index("idx_leads_org_sector", "organization_id", "sector"),
        Index("idx_leads_org_city", "organization_id", "city"),
        Index("idx_leads_org_score", "organization_id", quality_score.desc()),
        Index("idx_leads_org_kind", "organization_id", "lead_kind"),
        Index("idx_leads_naf", "naf_code"),
        Index("idx_leads_created", "created_at"),
    )


class LeadEmail(Base):
    __tablename__ = "lead_emails"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    is_valid: Mapped[bool | None] = mapped_column(Boolean)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    lead = relationship("Lead", back_populates="emails")


class LeadPhone(Base):
    __tablename__ = "lead_phones"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    phone_raw: Mapped[str | None] = mapped_column(String(50))
    phone_normalized: Mapped[str | None] = mapped_column(String(20))
    phone_type: Mapped[str] = mapped_column(String(20), default="unknown")
    is_valid: Mapped[bool | None] = mapped_column(Boolean)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    lead = relationship("Lead", back_populates="phones")
