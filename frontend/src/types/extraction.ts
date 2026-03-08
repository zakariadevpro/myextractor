export type ExtractionStatus =
  | "pending"
  | "running"
  | "completed"
  | "failed"
  | "cancelled";

export interface ExtractionJob {
  id: string;
  source: string;
  keywords: string[];
  city: string | null;
  postal_code: string | null;
  radius_km: number | null;
  sector_filter: string | null;
  max_leads: number;
  status: ExtractionStatus;
  progress: number;
  leads_found: number;
  leads_new: number;
  leads_duplicate: number;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  organization_id: string;
  created_by: string;
}

export interface ExtractionCreate {
  source?: string;
  target_kind?: "b2b" | "b2c" | "both";
  keywords?: string[];
  company_name?: string;
  first_name?: string;
  last_name?: string;
  city?: string;
  postal_code?: string;
  department?: string;
  radius_km?: number;
  sector_filter?: string;
  max_leads?: number;
}

export interface ExtractionFilters {
  status?: ExtractionStatus;
  page?: number;
  page_size?: number;
  ordering?: string;
}
