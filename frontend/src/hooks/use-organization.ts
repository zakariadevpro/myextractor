"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import apiClient from "@/lib/api-client";
import type {
  OrganizationSettings,
  UpdateOrganizationPayload,
} from "@/types/organization";

export function useOrganization() {
  return useQuery({
    queryKey: ["organization", "me"],
    queryFn: async () => {
      const response = await apiClient.get<OrganizationSettings>("/organizations/me");
      return response.data;
    },
  });
}

export function useUpdateOrganization() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (payload: UpdateOrganizationPayload) => {
      const response = await apiClient.patch<OrganizationSettings>("/organizations/me", payload);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["organization"] });
      queryClient.invalidateQueries({ queryKey: ["auth", "me"] });
    },
  });
}
