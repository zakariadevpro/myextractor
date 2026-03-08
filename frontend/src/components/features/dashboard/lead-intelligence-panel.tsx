"use client";

import { Brain, Flame, Layers3, Target } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useLeadIntelligence } from "@/hooks/use-dashboard";
import { formatNumber } from "@/lib/utils";

const BUCKET_LABELS: Record<string, string> = {
  hot: "Hot",
  warm: "Warm",
  cold: "Cold",
};

const BUCKET_COLORS: Record<string, string> = {
  hot: "bg-rose-500",
  warm: "bg-amber-500",
  cold: "bg-slate-400",
};

export function LeadIntelligencePanel() {
  const { data } = useLeadIntelligence();

  const total = data?.total_leads ?? 0;
  const ready = data?.ready_to_contact ?? 0;
  const missing = data?.missing_contact ?? 0;
  const readyRate = total > 0 ? Math.round((ready / total) * 100) : 0;
  const topSources = data?.by_source?.slice(0, 3) ?? [];
  const bucketData = data?.priority_buckets ?? [];
  const maxBucket = Math.max(...bucketData.map((item) => item.count), 1);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Brain className="h-5 w-5 text-primary" />
          Lead Intelligence
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="grid gap-3 sm:grid-cols-4">
          <div className="rounded-lg border border-border bg-slate-50 p-3">
            <p className="text-xs text-slate-500">Total Leads</p>
            <p className="mt-1 text-xl font-semibold text-slate-900">{formatNumber(total)}</p>
          </div>
          <div className="rounded-lg border border-border bg-slate-50 p-3">
            <p className="text-xs text-slate-500">Ready To Contact</p>
            <p className="mt-1 text-xl font-semibold text-slate-900">{formatNumber(ready)}</p>
          </div>
          <div className="rounded-lg border border-border bg-slate-50 p-3">
            <p className="text-xs text-slate-500">Missing Contact</p>
            <p className="mt-1 text-xl font-semibold text-slate-900">{formatNumber(missing)}</p>
          </div>
          <div className="rounded-lg border border-border bg-slate-50 p-3">
            <p className="text-xs text-slate-500">Contact Readiness</p>
            <p className="mt-1 text-xl font-semibold text-slate-900">{readyRate}%</p>
          </div>
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          <div className="space-y-3 rounded-lg border border-border p-3">
            <p className="text-sm font-semibold text-slate-900">Priorisation IA</p>
            <div className="space-y-2">
              {bucketData.map((bucket) => {
                const width = Math.round((bucket.count / maxBucket) * 100);
                return (
                  <div key={bucket.bucket} className="space-y-1">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-medium text-slate-700">
                        {BUCKET_LABELS[bucket.bucket] || bucket.bucket}
                      </span>
                      <span className="text-slate-500">{formatNumber(bucket.count)}</span>
                    </div>
                    <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
                      <div
                        className={`h-full rounded-full ${BUCKET_COLORS[bucket.bucket] || "bg-primary"}`}
                        style={{ width: `${width}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="space-y-3 rounded-lg border border-border p-3">
            <p className="text-sm font-semibold text-slate-900">Top Sources</p>
            {topSources.length > 0 ? (
              <div className="space-y-2">
                {topSources.map((source) => (
                  <div
                    key={source.source}
                    className="flex items-center justify-between rounded-md bg-slate-50 px-3 py-2 text-sm"
                  >
                    <span className="text-slate-700">{source.source}</span>
                    <span className="font-semibold text-slate-900">{formatNumber(source.count)}</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">Aucune source disponible pour le moment.</p>
            )}
          </div>
        </div>

        <div className="grid gap-2 border-t border-border pt-3 text-xs text-slate-500 sm:grid-cols-3">
          <div className="flex items-center gap-1.5">
            <Flame className="h-3.5 w-3.5 text-rose-500" />
            Hot: score &gt;= 80
          </div>
          <div className="flex items-center gap-1.5">
            <Target className="h-3.5 w-3.5 text-amber-500" />
            Warm: score 55-79
          </div>
          <div className="flex items-center gap-1.5">
            <Layers3 className="h-3.5 w-3.5 text-slate-500" />
            Cold: score &lt; 55
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
