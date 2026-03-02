import type { UserRole } from "@/types/user";

const ROLE_LEVEL: Record<UserRole, number> = {
  super_admin: 4,
  admin: 3,
  manager: 2,
  user: 1,
};

export function hasMinimumRole(
  role: UserRole | undefined,
  minimumRole: UserRole
): boolean {
  if (!role) return false;
  return ROLE_LEVEL[role] >= ROLE_LEVEL[minimumRole];
}
