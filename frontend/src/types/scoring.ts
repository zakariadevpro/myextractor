export interface ScoringProfile {
  id: string | null;
  name: string;
  high_threshold: number;
  medium_threshold: number;
  weights: Record<string, number>;
  updated_at: string | null;
}

export interface ScoringProfileUpdatePayload {
  name: string;
  high_threshold: number;
  medium_threshold: number;
  weights: Record<string, number>;
}

export interface ScoringRecomputeResponse {
  scored: number;
}
