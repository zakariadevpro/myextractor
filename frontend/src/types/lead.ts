export interface LeadEmail {
  email: string;
  is_valid: boolean | null;
  is_primary: boolean;
}

export interface LeadPhone {
  phone_raw: string | null;
  phone_normalized: string | null;
  phone_type: string;
  is_valid: boolean | null;
  is_primary: boolean;
}

export interface Lead {
  id: string;
  lead_kind: "b2b" | "b2c";
  company_name: string;
  siren: string | null;
  naf_code: string | null;
  sector: string | null;
  website: string | null;
  address: string | null;
  postal_code: string | null;
  city: string | null;
  department: string | null;
  region: string | null;
  quality_score: number;
  source: string;
  source_url: string | null;
  is_duplicate: boolean;
  consent_status: ConsentStatus;
  emails: LeadEmail[];
  phones: LeadPhone[];
  extraction_job_id: string;
  organization_id: string;
  created_at: string;
}

export interface LeadFilters {
  lead_kind?: "b2b" | "b2c";
  search?: string;
  sector?: string;
  city?: string;
  department?: string;
  region?: string;
  min_score?: number;
  max_score?: number;
  date_from?: string;
  date_to?: string;
  has_email?: boolean;
  has_phone?: boolean;
  is_duplicate?: boolean;
  consent_granted_only?: boolean;
  source?: string;
  page?: number;
  page_size?: number;
  ordering?: string;
}

export interface SuggestedSegment {
  code: string;
  label: string;
  description: string;
  count: number;
  filters: Record<string, string | number | boolean>;
}

export type ConsentStatus = "granted" | "denied" | "revoked" | "unknown";
export type ConsentScope = "email" | "phone" | "sms" | "whatsapp" | "all";
export type LawfulBasis = "consent" | "contract" | "legitimate_interest";

export interface LeadConsent {
  id: string;
  lead_id: string;
  organization_id: string;
  consent_status: ConsentStatus;
  consent_scope: ConsentScope;
  consent_source: string | null;
  consent_at: string | null;
  consent_text_version: string | null;
  consent_proof_ref: string | null;
  privacy_policy_version: string | null;
  lawful_basis: LawfulBasis;
  source_campaign: string | null;
  source_channel: string | null;
  ip_hash: string | null;
  user_agent_hash: string | null;
  double_opt_in: boolean;
  double_opt_in_at: string | null;
  purpose: string | null;
  data_retention_until: string | null;
  created_at: string;
  updated_at: string;
}

export interface LeadConsentUpdatePayload {
  consent_status?: ConsentStatus;
  consent_scope?: ConsentScope;
  consent_source?: string | null;
  consent_at?: string | null;
  consent_text_version?: string | null;
  consent_proof_ref?: string | null;
  privacy_policy_version?: string | null;
  lawful_basis?: LawfulBasis;
  source_campaign?: string | null;
  source_channel?: string | null;
  ip_hash?: string | null;
  user_agent_hash?: string | null;
  double_opt_in?: boolean;
  double_opt_in_at?: string | null;
  purpose?: string | null;
  data_retention_until?: string | null;
}

export interface B2CLeadIntakePayload {
  full_name: string;
  email?: string | null;
  phone?: string | null;
  city?: string | null;
  consent_source: "web_form" | "meta_lead_ads" | "google_lead_form" | "partner_api" | "crm_import";
  consent_at: string;
  consent_text_version: string;
  consent_proof_ref: string;
  privacy_policy_version: string;
  source_campaign?: string | null;
  source_channel?: "web" | "facebook" | "instagram" | "google" | "tiktok" | "partner" | "import" | null;
  purpose?: string | null;
  double_opt_in?: boolean;
  double_opt_in_at?: string | null;
}
