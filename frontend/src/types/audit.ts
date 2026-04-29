export interface AuditActionCount {
  action: string;
  count: number;
}

export interface AuditExtractionMetrics {
  total_jobs: number;
  completed_jobs: number;
  failed_jobs: number;
  running_jobs: number;
  success_rate_pct: number;
  avg_leads_found: number;
  avg_duration_seconds: number;
  filtered_non_b2b_total: number;
  filtered_out_total: number;
  classified_b2b_total: number;
  classified_b2c_total: number;
}

export interface AuditSummary {
  since_hours: number;
  total_events: number;
  unique_actors: number;
  events_by_action: AuditActionCount[];
  extraction_metrics: AuditExtractionMetrics;
}

export interface AuditLog {
  id: string;
  organization_id: string | null;
  organization_name: string | null;
  actor_user_id: string | null;
  actor_name: string | null;
  actor_email: string | null;
  action: string;
  resource_type: string;
  resource_id: string | null;
  details: Record<string, unknown> | null;
  created_at: string;
}
