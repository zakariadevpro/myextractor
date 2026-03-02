"use client";

import { useQuery } from "@tanstack/react-query";
import apiClient from "@/lib/api-client";
import type { PaginatedResponse } from "@/types/api";
import type { AuditLog, AuditSummary } from "@/types/audit";

export interface AuditLogFilters {
  page?: number;
  page_size?: number;
  action?: string;
  resource_type?: string;
}

export function useAuditSummary(sinceHours = 24) {
  return useQuery({
    queryKey: ["audit", "summary", sinceHours],
    queryFn: async () => {
      const response = await apiClient.get<AuditSummary>(
        `/audit/summary?since_hours=${sinceHours}`
      );
      return response.data;
    },
    placeholderData: {
      since_hours: sinceHours,
      total_events: 0,
      unique_actors: 0,
      events_by_action: [],
    },
  });
}

export function useAuditLogs(filters: AuditLogFilters = {}) {
  return useQuery({
    queryKey: ["audit", "logs", filters],
    queryFn: async () => {
      const params = new URLSearchParams();
      params.set("page", String(filters.page ?? 1));
      params.set("page_size", String(filters.page_size ?? 20));
      if (filters.action) params.set("action", filters.action);
      if (filters.resource_type) params.set("resource_type", filters.resource_type);

      const response = await apiClient.get<PaginatedResponse<AuditLog>>(
        `/audit/logs?${params.toString()}`
      );
      return response.data;
    },
  });
}
