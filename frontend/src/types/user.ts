export type UserRole = "super_admin" | "admin" | "manager" | "user";

export interface User {
  id: string;
  email: string;
  first_name: string | null;
  last_name: string | null;
  role: UserRole;
  is_active: boolean;
  organization_id: string;
  organization_name?: string | null;
  effective_permissions?: string[];
  created_at: string;
}

export interface Organization {
  id: string;
  name: string;
  slug: string;
  plan: "starter" | "pro" | "enterprise";
  leads_used: number;
  leads_limit: number;
  billing_cycle_start: string;
  billing_cycle_end: string;
  created_at: string;
  updated_at: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  first_name: string;
  last_name: string;
  organization_name: string;
}

export interface AuthTokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface TeamMember {
  id: string;
  user: User;
  role: UserRole;
  invited_at: string;
  joined_at: string | null;
}

export interface PermissionCatalogItem {
  key: string;
  label: string;
  description: string;
  category: string;
}

export interface PermissionPresetItem {
  key: string;
  label: string;
  description: string;
  permissions: string[];
}

export interface UserPermissionsSnapshot {
  user_id: string;
  role: UserRole;
  default_permissions: string[];
  grants: string[];
  revokes: string[];
  effective_permissions: string[];
}
