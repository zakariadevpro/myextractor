"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import apiClient from "@/lib/api-client";
import type { Plan, Subscription, Usage } from "@/types/subscription";

interface CheckoutPayload {
  plan_slug: string;
  success_url: string;
  cancel_url: string;
}

interface CheckoutResponse {
  checkout_url: string;
}

export function usePlans() {
  return useQuery({
    queryKey: ["subscriptions", "plans"],
    queryFn: async () => {
      const response = await apiClient.get<Plan[]>("/subscriptions/plans");
      return response.data;
    },
    placeholderData: [],
  });
}

export function useUsage() {
  return useQuery({
    queryKey: ["subscriptions", "usage"],
    queryFn: async () => {
      const response = await apiClient.get<Usage>("/subscriptions/usage");
      return response.data;
    },
    placeholderData: {
      leads_extracted: 0,
      leads_exported: 0,
      max_leads_per_month: 0,
      usage_percentage: 0,
    },
  });
}

export function useCurrentSubscription(enabled = true) {
  return useQuery({
    queryKey: ["subscriptions", "current"],
    queryFn: async () => {
      const response = await apiClient.get<Subscription | null>("/subscriptions/current");
      return response.data;
    },
    enabled,
  });
}

export function useCreateCheckoutSession() {
  return useMutation({
    mutationFn: async (payload: CheckoutPayload) => {
      const response = await apiClient.post<CheckoutResponse>("/subscriptions/checkout", payload);
      return response.data;
    },
  });
}
