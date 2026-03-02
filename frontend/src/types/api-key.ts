export interface ApiKey {
  id: string;
  name: string;
  key_prefix: string;
  scopes: string[];
  is_active: boolean;
  expires_at: string | null;
  last_used_at: string | null;
  revoked_at: string | null;
  created_at: string;
}

export interface ApiKeyCreatePayload {
  name: string;
  scopes: string[];
  expires_at?: string | null;
}

export interface ApiKeyCreateResponse {
  api_key: string;
  key: ApiKey;
}
