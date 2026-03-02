"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import apiClient from "@/lib/api-client";
import type { PaginatedResponse } from "@/types/api";
import type { User, UserRole } from "@/types/user";

interface UsersFilters {
  page?: number;
  page_size?: number;
}

interface CreateUserPayload {
  email: string;
  first_name: string;
  last_name: string;
  role: UserRole;
}

interface CreateUserResponse extends User {
  temporary_password: string;
}

interface UpdateUserPayload {
  userId: string;
  role?: UserRole;
  is_active?: boolean;
}

export function useUsers(filters: UsersFilters = {}) {
  return useQuery({
    queryKey: ["users", filters],
    queryFn: async () => {
      const params = new URLSearchParams();
      params.set("page", String(filters.page ?? 1));
      params.set("page_size", String(filters.page_size ?? 20));
      const response = await apiClient.get<PaginatedResponse<User>>(`/users?${params.toString()}`);
      return response.data;
    },
  });
}

export function useCreateUser() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (payload: CreateUserPayload) => {
      const response = await apiClient.post<CreateUserResponse>("/users", payload);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
    },
  });
}

export function useUpdateUser() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ userId, ...payload }: UpdateUserPayload) => {
      const response = await apiClient.patch<User>(`/users/${userId}`, payload);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
    },
  });
}

export function useDeactivateUser() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (userId: string) => {
      const response = await apiClient.delete<{ message: string }>(`/users/${userId}`);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
    },
  });
}
