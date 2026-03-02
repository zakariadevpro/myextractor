"use client";

import { ShieldCheck } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useB2CCompliance } from "@/hooks/use-dashboard";

export function B2CCompliancePanel() {
  const { data, isLoading } = useB2CCompliance();

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <ShieldCheck className="h-5 w-5 text-primary" />
          Conformite B2C
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {isLoading ? (
          <p className="text-sm text-muted-foreground">Chargement...</p>
        ) : (
          <>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
              <Badge variant="outline">Total B2C: {data?.total_b2c ?? 0}</Badge>
              <Badge variant="success">Consentis: {data?.consent_granted ?? 0}</Badge>
              <Badge variant="danger">Revokes: {data?.consent_revoked ?? 0}</Badge>
              <Badge variant="warning">Expire &lt;7j: {data?.expiring_7d ?? 0}</Badge>
              <Badge variant="secondary">Exportables: {data?.exportable_contacts ?? 0}</Badge>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <div className="rounded-md border border-border p-3 text-sm text-slate-700">
                Double opt-in: <span className="font-semibold">{data?.double_opt_in_rate ?? 0}%</span>
              </div>
              <div className="rounded-md border border-border p-3 text-sm text-slate-700">
                Taux de revocation: <span className="font-semibold">{data?.revocation_rate ?? 0}%</span>
              </div>
            </div>

            <div className="rounded-md border border-border p-3">
              <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
                Sources B2C
              </p>
              {data?.by_source?.length ? (
                <div className="flex flex-wrap gap-2">
                  {data.by_source.map((item) => (
                    <Badge key={item.source} variant="outline">
                      {item.source}: {item.count}
                    </Badge>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">Aucune source B2C pour le moment.</p>
              )}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}

