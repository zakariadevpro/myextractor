"use client";

import { useEffect } from "react";
import Link from "next/link";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import {
  Building2,
  CreditCard,
  KeyRound,
  Workflow,
  BrainCircuit,
  Users as UsersIcon,
  Save,
  ShieldCheck,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { MetricCard } from "@/components/ui/metric-card";
import { PageHeader } from "@/components/layout/page-header";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { hasMinimumRole } from "@/lib/authz";
import { useOrganization, useUpdateOrganization } from "@/hooks/use-organization";
import { useAuth } from "@/hooks/use-auth";

const settingsSchema = z.object({
  organization_name: z.string().min(2, "Le nom doit contenir au moins 2 caracteres"),
});

type SettingsFormData = z.infer<typeof settingsSchema>;

export default function SettingsPage() {
  const { user } = useAuth();
  const canManageSettings = hasMinimumRole(user?.role, "admin");
  const { data: organization } = useOrganization();
  const updateOrganization = useUpdateOrganization();

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<SettingsFormData>({
    resolver: zodResolver(settingsSchema),
    defaultValues: {
      organization_name: "",
    },
  });

  useEffect(() => {
    if (organization?.name) {
      reset({ organization_name: organization.name });
    } else if (user?.organization_name) {
      reset({ organization_name: user.organization_name });
    }
  }, [organization?.name, reset, user?.organization_name]);

  const onSubmit = async (data: SettingsFormData) => {
    if (!canManageSettings) {
      toast.error("Seul un admin peut modifier les parametres d'organisation.");
      return;
    }

    try {
      await updateOrganization.mutateAsync(data);
      toast.success("Parametres mis a jour avec succes.");
    } catch {
      toast.error("Erreur lors de la mise a jour des parametres.");
    }
  };

  const settingsNav = [
    {
      label: "Facturation",
      href: "/settings/billing",
      icon: CreditCard,
      description: "Gerez votre abonnement et votre facturation",
    },
    {
      label: "Equipe",
      href: "/settings/team",
      icon: UsersIcon,
      description: "Gerez les membres de votre equipe",
    },
    {
      label: "Matrice Permissions",
      href: "/settings/permissions-matrix",
      icon: ShieldCheck,
      description: "Vue globale et actions en lot sur les permissions",
    },
    {
      label: "API Keys",
      href: "/settings/api-keys",
      icon: KeyRound,
      description: "Acces API securises pour integrations externes",
    },
    {
      label: "Workflows",
      href: "/settings/workflows",
      icon: Workflow,
      description: "Automatisations post-extraction et manuelles",
    },
    {
      label: "Scoring IA",
      href: "/settings/scoring",
      icon: BrainCircuit,
      description: "Seuils et poids de scoring configurables",
    },
  ];

  return (
    <div className="space-y-8">
      <PageHeader
        title="Parametres"
        description="Configuration de l'organisation, de l'equipe et de la facturation."
        badges={
          <>
            <Badge variant="outline">Role {user?.role || "user"}</Badge>
            {canManageSettings ? (
              <Badge variant="success">Edition active</Badge>
            ) : (
              <Badge variant="secondary">Lecture seule</Badge>
            )}
          </>
        }
      />

      <div className="grid gap-4 md:grid-cols-3">
        <MetricCard
          label="Organisation"
          value={organization?.name || user?.organization_name || "N/A"}
          helper={`Slug: ${organization?.slug || "n/a"}`}
          icon={<Building2 className="h-4 w-4" />}
        />
        <MetricCard
          label="Role Actuel"
          value={(user?.role || "user").toUpperCase()}
          helper="Controle les droits dans le CRM"
          icon={<UsersIcon className="h-4 w-4" />}
        />
        <MetricCard
          label="Statut Organisation"
          value={organization?.is_active ? "ACTIVE" : "INACTIVE"}
          helper="Disponibilite du tenant"
          icon={<CreditCard className="h-4 w-4" />}
        />
      </div>

      <div className="grid gap-8 lg:grid-cols-3">
        {/* Main Settings */}
        <div className="space-y-6 lg:col-span-2">
          {/* Organization Settings */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Building2 className="h-5 w-5 text-primary" />
                Organisation
              </CardTitle>
              <CardDescription>
                Informations generales de votre organisation.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
                <Input
                  id="organization_name"
                  label="Nom de l'organisation"
                  placeholder="Mon Entreprise SAS"
                  error={errors.organization_name?.message}
                  disabled={!canManageSettings}
                  {...register("organization_name")}
                />
                <div className="grid gap-4 sm:grid-cols-2">
                  <Input
                    label="Email du proprietaire"
                    value={user?.email ?? ""}
                    disabled
                  />
                  <Input
                    label="Role"
                    value={user?.role ?? "admin"}
                    disabled
                  />
                </div>
                <div className="flex justify-end">
                  <Button
                    type="submit"
                    className="gap-2"
                    isLoading={updateOrganization.isPending}
                    disabled={!canManageSettings}
                  >
                    <Save className="h-4 w-4" />
                    Enregistrer
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>
        </div>

        {/* Settings Navigation */}
        <div className="space-y-4">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
            Autres parametres
          </h2>
          {settingsNav.map((item) => {
            const Icon = item.icon;
            return (
              <Link key={item.href} href={item.href}>
                <Card className="card-hover cursor-pointer">
                  <CardContent className="flex items-center gap-4 p-4">
                    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary-50">
                      <Icon className="h-5 w-5 text-primary" />
                    </div>
                    <div>
                      <p className="text-sm font-medium text-slate-900">
                        {item.label}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {item.description}
                      </p>
                    </div>
                  </CardContent>
                </Card>
              </Link>
            );
          })}
        </div>
      </div>
    </div>
  );
}
