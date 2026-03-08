"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import apiClient from "@/lib/api-client";
import type {
  Workflow,
  WorkflowCreatePayload,
  WorkflowRunRequest,
  WorkflowRunResponse,
} from "@/types/workflow";

export function useWorkflows() {
  return useQuery({
    queryKey: ["workflows"],
    queryFn: async () => {
      const response = await apiClient.get<Workflow[]>("/workflows");
      return response.data;
    },
    placeholderData: [],
  });
}

export function useCreateWorkflow() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: WorkflowCreatePayload) => {
      const response = await apiClient.post<Workflow>("/workflows", payload);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["workflows"] });
    },
  });
}

export function useRunWorkflows() {
  return useMutation({
    mutationFn: async (payload: WorkflowRunRequest) => {
      const response = await apiClient.post<WorkflowRunResponse>("/workflows/run", payload);
      return response.data;
    },
  });
}
