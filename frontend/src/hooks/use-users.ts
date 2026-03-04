"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import apiClient from "@/lib/api-client";
import type { PaginatedResponse } from "@/types/api";
import type {
  PermissionCatalogItem,
  PermissionPresetItem,
  User,
  UserPermissionsSnapshot,
  UserRole,
} from "@/types/user";

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

export function usePermissionCatalog(enabled = true) {
  return useQuery({
    queryKey: ["users", "permissions", "catalog"],
    queryFn: async () => {
      const response = await apiClient.get<PermissionCatalogItem[]>("/users/permissions/catalog");
      return response.data;
    },
    enabled,
    placeholderData: [],
  });
}

export function useUserPermissions(userId?: string) {
  return useQuery({
    queryKey: ["users", "permissions", userId],
    queryFn: async () => {
      const response = await apiClient.get<UserPermissionsSnapshot>(`/users/${userId}/permissions`);
      return response.data;
    },
    enabled: Boolean(userId),
  });
}

export function useUsersPermissionsMatrix(userIds: string[], enabled = true) {
  const stableIds = [...userIds].sort();
  return useQuery({
    queryKey: ["users", "permissions", "matrix", stableIds],
    queryFn: async () => {
      const snapshots = await Promise.all(
        stableIds.map(async (userId) => {
          const response = await apiClient.get<UserPermissionsSnapshot>(`/users/${userId}/permissions`);
          return response.data;
        })
      );
      return snapshots.reduce(
        (acc, snapshot) => {
          acc[snapshot.user_id] = snapshot;
          return acc;
        },
        {} as Record<string, UserPermissionsSnapshot>
      );
    },
    enabled: enabled && stableIds.length > 0,
    placeholderData: {},
  });
}

export function usePermissionPresets(enabled = true) {
  return useQuery({
    queryKey: ["users", "permissions", "presets"],
    queryFn: async () => {
      const response = await apiClient.get<PermissionPresetItem[]>("/users/permissions/presets");
      return response.data;
    },
    enabled,
    placeholderData: [],
  });
}

export function useUpdateUserPermissions() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      userId,
      grants,
      revokes,
    }: {
      userId: string;
      grants: string[];
      revokes: string[];
    }) => {
      const response = await apiClient.put<UserPermissionsSnapshot>(`/users/${userId}/permissions`, {
        grants,
        revokes,
      });
      return response.data;
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      queryClient.invalidateQueries({ queryKey: ["users", "permissions", variables.userId] });
    },
  });
}

export function useApplyPermissionPreset() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ userId, presetKey }: { userId: string; presetKey: string }) => {
      const response = await apiClient.post<UserPermissionsSnapshot>(
        `/users/${userId}/permissions/apply-preset`,
        {
          preset_key: presetKey,
        }
      );
      return response.data;
    },
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      queryClient.invalidateQueries({ queryKey: ["users", "permissions", variables.userId] });
    },
  });
}
