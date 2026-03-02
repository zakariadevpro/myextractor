import type { ReactNode } from "react";
import { Card, CardContent } from "@/components/ui/card";

interface MetricCardProps {
  label: string;
  value: string | number;
  helper?: string;
  icon?: ReactNode;
}

export function MetricCard({ label, value, helper, icon }: MetricCardProps) {
  return (
    <Card className="card-hover">
      <CardContent className="p-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
            <p className="mt-2 text-2xl font-bold text-slate-900">{value}</p>
            {helper ? <p className="mt-1 text-xs text-muted-foreground">{helper}</p> : null}
          </div>
          {icon ? (
            <div className="rounded-lg border border-border bg-slate-50 p-2 text-slate-600">{icon}</div>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}
