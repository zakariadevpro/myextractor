export type WorkflowTrigger = "post_extraction" | "manual";

export interface Workflow {
  id: string;
  name: string;
  trigger_event: WorkflowTrigger;
  is_active: boolean;
  conditions: Record<string, unknown>;
  actions: Record<string, unknown>;
  last_run_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface WorkflowCreatePayload {
  name: string;
  trigger_event: WorkflowTrigger;
  is_active: boolean;
  conditions: Record<string, unknown>;
  actions: Record<string, unknown>;
}

export interface WorkflowRunRequest {
  extraction_job_id?: string | null;
  dry_run?: boolean;
}

export interface WorkflowRunResult {
  workflow_id: string;
  matched: number;
  updated: number;
  dry_run: boolean;
}

export interface WorkflowRunResponse {
  total_workflows: number;
  total_matched: number;
  total_updated: number;
  details: WorkflowRunResult[];
}
