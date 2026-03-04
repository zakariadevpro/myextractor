"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  Copy,
  KeyRound,
  Mail,
  ShieldCheck,
  SlidersHorizontal,
  ShieldAlert,
  Shield,
  Trash2,
  UserPlus,
  Users,
} from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { MetricCard } from "@/components/ui/metric-card";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useAuth } from "@/hooks/use-auth";
import {
  useApplyPermissionPreset,
  useCreateUser,
  useDeactivateUser,
  usePermissionCatalog,
  usePermissionPresets,
  useUpdateUser,
  useUpdateUserPermissions,
  useUserPermissions,
  useUsers,
} from "@/hooks/use-users";
import { useCurrentSubscription } from "@/hooks/use-subscriptions";
import { hasPermission } from "@/lib/authz";
import { getInitials } from "@/lib/utils";
import type { User, UserRole } from "@/types/user";

const roleLabels: Record<UserRole, string> = {
  super_admin: "Super Admin",
  admin: "Administrateur",
  manager: "Manager",
  user: "Utilisateur",
};

const roleBadgeVariant: Record<UserRole, "default" | "success" | "warning" | "secondary"> = {
  super_admin: "warning",
  admin: "default",
  manager: "success",
  user: "secondary",
};

const roleOptions = [
  { value: "admin", label: "Administrateur" },
  { value: "manager", label: "Manager" },
  { value: "user", label: "Utilisateur" },
] as const;

export default function TeamPage() {
  const { user } = useAuth();
  const canManageTeam = hasPermission(user?.effective_permissions, "users.manage");
  const canManagePermissions = hasPermission(
    user?.effective_permissions,
    "users.permissions.manage"
  );
  const [page, setPage] = useState(1);

  const [inviteDialogOpen, setInviteDialogOpen] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteFirstName, setInviteFirstName] = useState("");
  const [inviteLastName, setInviteLastName] = useState("");
  const [inviteRole, setInviteRole] = useState<UserRole>("user");
  const [createdCredentials, setCreatedCredentials] = useState<{
    email: string;
    temporary_password: string;
  } | null>(null);
  const [passwordCopied, setPasswordCopied] = useState(false);
  const [permissionsDialogOpen, setPermissionsDialogOpen] = useState(false);
  const [permissionsTarget, setPermissionsTarget] = useState<User | null>(null);
  const [editedPermissions, setEditedPermissions] = useState<string[]>([]);
  const [selectedPresetKey, setSelectedPresetKey] = useState("");

  const { data, isLoading } = useUsers({ page, page_size: 20 });
  const { data: currentSubscription } = useCurrentSubscription(canManageTeam);
  const { data: permissionCatalog } = usePermissionCatalog(canManagePermissions);
  const { data: permissionPresets } = usePermissionPresets(canManagePermissions);
  const { data: permissionSnapshot, isLoading: permissionsLoading } = useUserPermissions(
    permissionsTarget?.id
  );
  const createUser = useCreateUser();
  const updateUser = useUpdateUser();
  const updateUserPermissions = useUpdateUserPermissions();
  const applyPermissionPreset = useApplyPermissionPreset();
  const deactivateUser = useDeactivateUser();
  const members = useMemo(() => data?.items ?? [], [data?.items]);
  const totalPages = data?.total_pages ?? 1;
  const canAssignSuperAdmin = user?.role === "super_admin";
  const inviteRoleOptions = canAssignSuperAdmin
    ? [{ value: "super_admin", label: "Super Admin" }, ...roleOptions]
    : roleOptions;
  const maxUsers = currentSubscription?.plan.max_users ?? 1;

  const stats = useMemo(() => {
    const activeCount = members.filter((member) => member.is_active).length;
    const superAdminCount = members.filter((member) => member.role === "super_admin").length;
    const adminCount = members.filter((member) => member.role === "admin").length;
    const managerCount = members.filter((member) => member.role === "manager").length;
    return { activeCount, superAdminCount, adminCount, managerCount };
  }, [members]);
  const seatsRemaining = Math.max(0, maxUsers - stats.activeCount);
  const seatLimitReached = seatsRemaining <= 0;
  const permissionsByCategory = useMemo(() => {
    const groups: Record<string, typeof permissionCatalog> = {};
    for (const item of permissionCatalog ?? []) {
      const category = item.category || "other";
      if (!groups[category]) groups[category] = [];
      groups[category]?.push(item);
    }
    return groups;
  }, [permissionCatalog]);

  useEffect(() => {
    if (permissionSnapshot) {
      setEditedPermissions(permissionSnapshot.effective_permissions ?? []);
    }
  }, [permissionSnapshot]);

  useEffect(() => {
    if (!selectedPresetKey && (permissionPresets?.length ?? 0) > 0) {
      setSelectedPresetKey(permissionPresets?.[0]?.key ?? "");
    }
  }, [permissionPresets, selectedPresetKey]);

  const handleInvite = async () => {
    if (seatLimitReached) {
      toast.error("Limite d'utilisateurs atteinte pour votre plan.");
      return;
    }
    if (!inviteEmail || !inviteFirstName || !inviteLastName) {
      toast.error("Veuillez remplir email, prenom et nom.");
      return;
    }
    try {
      const created = await createUser.mutateAsync({
        email: inviteEmail,
        first_name: inviteFirstName,
        last_name: inviteLastName,
        role: inviteRole,
      });
      toast.success("Membre cree.");
      setCreatedCredentials({
        email: created.email,
        temporary_password: created.temporary_password,
      });
      setPasswordCopied(false);
      setInviteEmail("");
      setInviteFirstName("");
      setInviteLastName("");
      setInviteRole("user");
      setInviteDialogOpen(false);
    } catch {
      toast.error("Erreur lors de la creation du membre.");
    }
  };

  const toggleRole = async (member: User) => {
    if (member.role === "admin" || member.role === "super_admin") {
      toast.error("Ce role ne peut pas etre modifie depuis ce bouton.");
      return;
    }
    const nextRole: UserRole = member.role === "user" ? "manager" : "user";
    try {
      await updateUser.mutateAsync({ userId: member.id, role: nextRole });
      toast.success(`Role mis a jour: ${roleLabels[nextRole]}.`);
    } catch {
      toast.error("Impossible de modifier le role.");
    }
  };

  const handleDeactivate = async (member: User) => {
    try {
      const result = await deactivateUser.mutateAsync(member.id);
      toast.success(result.message || "Membre desactive.");
    } catch {
      toast.error("Impossible de desactiver ce membre.");
    }
  };

  const handleCopyPassword = async () => {
    if (!createdCredentials) return;
    try {
      await navigator.clipboard.writeText(createdCredentials.temporary_password);
      setPasswordCopied(true);
      toast.success("Mot de passe temporaire copie.");
    } catch {
      toast.error("Impossible de copier le mot de passe.");
    }
  };

  const openPermissionsDialog = (member: User) => {
    setPermissionsTarget(member);
    if ((permissionPresets?.length ?? 0) > 0) {
      setSelectedPresetKey(permissionPresets?.[0]?.key ?? "");
    }
    setPermissionsDialogOpen(true);
  };

  const togglePermissionSelection = (permission: string) => {
    setEditedPermissions((prev) => {
      const set = new Set(prev);
      if (set.has(permission)) {
        set.delete(permission);
      } else {
        set.add(permission);
      }
      return Array.from(set).sort();
    });
  };

  const handleSavePermissions = async () => {
    if (!permissionsTarget || !permissionSnapshot) return;
    const defaultSet = new Set(permissionSnapshot.default_permissions);
    const editedSet = new Set(editedPermissions);

    const grants = Array.from(editedSet).filter((perm) => !defaultSet.has(perm));
    const revokes = Array.from(defaultSet).filter((perm) => !editedSet.has(perm));

    try {
      await updateUserPermissions.mutateAsync({
        userId: permissionsTarget.id,
        grants,
        revokes,
      });
      toast.success("Permissions mises a jour.");
      setPermissionsDialogOpen(false);
      setPermissionsTarget(null);
    } catch {
      toast.error("Impossible de mettre a jour les permissions.");
    }
  };

  const handleApplyPreset = async () => {
    if (!permissionsTarget || !selectedPresetKey) return;
    try {
      const snapshot = await applyPermissionPreset.mutateAsync({
        userId: permissionsTarget.id,
        presetKey: selectedPresetKey,
      });
      setEditedPermissions(snapshot.effective_permissions ?? []);
      toast.success("Preset applique.");
    } catch {
      toast.error("Impossible d'appliquer le preset.");
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Equipe"
        description="Gestion des utilisateurs, roles et acces de ton organisation."
        badges={
          <>
            <Badge variant="outline">Role {user?.role || "user"}</Badge>
            {canManageTeam ? (
              <Badge variant="success">Administration active</Badge>
            ) : (
              <Badge variant="secondary">Consultation</Badge>
            )}
          </>
        }
        actions={
          <>
            <Link href="/settings">
              <Button variant="outline" className="gap-2">
                <ArrowLeft className="h-4 w-4" />
                Retour Parametres
              </Button>
            </Link>
            {canManagePermissions ? (
              <Link href="/settings/permissions-matrix">
                <Button variant="outline" className="gap-2">
                  <ShieldCheck className="h-4 w-4" />
                  Matrice Permissions
                </Button>
              </Link>
            ) : null}
            {canManageTeam ? (
              <Button
                className="gap-2"
                onClick={() => setInviteDialogOpen(true)}
                disabled={seatLimitReached}
              >
                <UserPlus className="h-4 w-4" />
                Nouveau membre
              </Button>
            ) : null}
          </>
        }
      />

      {canManageTeam && seatLimitReached ? (
        <Card className="border-warning/40 bg-warning/5">
          <CardContent className="flex items-center gap-3 p-4">
            <ShieldAlert className="h-5 w-5 text-warning" />
            <p className="text-sm text-slate-800">
              Limite atteinte: {stats.activeCount}/{maxUsers} utilisateurs actifs. Passez sur un plan
              supérieur pour ajouter des membres.
            </p>
          </CardContent>
        </Card>
      ) : null}

      <div className="grid gap-4 md:grid-cols-4">
        <MetricCard
          label="Membres"
          value={data?.total ?? 0}
          helper="Comptes utilisateurs"
          icon={<Users className="h-4 w-4" />}
        />
        <MetricCard
          label="Actifs"
          value={stats.activeCount}
          helper={`${stats.managerCount} managers`}
          icon={<Shield className="h-4 w-4" />}
        />
        <MetricCard
          label="Sieges Actifs"
          value={`${stats.activeCount}/${maxUsers}`}
          helper={`${seatsRemaining} disponibles`}
          icon={<KeyRound className="h-4 w-4" />}
        />
        <MetricCard
          label="Admins+"
          value={stats.adminCount + stats.superAdminCount}
          helper={`${stats.superAdminCount} super admin`}
          icon={<Mail className="h-4 w-4" />}
        />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Membres ({data?.total ?? 0})</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto rounded-lg border border-border">
            <table className="min-w-full divide-y divide-border text-sm">
              <thead className="bg-slate-50">
                <tr>
                  <th className="px-3 py-2 text-left font-medium text-slate-600">Membre</th>
                  <th className="px-3 py-2 text-left font-medium text-slate-600">Role</th>
                  <th className="px-3 py-2 text-left font-medium text-slate-600">Statut</th>
                  <th className="px-3 py-2 text-left font-medium text-slate-600">Creation</th>
                  <th className="px-3 py-2 text-right font-medium text-slate-600">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border bg-white">
                {isLoading ? (
                  <tr>
                    <td colSpan={5} className="px-3 py-6 text-center text-muted-foreground">
                      Chargement de l&apos;equipe...
                    </td>
                  </tr>
                ) : members.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-3 py-6 text-center text-muted-foreground">
                      Aucun membre trouve.
                    </td>
                  </tr>
                ) : (
                  members.map((member) => {
                    const memberName =
                      `${member.first_name || ""} ${member.last_name || ""}`.trim() || member.email;
                    const isCurrentUser = member.id === user?.id;

                    return (
                      <tr key={member.id}>
                        <td className="px-3 py-2">
                          <div className="flex items-center gap-3">
                            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary-50 text-xs font-semibold text-primary-700">
                              {getInitials(memberName)}
                            </div>
                            <div>
                              <p className="font-medium text-slate-900">{memberName}</p>
                              <p className="text-xs text-muted-foreground">{member.email}</p>
                            </div>
                          </div>
                        </td>
                        <td className="px-3 py-2">
                          <Badge variant={roleBadgeVariant[member.role]}>
                            {roleLabels[member.role]}
                          </Badge>
                        </td>
                        <td className="px-3 py-2">
                          <Badge variant={member.is_active ? "success" : "secondary"}>
                            {member.is_active ? "Actif" : "Inactif"}
                          </Badge>
                        </td>
                        <td className="px-3 py-2 text-slate-600">
                          {new Date(member.created_at).toLocaleDateString("fr-FR")}
                        </td>
                        <td className="px-3 py-2">
                          <div className="flex justify-end gap-2">
                            {canManagePermissions && !isCurrentUser ? (
                              <Button
                                size="sm"
                                variant="outline"
                                className="gap-1"
                                onClick={() => openPermissionsDialog(member)}
                              >
                                <SlidersHorizontal className="h-3.5 w-3.5" />
                                Permissions
                              </Button>
                            ) : null}
                            {canManageTeam &&
                            !isCurrentUser &&
                            member.role !== "admin" &&
                            member.role !== "super_admin" ? (
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => toggleRole(member)}
                                isLoading={updateUser.isPending}
                              >
                                {member.role === "user" ? "Promouvoir" : "Retrograder"}
                              </Button>
                            ) : null}
                            {canManageTeam && !isCurrentUser && member.is_active ? (
                              <Button
                                size="sm"
                                variant="outline"
                                className="text-danger"
                                onClick={() => handleDeactivate(member)}
                                isLoading={deactivateUser.isPending}
                              >
                                <Trash2 className="h-4 w-4" />
                              </Button>
                            ) : null}
                            {!canManagePermissions && !canManageTeam ? (
                              <span className="text-xs text-muted-foreground">-</span>
                            ) : null}
                          </div>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>

          {totalPages > 1 ? (
            <div className="mt-4 flex items-center justify-between">
              <p className="text-sm text-muted-foreground">
                Page {page} / {totalPages}
              </p>
              <div className="flex gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                >
                  Precedent
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => p + 1)}
                >
                  Suivant
                </Button>
              </div>
            </div>
          ) : null}
        </CardContent>
      </Card>

      <Dialog open={inviteDialogOpen} onOpenChange={setInviteDialogOpen}>
        <DialogContent onClose={() => setInviteDialogOpen(false)}>
          <DialogHeader>
            <DialogTitle>Ajouter un membre</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <Input
              label="Email"
              type="email"
              value={inviteEmail}
              onChange={(e) => setInviteEmail(e.target.value)}
            />
            <div className="grid gap-3 sm:grid-cols-2">
              <Input
                label="Prenom"
                value={inviteFirstName}
                onChange={(e) => setInviteFirstName(e.target.value)}
              />
              <Input
                label="Nom"
                value={inviteLastName}
                onChange={(e) => setInviteLastName(e.target.value)}
              />
            </div>
            <Select
              label="Role"
              value={inviteRole}
              onChange={(e) => setInviteRole(e.target.value as UserRole)}
              options={[...inviteRoleOptions]}
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setInviteDialogOpen(false)}>
              Annuler
            </Button>
            <Button
              onClick={handleInvite}
              isLoading={createUser.isPending}
              disabled={seatLimitReached}
            >
              Creer membre
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={Boolean(createdCredentials)} onOpenChange={() => setCreatedCredentials(null)}>
        <DialogContent onClose={() => setCreatedCredentials(null)}>
          <DialogHeader>
            <DialogTitle>Identifiants Temporaires</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 text-sm">
            <p className="text-muted-foreground">
              Communique ce mot de passe temporaire au nouvel utilisateur, puis impose un changement au
              premier login.
            </p>
            <Input label="Email" value={createdCredentials?.email ?? ""} readOnly />
            <Input
              label="Mot de passe temporaire"
              value={createdCredentials?.temporary_password ?? ""}
              readOnly
            />
          </div>
          <DialogFooter>
            <Button variant="outline" className="gap-2" onClick={handleCopyPassword}>
              <Copy className="h-4 w-4" />
              {passwordCopied ? "Copie" : "Copier"}
            </Button>
            <Button onClick={() => setCreatedCredentials(null)}>Fermer</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={permissionsDialogOpen}
        onOpenChange={(open) => {
          setPermissionsDialogOpen(open);
          if (!open) {
            setPermissionsTarget(null);
          }
        }}
      >
        <DialogContent onClose={() => setPermissionsDialogOpen(false)}>
          <DialogHeader>
            <DialogTitle>
              Permissions Utilisateur
              {permissionsTarget ? ` - ${permissionsTarget.email}` : ""}
            </DialogTitle>
          </DialogHeader>
          {permissionsLoading || !permissionSnapshot ? (
            <p className="text-sm text-muted-foreground">Chargement des permissions...</p>
          ) : (
            <div className="max-h-[60vh] space-y-4 overflow-y-auto pr-1">
              <div className="rounded-md border border-border p-3">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
                  <div className="flex-1">
                    <Select
                      label="Preset rapide"
                      value={selectedPresetKey}
                      onChange={(e) => setSelectedPresetKey(e.target.value)}
                      options={(permissionPresets ?? []).map((preset) => ({
                        value: preset.key,
                        label: preset.label,
                      }))}
                    />
                  </div>
                  <Button
                    variant="outline"
                    onClick={handleApplyPreset}
                    isLoading={applyPermissionPreset.isPending}
                    disabled={!selectedPresetKey}
                  >
                    Appliquer preset
                  </Button>
                </div>
                {selectedPresetKey ? (
                  <p className="mt-2 text-xs text-muted-foreground">
                    {(permissionPresets ?? []).find((preset) => preset.key === selectedPresetKey)
                      ?.description ?? ""}
                  </p>
                ) : null}
              </div>
              {Object.entries(permissionsByCategory).map(([category, items]) => (
                <div key={category} className="rounded-md border border-border p-3">
                  <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
                    {category}
                  </p>
                  <div className="space-y-2">
                    {items?.map((item) => {
                      const checked = editedPermissions.includes(item.key);
                      const inherited = permissionSnapshot.default_permissions.includes(item.key);
                      return (
                        <label key={item.key} className="flex items-start gap-2 text-sm">
                          <input
                            type="checkbox"
                            className="mt-0.5 h-4 w-4 rounded border-border"
                            checked={checked}
                            onChange={() => togglePermissionSelection(item.key)}
                          />
                          <span>
                            <span className="font-medium text-slate-900">{item.label}</span>
                            <span className="ml-2 text-xs text-muted-foreground">{item.key}</span>
                            <br />
                            <span className="text-xs text-muted-foreground">{item.description}</span>
                            {inherited ? (
                              <span className="ml-2 inline-block text-[11px] text-primary">
                                (par role)
                              </span>
                            ) : null}
                          </span>
                        </label>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setPermissionsDialogOpen(false)}>
              Annuler
            </Button>
            <Button
              onClick={handleSavePermissions}
              isLoading={updateUserPermissions.isPending}
              disabled={!permissionSnapshot}
            >
              Enregistrer
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
