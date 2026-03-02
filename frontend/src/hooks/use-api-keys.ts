"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import apiClient from "@/lib/api-client";
import type {
  ApiKey,
  ApiKeyCreatePayload,
  ApiKeyCreateResponse,
} from "@/types/api-key";

export function useApiKeys() {
  return useQuery({
    queryKey: ["api-keys"],
    queryFn: async () => {
      const response = await apiClient.get<ApiKey[]>("/api-keys");
      return response.data;
    },
    placeholderData: [],
  });
}

export function useCreateApiKey() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: ApiKeyCreatePayload) => {
      const response = await apiClient.post<ApiKeyCreateResponse>("/api-keys", payload);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["api-keys"] });
    },
  });
}

export function useRevokeApiKey() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (keyId: string) => {
      await apiClient.post(`/api-keys/${keyId}/revoke`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["api-keys"] });
    },
  });
}
