"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { ArrowLeft, Download, ShieldCheck } from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/layout/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { useAuth } from "@/hooks/use-auth";
import {
  useApplyPermissionPreset,
  usePermissionCatalog,
  usePermissionPresets,
  useUsers,
  useUsersPermissionsMatrix,
} from "@/hooks/use-users";
import { hasPermission } from "@/lib/authz";
import type { UserRole } from "@/types/user";

const ROLE_OPTIONS: Array<{ value: UserRole | "all"; label: string }> = [
  { value: "all", label: "Tous les roles" },
  { value: "super_admin", label: "Super Admin" },
  { value: "admin", label: "Administrateur" },
  { value: "manager", label: "Manager" },
  { value: "user", label: "Utilisateur" },
];

function escapeCsvCell(value: string): string {
  const text = String(value ?? "");
  if (text.includes(",") || text.includes('"') || text.includes("\n")) {
    return `"${text.replace(/"/g, '""')}"`;
  }
  return text;
}

export default function PermissionsMatrixPage() {
  const { user } = useAuth();
  const canViewUsers = hasPermission(user?.effective_permissions, "users.view");
  const canManagePermissions = hasPermission(user?.effective_permissions, "users.permissions.manage");

  const [search, setSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState<UserRole | "all">("all");
  const [presetFilter, setPresetFilter] = useState("all");
  const [batchPreset, setBatchPreset] = useState("");
  const [selectedUserIds, setSelectedUserIds] = useState<Set<string>>(new Set());
  const [isBatchApplying, setIsBatchApplying] = useState(false);

  const { data: usersPage, isLoading: usersLoading } = useUsers({ page: 1, page_size: 100 });
  const members = useMemo(() => usersPage?.items ?? [], [usersPage?.items]);
  const userIds = useMemo(() => members.map((member) => member.id), [members]);

  const { data: permissionCatalog = [] } = usePermissionCatalog(canViewUsers);
  const { data: permissionPresets = [] } = usePermissionPresets(canViewUsers);
  const { data: permissionMatrix = {}, isLoading: matrixLoading } = useUsersPermissionsMatrix(
    userIds,
    canViewUsers
  );
  const applyPermissionPreset = useApplyPermissionPreset();

  const filteredMembers = useMemo(() => {
    const query = search.trim().toLowerCase();
    const selectedPreset = permissionPresets.find((item) => item.key === presetFilter);

    return members.filter((member) => {
      const fullName = `${member.first_name || ""} ${member.last_name || ""}`.trim().toLowerCase();
      const email = (member.email || "").toLowerCase();
      if (query && !fullName.includes(query) && !email.includes(query)) {
        return false;
      }
      if (roleFilter !== "all" && member.role !== roleFilter) {
        return false;
      }
      if (selectedPreset) {
        const snapshot = permissionMatrix[member.id];
        const effective = new Set(snapshot?.effective_permissions ?? []);
        if (!selectedPreset.permissions.every((permission) => effective.has(permission))) {
          return false;
        }
      }
      return true;
    });
  }, [members, permissionMatrix, permissionPresets, presetFilter, roleFilter, search]);

  const permissionKeys = useMemo(
    () => permissionCatalog.map((permission) => permission.key),
    [permissionCatalog]
  );

  const allVisibleSelectableIds = useMemo(
    () => filteredMembers.filter((member) => member.id !== user?.id).map((member) => member.id),
    [filteredMembers, user?.id]
  );

  const allVisibleSelected =
    allVisibleSelectableIds.length > 0 &&
    allVisibleSelectableIds.every((id) => selectedUserIds.has(id));

  const toggleRowSelection = (userId: string) => {
    setSelectedUserIds((prev) => {
      const next = new Set(prev);
      if (next.has(userId)) next.delete(userId);
      else next.add(userId);
      return next;
    });
  };

  const toggleSelectAllVisible = () => {
    setSelectedUserIds((prev) => {
      const next = new Set(prev);
      if (allVisibleSelected) {
        allVisibleSelectableIds.forEach((id) => next.delete(id));
      } else {
        allVisibleSelectableIds.forEach((id) => next.add(id));
      }
      return next;
    });
  };

  const handleBatchApplyPreset = async () => {
    if (!batchPreset) {
      toast.error("Selectionne un preset a appliquer.");
      return;
    }
    const targets = Array.from(selectedUserIds).filter((id) => id !== user?.id);
    if (targets.length === 0) {
      toast.error("Selectionne au moins un utilisateur.");
      return;
    }

    setIsBatchApplying(true);
    let success = 0;
    let failed = 0;
    for (const userId of targets) {
      try {
        await applyPermissionPreset.mutateAsync({ userId, presetKey: batchPreset });
        success += 1;
      } catch {
        failed += 1;
      }
    }
    setIsBatchApplying(false);
    if (failed === 0) {
      toast.success(`Preset applique a ${success} utilisateur(s).`);
    } else {
      toast.error(`Preset applique a ${success}, echec sur ${failed}.`);
    }
  };

  const handleExportCsv = () => {
    const headers = ["email", "first_name", "last_name", "role", "is_active", ...permissionKeys];
    const rows = filteredMembers.map((member) => {
      const snapshot = permissionMatrix[member.id];
      const effective = new Set(snapshot?.effective_permissions ?? []);
      return [
        member.email,
        member.first_name || "",
        member.last_name || "",
        member.role,
        member.is_active ? "1" : "0",
        ...permissionKeys.map((permission) => (effective.has(permission) ? "1" : "0")),
      ];
    });
    const csv = [headers, ...rows]
      .map((row) => row.map((cell) => escapeCsvCell(String(cell))).join(","))
      .join("\n");
    const blob = new Blob([`\uFEFF${csv}`], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `permissions_matrix_${new Date().toISOString().slice(0, 10)}.csv`;
    anchor.click();
    URL.revokeObjectURL(url);
    toast.success("Matrice exportee en CSV.");
  };

  if (!canViewUsers) {
    return (
      <div className="space-y-6">
        <PageHeader
          title="Matrice Permissions"
          description="Vue globale des permissions par utilisateur."
        />
        <Card>
          <CardContent className="p-6 text-sm text-muted-foreground">
            Permission insuffisante: `users.view` est requise.
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Matrice Permissions"
        description="Controle global des permissions par utilisateur, presets et export."
        badges={
          <>
            <Badge variant="outline">{filteredMembers.length} utilisateurs visibles</Badge>
            <Badge variant="secondary">{selectedUserIds.size} selectionnes</Badge>
            <Badge variant="outline">{permissionKeys.length} permissions</Badge>
          </>
        }
        actions={
          <>
            <Link href="/settings/team">
              <Button variant="outline" className="gap-2">
                <ArrowLeft className="h-4 w-4" />
                Retour Equipe
              </Button>
            </Link>
            <Button variant="outline" className="gap-2" onClick={handleExportCsv}>
              <Download className="h-4 w-4" />
              Export CSV
            </Button>
          </>
        }
      />

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ShieldCheck className="h-5 w-5 text-primary" />
            Filtres et Actions en lot
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 lg:grid-cols-4">
            <Input
              label="Recherche utilisateur"
              placeholder="Nom ou email"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
            <Select
              label="Filtre role"
              value={roleFilter}
              onChange={(event) => setRoleFilter(event.target.value as UserRole | "all")}
              options={ROLE_OPTIONS.map((item) => ({ value: item.value, label: item.label }))}
            />
            <Select
              label="Filtre preset"
              value={presetFilter}
              onChange={(event) => setPresetFilter(event.target.value)}
              options={[
                { value: "all", label: "Tous les presets" },
                ...permissionPresets.map((preset) => ({
                  value: preset.key,
                  label: preset.label,
                })),
              ]}
            />
            <Select
              label="Preset batch"
              value={batchPreset}
              onChange={(event) => setBatchPreset(event.target.value)}
              options={[
                { value: "", label: "Selectionner un preset" },
                ...permissionPresets.map((preset) => ({
                  value: preset.key,
                  label: preset.label,
                })),
              ]}
            />
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button variant="outline" onClick={toggleSelectAllVisible}>
              {allVisibleSelected ? "Deselectionner visibles" : "Selectionner visibles"}
            </Button>
            <Button
              onClick={handleBatchApplyPreset}
              isLoading={isBatchApplying || applyPermissionPreset.isPending}
              disabled={!canManagePermissions}
            >
              Appliquer preset en lot
            </Button>
            {!canManagePermissions ? (
              <span className="text-xs text-muted-foreground">
                Permission requise: `users.permissions.manage`
              </span>
            ) : null}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Tableau Matrice</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto rounded-lg border border-border">
            <table className="min-w-full divide-y divide-border text-xs">
              <thead className="bg-slate-50">
                <tr>
                  <th className="px-2 py-2 text-left font-semibold text-slate-700">Sel.</th>
                  <th className="px-2 py-2 text-left font-semibold text-slate-700">Utilisateur</th>
                  <th className="px-2 py-2 text-left font-semibold text-slate-700">Role</th>
                  <th className="px-2 py-2 text-left font-semibold text-slate-700">Actif</th>
                  {permissionCatalog.map((permission) => (
                    <th
                      key={permission.key}
                      className="whitespace-nowrap px-2 py-2 text-left font-semibold text-slate-700"
                      title={`${permission.label} - ${permission.description}`}
                    >
                      {permission.key}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-border bg-white">
                {usersLoading || matrixLoading ? (
                  <tr>
                    <td colSpan={4 + permissionCatalog.length} className="px-3 py-6 text-center">
                      Chargement de la matrice...
                    </td>
                  </tr>
                ) : filteredMembers.length === 0 ? (
                  <tr>
                    <td colSpan={4 + permissionCatalog.length} className="px-3 py-6 text-center">
                      Aucun utilisateur sur ce filtre.
                    </td>
                  </tr>
                ) : (
                  filteredMembers.map((member) => {
                    const isSelf = member.id === user?.id;
                    const snapshot = permissionMatrix[member.id];
                    const effective = new Set(snapshot?.effective_permissions ?? []);
                    return (
                      <tr key={member.id}>
                        <td className="px-2 py-2">
                          <input
                            type="checkbox"
                            checked={selectedUserIds.has(member.id)}
                            disabled={isSelf}
                            onChange={() => toggleRowSelection(member.id)}
                          />
                        </td>
                        <td className="whitespace-nowrap px-2 py-2">
                          <div className="font-medium text-slate-900">
                            {`${member.first_name || ""} ${member.last_name || ""}`.trim() ||
                              member.email}
                          </div>
                          <div className="text-[11px] text-muted-foreground">{member.email}</div>
                        </td>
                        <td className="px-2 py-2">{member.role}</td>
                        <td className="px-2 py-2">{member.is_active ? "Oui" : "Non"}</td>
                        {permissionKeys.map((permissionKey) => (
                          <td key={`${member.id}:${permissionKey}`} className="px-2 py-2 text-center">
                            {effective.has(permissionKey) ? "✓" : "·"}
                          </td>
                        ))}
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
