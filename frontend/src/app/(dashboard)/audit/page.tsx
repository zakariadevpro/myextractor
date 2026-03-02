"use client";

import { useMemo, useState } from "react";
import { ShieldAlert, ShieldCheck } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { MetricCard } from "@/components/ui/metric-card";
import { useAuth } from "@/hooks/use-auth";
import { useAuditLogs, useAuditSummary } from "@/hooks/use-audit";
import { hasMinimumRole } from "@/lib/authz";

const LOOKBACK_OPTIONS = [
  { value: "24", label: "24h" },
  { value: "72", label: "3 jours" },
  { value: "168", label: "7 jours" },
];

const RESOURCE_OPTIONS = [
  { value: "", label: "Toutes ressources" },
  { value: "user", label: "Users" },
  { value: "lead", label: "Leads" },
  { value: "extraction_job", label: "Extraction" },
  { value: "subscription", label: "Subscription" },
  { value: "system", label: "System" },
];

function getActionBadgeVariant(action: string): "default" | "warning" | "danger" | "success" {
  if (action.includes("delete") || action.includes("deactivate")) return "danger";
  if (action.includes("cancel")) return "warning";
  if (action.includes("login") || action.includes("create") || action.includes("activated")) {
    return "success";
  }
  return "default";
}

export default function AuditPage() {
  const { user } = useAuth();
  const [sinceHours, setSinceHours] = useState(24);
  const [page, setPage] = useState(1);
  const [action, setAction] = useState("");
  const [resourceType, setResourceType] = useState("");

  const canAccess = hasMinimumRole(user?.role, "manager");
  const { data: summary, isLoading: summaryLoading } = useAuditSummary(sinceHours);
  const { data: logs, isLoading: logsLoading } = useAuditLogs({
    page,
    page_size: 20,
    action: action || undefined,
    resource_type: resourceType || undefined,
  });

  const topActions = useMemo(
    () => (summary?.events_by_action ?? []).slice(0, 8),
    [summary?.events_by_action]
  );

  if (!canAccess) {
    return (
      <div className="space-y-6">
        <PageHeader
          title="Audit"
          description="Journal de securite et operations sensibles."
          badges={<Badge variant="secondary">Acces restreint</Badge>}
        />
        <Card className="border-warning/30 bg-warning-light/20">
          <CardContent className="flex items-start gap-3 p-6">
            <ShieldAlert className="mt-0.5 h-5 w-5 text-warning" />
            <div>
              <p className="font-medium text-slate-900">Acces reserve</p>
              <p className="mt-1 text-sm text-slate-600">
                Cette section est accessible aux roles <strong>manager</strong> et{" "}
                <strong>admin</strong>.
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Audit & Securite"
        description="Tracabilite des actions sensibles sur ton CRM d'extraction."
        badges={<Badge variant="success">Monitor actif</Badge>}
        actions={
          <Select
            className="w-40"
            value={String(sinceHours)}
            onChange={(e) => setSinceHours(Number(e.target.value))}
            options={LOOKBACK_OPTIONS}
          />
        }
      />

      <div className="grid gap-4 md:grid-cols-3">
        <MetricCard
          label="Evenements"
          value={summaryLoading ? "..." : summary?.total_events ?? 0}
          helper="Logs traces dans la fenetre"
        />
        <MetricCard
          label="Acteurs Uniques"
          value={summaryLoading ? "..." : summary?.unique_actors ?? 0}
          helper="Utilisateurs differents"
        />
        <MetricCard
          label="Fenetre Active"
          value={`${sinceHours}h`}
          helper="Perimetre analyse"
          icon={<ShieldCheck className="h-4 w-4 text-success" />}
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle>Top actions</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {topActions.length === 0 ? (
              <p className="text-sm text-muted-foreground">Aucune action sur cette periode.</p>
            ) : (
              topActions.map((item) => (
                <div
                  key={item.action}
                  className="flex items-center justify-between rounded-lg border border-border px-3 py-2"
                >
                  <span className="text-sm text-slate-700">{item.action}</span>
                  <Badge variant="outline">{item.count}</Badge>
                </div>
              ))
            )}
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Logs recents</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-3">
              <Input
                placeholder="Filtrer action (ex: auth.login)"
                value={action}
                onChange={(e) => {
                  setAction(e.target.value);
                  setPage(1);
                }}
              />
              <Select
                value={resourceType}
                onChange={(e) => {
                  setResourceType(e.target.value);
                  setPage(1);
                }}
                options={RESOURCE_OPTIONS}
              />
              <Button variant="outline" onClick={() => {
                setAction("");
                setResourceType("");
                setPage(1);
              }}>
                Reinitialiser filtres
              </Button>
            </div>

            <div className="overflow-x-auto rounded-lg border border-border">
              <table className="min-w-full divide-y divide-border text-sm">
                <thead className="bg-slate-50">
                  <tr>
                    <th className="px-3 py-2 text-left font-medium text-slate-600">Date</th>
                    <th className="px-3 py-2 text-left font-medium text-slate-600">Action</th>
                    <th className="px-3 py-2 text-left font-medium text-slate-600">Ressource</th>
                    <th className="px-3 py-2 text-left font-medium text-slate-600">Actor</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border bg-white">
                  {logsLoading ? (
                    <tr>
                      <td colSpan={4} className="px-3 py-6 text-center text-muted-foreground">
                        Chargement des logs...
                      </td>
                    </tr>
                  ) : (logs?.items ?? []).length === 0 ? (
                    <tr>
                      <td colSpan={4} className="px-3 py-6 text-center text-muted-foreground">
                        Aucun log trouve.
                      </td>
                    </tr>
                  ) : (
                    (logs?.items ?? []).map((item) => (
                      <tr key={item.id}>
                        <td className="whitespace-nowrap px-3 py-2 text-slate-600">
                          {new Date(item.created_at).toLocaleString("fr-FR")}
                        </td>
                        <td className="px-3 py-2">
                          <Badge variant={getActionBadgeVariant(item.action)}>{item.action}</Badge>
                        </td>
                        <td className="px-3 py-2 text-slate-700">
                          {item.resource_type}
                          {item.resource_id ? `:${item.resource_id.slice(0, 8)}` : ""}
                        </td>
                        <td className="px-3 py-2 text-slate-700">
                          {item.actor_user_id ? item.actor_user_id.slice(0, 8) : "system"}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            {(logs?.total_pages ?? 0) > 1 && (
              <div className="flex items-center justify-between">
                <p className="text-sm text-muted-foreground">
                  Page {logs?.page ?? 1} / {logs?.total_pages ?? 1}
                </p>
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={(logs?.page ?? 1) <= 1}
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                  >
                    Precedent
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={(logs?.page ?? 1) >= (logs?.total_pages ?? 1)}
                    onClick={() => setPage((p) => p + 1)}
                  >
                    Suivant
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
