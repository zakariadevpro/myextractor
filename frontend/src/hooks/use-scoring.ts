"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import apiClient from "@/lib/api-client";
import type {
  ScoringProfile,
  ScoringProfileUpdatePayload,
  ScoringRecomputeResponse,
} from "@/types/scoring";

export function useScoringProfile() {
  return useQuery({
    queryKey: ["scoring", "profile"],
    queryFn: async () => {
      const response = await apiClient.get<ScoringProfile>("/scoring/profile");
      return response.data;
    },
  });
}

export function useUpdateScoringProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: ScoringProfileUpdatePayload) => {
      const response = await apiClient.put<ScoringProfile>("/scoring/profile", payload);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["scoring"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}

export function useRecomputeScoring() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const response = await apiClient.post<ScoringRecomputeResponse>("/scoring/recompute");
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["leads"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}
