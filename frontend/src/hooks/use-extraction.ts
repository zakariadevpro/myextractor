"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import apiClient from "@/lib/api-client";
import type {
  ExtractionJob,
  ExtractionCreate,
  ExtractionFilters,
} from "@/types/extraction";
import type { PaginatedResponse } from "@/types/api";

export function useExtractions(filters: ExtractionFilters = {}) {
  return useQuery({
    queryKey: ["extractions", filters],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (filters.status) params.set("status", filters.status);
      if (filters.page) params.set("page", String(filters.page));
      if (filters.page_size) params.set("page_size", String(filters.page_size));
      if (filters.ordering) params.set("ordering", filters.ordering);

      const response = await apiClient.get<PaginatedResponse<ExtractionJob>>(
        `/extractions?${params.toString()}`
      );
      return response.data;
    },
    refetchInterval: (query) => {
      // Auto-refresh every 5s if there are running extractions
      const data = query.state.data;
      if (data?.items.some((job) => job.status === "running" || job.status === "pending")) {
        return 5000;
      }
      return false;
    },
  });
}

export function useExtraction(id: string) {
  return useQuery({
    queryKey: ["extraction", id],
    queryFn: async () => {
      const response = await apiClient.get<ExtractionJob>(
        `/extractions/${id}`
      );
      return response.data;
    },
    enabled: !!id,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (data?.status === "running" || data?.status === "pending") {
        return 3000;
      }
      return false;
    },
  });
}

export function useCreateExtraction() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: ExtractionCreate) => {
      const response = await apiClient.post<ExtractionJob>(
        "/extractions",
        data
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["extractions"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}

export function useCancelExtraction() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (id: string) => {
      const response = await apiClient.post<{ message: string }>(
        `/extractions/${id}/cancel`
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["extractions"] });
      toast.success("Extraction annulee.");
    },
    onError: () => {
      toast.error("Impossible d'annuler cette extraction.");
    },
  });
}
