"use client";

import { useQuery } from "@tanstack/react-query";
import apiClient from "@/lib/api-client";
import type {
  B2CComplianceOverview,
  ChartDataPoint,
  DashboardOverview,
  LeadIntelligenceOverview,
} from "@/types/api";

export function useDashboardOverview() {
  return useQuery({
    queryKey: ["dashboard", "overview"],
    queryFn: async () => {
      const response = await apiClient.get<DashboardOverview>(
        "/dashboard/overview"
      );
      return response.data;
    },
    placeholderData: {
      leads_today: 0,
      leads_total: 0,
      avg_score: 0,
      email_valid_rate: 0,
      duplicate_rate: 0,
      active_extractions: 0,
    },
  });
}

export function useLeadsBySector() {
  return useQuery<ChartDataPoint[]>({
    queryKey: ["dashboard", "leads-by-sector"],
    queryFn: async () => {
      const response = await apiClient.get<{ data: { sector: string; count: number }[] }>(
        "/dashboard/leads-by-sector"
      );
      return (response.data.data ?? []).map((item) => ({
        name: item.sector,
        value: item.count,
      }));
    },
    placeholderData: [],
  });
}

export function useLeadsByZone() {
  return useQuery<ChartDataPoint[]>({
    queryKey: ["dashboard", "leads-by-zone"],
    queryFn: async () => {
      const response = await apiClient.get<{ data: { zone: string; count: number }[] }>(
        "/dashboard/leads-by-zone"
      );
      return (response.data.data ?? []).map((item) => ({
        name: item.zone,
        value: item.count,
      }));
    },
    placeholderData: [],
  });
}

export function useB2CCompliance() {
  return useQuery({
    queryKey: ["dashboard", "b2c-compliance"],
    queryFn: async () => {
      const response = await apiClient.get<B2CComplianceOverview>("/dashboard/b2c-compliance");
      return response.data;
    },
    placeholderData: {
      total_b2c: 0,
      consent_granted: 0,
      consent_denied: 0,
      consent_revoked: 0,
      consent_unknown: 0,
      exportable_contacts: 0,
      expiring_7d: 0,
      double_opt_in_rate: 0,
      revocation_rate: 0,
      by_source: [],
    },
  });
}

export function useLeadIntelligence() {
  return useQuery({
    queryKey: ["dashboard", "lead-intelligence"],
    queryFn: async () => {
      const response = await apiClient.get<LeadIntelligenceOverview>("/dashboard/lead-intelligence");
      return response.data;
    },
    placeholderData: {
      total_leads: 0,
      ready_to_contact: 0,
      missing_contact: 0,
      high_potential: 0,
      medium_potential: 0,
      low_potential: 0,
      priority_buckets: [],
      by_source: [],
      by_kind: [],
    },
  });
}
