"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import apiClient from "@/lib/api-client";
import type {
  B2CCsvImportSummary,
  B2CLeadIntakePayload,
  Lead,
  LeadConsent,
  LeadConsentUpdatePayload,
  LeadFilters,
  SuggestedSegment,
} from "@/types/lead";
import type { PaginatedResponse } from "@/types/api";

export function useLeads(filters: LeadFilters = {}) {
  return useQuery({
    queryKey: ["leads", filters],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (filters.search) params.set("search", filters.search);
      if (filters.lead_kind) params.set("lead_kind", filters.lead_kind);
      if (filters.sector) params.set("sector", filters.sector);
      if (filters.city) params.set("city", filters.city);
      if (filters.min_score !== undefined)
        params.set("min_score", String(filters.min_score));
      if (filters.max_score !== undefined)
        params.set("max_score", String(filters.max_score));
      if (filters.date_from) params.set("date_from", filters.date_from);
      if (filters.date_to) params.set("date_to", filters.date_to);
      if (filters.has_email !== undefined)
        params.set("has_email", String(filters.has_email));
      if (filters.has_phone !== undefined)
        params.set("has_phone", String(filters.has_phone));
      if (filters.is_duplicate !== undefined)
        params.set("is_duplicate", String(filters.is_duplicate));
      if (filters.consent_granted_only !== undefined)
        params.set("consent_granted_only", String(filters.consent_granted_only));
      if (filters.page) params.set("page", String(filters.page));
      if (filters.page_size) params.set("page_size", String(filters.page_size));
      if (filters.ordering) params.set("ordering", filters.ordering);

      const response = await apiClient.get<PaginatedResponse<Lead>>(
        `/leads?${params.toString()}`
      );
      return response.data;
    },
  });
}

export function useLead(id: string) {
  return useQuery({
    queryKey: ["lead", id],
    queryFn: async () => {
      const response = await apiClient.get<Lead>(`/leads/${id}`);
      return response.data;
    },
    enabled: !!id,
  });
}

export function useSuggestedSegments() {
  return useQuery({
    queryKey: ["leads", "segments", "suggested"],
    queryFn: async () => {
      const response = await apiClient.get<{ items: SuggestedSegment[] }>(
        "/leads/segments/suggested"
      );
      return response.data.items ?? [];
    },
    placeholderData: [],
  });
}

export function useLeadConsent(leadId: string) {
  return useQuery({
    queryKey: ["lead", "consent", leadId],
    queryFn: async () => {
      const response = await apiClient.get<LeadConsent>(`/leads/${leadId}/consent`);
      return response.data;
    },
    enabled: !!leadId,
  });
}

export function useUpdateLeadConsent() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      leadId,
      payload,
    }: {
      leadId: string;
      payload: LeadConsentUpdatePayload;
    }) => {
      const response = await apiClient.patch<LeadConsent>(`/leads/${leadId}/consent`, payload);
      return response.data;
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["lead", "consent", variables.leadId] });
      queryClient.invalidateQueries({ queryKey: ["lead", variables.leadId] });
      queryClient.invalidateQueries({ queryKey: ["leads"] });
    },
  });
}

export function useDeleteLead() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (id: string) => {
      await apiClient.delete(`/leads/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["leads"] });
    },
  });
}

export function useExportLeads() {
  return useMutation({
    mutationFn: async ({
      filters,
      format = "csv",
    }: {
      filters: LeadFilters;
      format?: "csv" | "xlsx";
    }) => {
      const params = new URLSearchParams();
      if (filters.search) params.set("search", filters.search);
      if (filters.lead_kind) params.set("lead_kind", filters.lead_kind);
      if (filters.sector) params.set("sector", filters.sector);
      if (filters.city) params.set("city", filters.city);
      if (filters.min_score !== undefined)
        params.set("min_score", String(filters.min_score));
      if (filters.consent_granted_only !== undefined)
        params.set("consent_granted_only", String(filters.consent_granted_only));

      const endpoint = format === "xlsx" ? "/leads/export/xlsx" : "/leads/export/csv";
      const response = await apiClient.get(`${endpoint}?${params.toString()}`, {
        responseType: "blob",
      });

      // Trigger download
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", `winaity-extractor-leads-${Date.now()}.${format}`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    },
  });
}

export function useRemoveDuplicates() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async () => {
      const response = await apiClient.post<{ message: string }>(
        "/leads/deduplicate"
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["leads"] });
    },
  });
}

export function useCreateB2CLeadIntake() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (payload: B2CLeadIntakePayload) => {
      const response = await apiClient.post<Lead>("/leads/b2c/intake", payload);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["leads"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}

export function useImportB2CCsvIntake() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      file,
      mapping,
      defaults,
    }: {
      file: File;
      mapping: Record<string, string>;
      defaults?: Record<string, string | boolean>;
    }) => {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("mapping", JSON.stringify(mapping));
      if (defaults) {
        formData.append("defaults", JSON.stringify(defaults));
      }
      const response = await apiClient.post<B2CCsvImportSummary>("/leads/b2c/intake/csv", formData, {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["leads"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}
