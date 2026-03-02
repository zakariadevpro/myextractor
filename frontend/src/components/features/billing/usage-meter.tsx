"use client";

import { cn, formatNumber } from "@/lib/utils";

interface UsageMeterProps {
  used: number;
  limit: number;
  label?: string;
  periodStart?: string;
  periodEnd?: string;
}

export function UsageMeter({
  used,
  limit,
  label = "Leads utilises",
  periodStart,
  periodEnd,
}: UsageMeterProps) {
  const percentage = Math.min(Math.round((used / Math.max(limit, 1)) * 100), 100);

  let barColor = "bg-primary";
  let textColor = "text-primary-700";
  if (percentage >= 90) {
    barColor = "bg-danger";
    textColor = "text-danger";
  } else if (percentage >= 70) {
    barColor = "bg-warning";
    textColor = "text-yellow-700";
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium text-slate-700">{label}</p>
        <p className={cn("text-sm font-semibold", textColor)}>
          {formatNumber(used)} / {formatNumber(limit)}
        </p>
      </div>

      {/* Progress bar */}
      <div className="h-3 w-full overflow-hidden rounded-full bg-slate-100">
        <div
          className={cn("h-full rounded-full transition-all duration-700", barColor)}
          style={{ width: `${percentage}%` }}
        />
      </div>

      {/* Details */}
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>{percentage}% utilise</span>
        {periodStart && periodEnd && (
          <span>
            Periode : {periodStart} - {periodEnd}
          </span>
        )}
      </div>

      {/* Warning */}
      {percentage >= 90 && (
        <div className="rounded-lg bg-danger-light px-3 py-2">
          <p className="text-xs font-medium text-red-700">
            Vous approchez de votre limite mensuelle. Passez a un plan superieur
            pour continuer vos extractions.
          </p>
        </div>
      )}
    </div>
  );
}
