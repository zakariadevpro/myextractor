"use client";

import Link from "next/link";
import {
  Activity,
  CreditCard,
  Search,
  Settings,
  ShieldCheck,
  Users,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useAuth } from "@/hooks/use-auth";
import { hasMinimumRole } from "@/lib/authz";
import type { UserRole } from "@/types/user";

interface ActionItem {
  title: string;
  description: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  minRole: UserRole;
}

const ACTIONS: ActionItem[] = [
  {
    title: "Lancer une extraction",
    description: "Demarrer un job de collecte ciblee.",
    href: "/extraction",
    icon: Search,
    minRole: "manager",
  },
  {
    title: "Suivre l'audit",
    description: "Verifier les actions sensibles.",
    href: "/audit",
    icon: ShieldCheck,
    minRole: "manager",
  },
  {
    title: "Gerer l'equipe",
    description: "Administrer users et roles.",
    href: "/settings/team",
    icon: Users,
    minRole: "admin",
  },
  {
    title: "Pilotage abonnement",
    description: "Plan, usage et facturation.",
    href: "/settings/billing",
    icon: CreditCard,
    minRole: "admin",
  },
  {
    title: "Explorer les leads",
    description: "Filtrer et qualifier les fiches.",
    href: "/leads",
    icon: Activity,
    minRole: "user",
  },
  {
    title: "Configurer le CRM",
    description: "Parametres generaux du tenant.",
    href: "/settings",
    icon: Settings,
    minRole: "user",
  },
];

export function RoleActionsPanel() {
  const { user } = useAuth();
  const role = user?.role;

  const visibleActions = ACTIONS.filter((item) => hasMinimumRole(role, item.minRole));
  const roleLabel = role ? role.toUpperCase() : "UNKNOWN";

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <CardTitle>Actions Rapides</CardTitle>
        <Badge variant="outline">Role {roleLabel}</Badge>
      </CardHeader>
      <CardContent className="grid gap-3 sm:grid-cols-2">
        {visibleActions.map((item) => {
          const Icon = item.icon;
          return (
            <Link
              key={item.title}
              href={item.href}
              className="group rounded-lg border border-border bg-white p-4 transition hover:border-primary-300 hover:bg-primary-50/30"
            >
              <div className="flex items-start gap-3">
                <div className="rounded-md bg-slate-100 p-2 text-slate-600 group-hover:bg-primary-100 group-hover:text-primary-700">
                  <Icon className="h-4 w-4" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-slate-900">{item.title}</p>
                  <p className="mt-1 text-xs text-slate-500">{item.description}</p>
                </div>
              </div>
            </Link>
          );
        })}
      </CardContent>
    </Card>
  );
}
