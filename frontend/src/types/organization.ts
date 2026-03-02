export interface OrganizationSettings {
  id: string;
  name: string;
  slug: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface UpdateOrganizationPayload {
  organization_name: string;
}
