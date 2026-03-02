export interface Plan {
  id: string;
  name: string;
  slug: string;
  monthly_price_cents: number;
  max_leads_per_month: number;
  max_users: number;
  max_extractions_per_day: number;
}

export interface Subscription {
  id: string;
  plan: Plan;
  status: string;
  current_period_start: string | null;
  current_period_end: string | null;
  created_at: string;
}

export interface Usage {
  leads_extracted: number;
  leads_exported: number;
  max_leads_per_month: number;
  usage_percentage: number;
}
