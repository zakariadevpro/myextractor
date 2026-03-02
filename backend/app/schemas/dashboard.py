from typing import Literal

from pydantic import BaseModel


class DashboardOverview(BaseModel):
    leads_today: int = 0
    leads_total: int = 0
    avg_score: float = 0.0
    email_valid_rate: float = 0.0
    duplicate_rate: float = 0.0
    active_extractions: int = 0


class SectorStat(BaseModel):
    sector: str
    count: int


class ZoneStat(BaseModel):
    zone: str
    count: int


class DashboardLeadsBySector(BaseModel):
    data: list[SectorStat]


class DashboardLeadsByZone(BaseModel):
    data: list[ZoneStat]


class B2CConsentSourceStat(BaseModel):
    source: str
    count: int


class B2CComplianceOverview(BaseModel):
    total_b2c: int = 0
    consent_granted: int = 0
    consent_denied: int = 0
    consent_revoked: int = 0
    consent_unknown: int = 0
    exportable_contacts: int = 0
    expiring_7d: int = 0
    double_opt_in_rate: float = 0.0
    revocation_rate: float = 0.0
    by_source: list[B2CConsentSourceStat] = []


class LeadPriorityStat(BaseModel):
    bucket: Literal["hot", "warm", "cold"]
    count: int


class LeadSourceStat(BaseModel):
    source: str
    count: int


class LeadKindStat(BaseModel):
    lead_kind: Literal["b2b", "b2c"]
    count: int


class LeadIntelligenceOverview(BaseModel):
    total_leads: int = 0
    ready_to_contact: int = 0
    missing_contact: int = 0
    high_potential: int = 0
    medium_potential: int = 0
    low_potential: int = 0
    priority_buckets: list[LeadPriorityStat] = []
    by_source: list[LeadSourceStat] = []
    by_kind: list[LeadKindStat] = []
