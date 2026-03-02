"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  Mail,
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
import { useCreateUser, useDeactivateUser, useUpdateUser, useUsers } from "@/hooks/use-users";
import { hasMinimumRole } from "@/lib/authz";
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
  const canManageTeam = hasMinimumRole(user?.role, "admin");
  const [page, setPage] = useState(1);

  const [inviteDialogOpen, setInviteDialogOpen] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteFirstName, setInviteFirstName] = useState("");
  const [inviteLastName, setInviteLastName] = useState("");
  const [inviteRole, setInviteRole] = useState<UserRole>("user");

  const { data, isLoading } = useUsers({ page, page_size: 20 });
  const createUser = useCreateUser();
  const updateUser = useUpdateUser();
  const deactivateUser = useDeactivateUser();
  const members = useMemo(() => data?.items ?? [], [data?.items]);
  const totalPages = data?.total_pages ?? 1;
  const canAssignSuperAdmin = user?.role === "super_admin";
  const inviteRoleOptions = canAssignSuperAdmin
    ? [{ value: "super_admin", label: "Super Admin" }, ...roleOptions]
    : roleOptions;

  const stats = useMemo(() => {
    const activeCount = members.filter((member) => member.is_active).length;
    const superAdminCount = members.filter((member) => member.role === "super_admin").length;
    const adminCount = members.filter((member) => member.role === "admin").length;
    const managerCount = members.filter((member) => member.role === "manager").length;
    return { activeCount, superAdminCount, adminCount, managerCount };
  }, [members]);

  const handleInvite = async () => {
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
      toast.success(`Membre cree. Mot de passe temporaire: ${created.temporary_password}`);
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
            {canManageTeam ? (
              <Button className="gap-2" onClick={() => setInviteDialogOpen(true)}>
                <UserPlus className="h-4 w-4" />
                Nouveau membre
              </Button>
            ) : null}
          </>
        }
      />

      <div className="grid gap-4 md:grid-cols-3">
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
                            {canManageTeam &&
                            !isCurrentUser &&
                            member.role !== "admin" &&
                            member.role !== "super_admin" ? (
                              <>
                                <Button
                                  size="sm"
                                  variant="outline"
                                  onClick={() => toggleRole(member)}
                                  isLoading={updateUser.isPending}
                                >
                                  {member.role === "user" ? "Promouvoir" : "Retrograder"}
                                </Button>
                                {member.is_active ? (
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
                              </>
                            ) : (
                              <span className="text-xs text-muted-foreground">-</span>
                            )}
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
            <Button onClick={handleInvite} isLoading={createUser.isPending}>
              Creer membre
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
