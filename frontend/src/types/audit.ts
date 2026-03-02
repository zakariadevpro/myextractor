export interface AuditActionCount {
  action: string;
  count: number;
}

export interface AuditSummary {
  since_hours: number;
  total_events: number;
  unique_actors: number;
  events_by_action: AuditActionCount[];
}

export interface AuditLog {
  id: string;
  organization_id: string | null;
  actor_user_id: string | null;
  action: string;
  resource_type: string;
  resource_id: string | null;
  details: Record<string, unknown> | null;
  created_at: string;
}
