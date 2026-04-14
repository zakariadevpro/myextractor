import uuid
from datetime import datetime

from pydantic import BaseModel, Field, model_validator


class ScoringProfileResponse(BaseModel):
    id: uuid.UUID | None = None
    name: str = "default"
    high_threshold: int = 80
    medium_threshold: int = 55
    weights: dict[str, int]
    updated_at: datetime | None = None


class ScoringProfileUpdate(BaseModel):
    name: str = Field(default="default", min_length=3, max_length=80)
    high_threshold: int = Field(default=80, ge=1, le=100)
    medium_threshold: int = Field(default=55, ge=0, le=99)
    weights: dict[str, int] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_thresholds(self):
        if self.medium_threshold >= self.high_threshold:
            raise ValueError("medium_threshold must be lower than high_threshold")
        return self


class ScoringRecomputeResponse(BaseModel):
    scored: int = 0
    status: str = "completed"
