"use client";

import { CheckCircle2, Gauge, Layers3 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useDashboardOverview } from "@/hooks/use-dashboard";

interface ProgressRowProps {
  label: string;
  value: number;
  colorClass: string;
}

function ProgressRow({ label, value, colorClass }: ProgressRowProps) {
  const safeValue = Math.max(0, Math.min(100, value));
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-sm">
        <span className="text-slate-600">{label}</span>
        <span className="font-medium text-slate-900">{safeValue.toFixed(1)}%</span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
        <div className={`h-full rounded-full ${colorClass}`} style={{ width: `${safeValue}%` }} />
      </div>
    </div>
  );
}

export function DataQualityPanel() {
  const { data: overview } = useDashboardOverview();
  const avgScore = overview?.avg_score ?? 0;
  const emailRate = overview?.email_valid_rate ?? 0;
  const duplicateRate = overview?.duplicate_rate ?? 0;
  const uniquenessRate = Math.max(0, 100 - duplicateRate);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Gauge className="h-5 w-5 text-primary" />
          Qualite Data
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="grid gap-3 sm:grid-cols-3">
          <div className="rounded-lg border border-border bg-slate-50 p-3">
            <p className="text-xs text-slate-500">Score moyen</p>
            <p className="mt-1 text-xl font-semibold text-slate-900">{avgScore.toFixed(1)}/100</p>
          </div>
          <div className="rounded-lg border border-border bg-slate-50 p-3">
            <p className="text-xs text-slate-500">Taux emails valides</p>
            <p className="mt-1 text-xl font-semibold text-slate-900">{emailRate.toFixed(1)}%</p>
          </div>
          <div className="rounded-lg border border-border bg-slate-50 p-3">
            <p className="text-xs text-slate-500">Taux doublons</p>
            <p className="mt-1 text-xl font-semibold text-slate-900">{duplicateRate.toFixed(1)}%</p>
          </div>
        </div>

        <ProgressRow
          label="Couverture email valide"
          value={emailRate}
          colorClass="bg-success"
        />
        <ProgressRow
          label="Unicite des leads"
          value={uniquenessRate}
          colorClass="bg-primary"
        />
        <ProgressRow
          label="Qualite score (normalisee)"
          value={avgScore}
          colorClass="bg-warning"
        />

        <div className="grid gap-2 border-t border-border pt-3 text-xs text-slate-500 sm:grid-cols-3">
          <div className="flex items-center gap-1.5">
            <CheckCircle2 className="h-3.5 w-3.5 text-success" />
            Objectif email valide {" > "} 70%
          </div>
          <div className="flex items-center gap-1.5">
            <Layers3 className="h-3.5 w-3.5 text-primary" />
            Objectif unicite {" > "} 85%
          </div>
          <div className="flex items-center gap-1.5">
            <Gauge className="h-3.5 w-3.5 text-warning" />
            Objectif score {" > "} 60
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
