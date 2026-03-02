import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ExtractionJob(Base):
    __tablename__ = "extraction_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    # Search parameters
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="google_maps")
    keywords: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    sector_filter: Mapped[str | None] = mapped_column(String(255))
    city: Mapped[str | None] = mapped_column(String(255))
    postal_code: Mapped[str | None] = mapped_column(String(10))
    radius_km: Mapped[int | None] = mapped_column(Integer)
    max_leads: Mapped[int] = mapped_column(Integer, default=100)

    # Execution
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    celery_task_id: Mapped[str | None] = mapped_column(String(255))
    progress: Mapped[int] = mapped_column(SmallInteger, default=0)
    leads_found: Mapped[int] = mapped_column(Integer, default=0)
    leads_new: Mapped[int] = mapped_column(Integer, default=0)
    leads_duplicate: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)

    # Timestamps
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    organization = relationship("Organization", back_populates="extraction_jobs")
    creator = relationship("User")
    leads = relationship("Lead", back_populates="extraction_job", lazy="noload")
