export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface ApiError {
  detail: string;
  status_code: number;
  errors?: Record<string, string[]>;
}

export interface ApiSuccessResponse<T> {
  data: T;
  message?: string;
}

export interface DashboardOverview {
  leads_today: number;
  leads_total: number;
  avg_score: number;
  email_valid_rate: number;
  duplicate_rate: number;
  active_extractions: number;
}

export interface ChartDataPoint {
  name: string;
  value: number;
}

export interface B2CConsentSourceStat {
  source: string;
  count: number;
}

export interface B2CComplianceOverview {
  total_b2c: number;
  consent_granted: number;
  consent_denied: number;
  consent_revoked: number;
  consent_unknown: number;
  exportable_contacts: number;
  expiring_7d: number;
  double_opt_in_rate: number;
  revocation_rate: number;
  by_source: B2CConsentSourceStat[];
}

export type LeadPriorityBucket = "hot" | "warm" | "cold";

export interface LeadPriorityStat {
  bucket: LeadPriorityBucket;
  count: number;
}

export interface LeadSourceStat {
  source: string;
  count: number;
}

export interface LeadKindStat {
  lead_kind: "b2b" | "b2c";
  count: number;
}

export interface LeadIntelligenceOverview {
  total_leads: number;
  ready_to_contact: number;
  missing_contact: number;
  high_potential: number;
  medium_potential: number;
  low_potential: number;
  priority_buckets: LeadPriorityStat[];
  by_source: LeadSourceStat[];
  by_kind: LeadKindStat[];
}
