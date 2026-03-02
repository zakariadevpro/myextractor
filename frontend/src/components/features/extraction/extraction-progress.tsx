"use client";

import { format } from "date-fns";
import { fr } from "date-fns/locale";
import {
  CheckCircle2,
  XCircle,
  Clock,
  Loader2,
  Ban,
  Users,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useCancelExtraction } from "@/hooks/use-extraction";
import { SOURCES } from "@/lib/constants";
import type { ExtractionJob, ExtractionStatus } from "@/types/extraction";

interface ExtractionProgressProps {
  job: ExtractionJob;
}

const statusConfig: Record<
  ExtractionStatus,
  { label: string; icon: React.ReactNode; variant: "default" | "success" | "warning" | "danger" | "secondary"; color: string }
> = {
  pending: {
    label: "En attente",
    icon: <Clock className="h-4 w-4" />,
    variant: "secondary",
    color: "text-slate-500",
  },
  running: {
    label: "En cours",
    icon: <Loader2 className="h-4 w-4 animate-spin" />,
    variant: "warning",
    color: "text-yellow-600",
  },
  completed: {
    label: "Terminee",
    icon: <CheckCircle2 className="h-4 w-4" />,
    variant: "success",
    color: "text-green-600",
  },
  failed: {
    label: "Echouee",
    icon: <XCircle className="h-4 w-4" />,
    variant: "danger",
    color: "text-red-600",
  },
  cancelled: {
    label: "Annulee",
    icon: <Ban className="h-4 w-4" />,
    variant: "secondary",
    color: "text-slate-500",
  },
};

export function ExtractionProgress({ job }: ExtractionProgressProps) {
  const cancelMutation = useCancelExtraction();
  const config = statusConfig[job.status];

  const progressPercent = job.progress ?? 0;

  return (
    <Card className="card-hover">
      <CardContent className="p-4">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 space-y-3">
            {/* Header */}
            <div className="flex items-center gap-2">
              <Badge variant={config.variant} className="gap-1">
                {config.icon}
                {config.label}
              </Badge>
              <span className="text-xs text-muted-foreground">
                {format(new Date(job.created_at), "dd MMM yyyy HH:mm", {
                  locale: fr,
                })}
              </span>
            </div>

            {/* Job details */}
            <div>
              <p className="text-sm font-medium text-slate-900">
                {job.keywords?.join(", ") ?? "-"}
              </p>
              <p className="text-xs text-muted-foreground">
                <span className="font-medium">{SOURCES.find(s => s.value === job.source)?.label ?? job.source}</span>
                {" - "}{job.city ?? "-"}{job.sector_filter ? ` - ${job.sector_filter}` : ""}{job.radius_km ? ` - Rayon: ${job.radius_km} km` : ""}
              </p>
            </div>

            {/* Progress bar */}
            {(job.status === "running" || job.status === "completed") && (
              <div className="space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">Progression</span>
                  <span className="font-medium text-slate-700">
                    {progressPercent}%
                  </span>
                </div>
                <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
                  <div
                    className={cn(
                      "h-full rounded-full transition-all duration-500",
                      job.status === "completed"
                        ? "bg-success"
                        : "bg-primary"
                    )}
                    style={{ width: `${progressPercent}%` }}
                  />
                </div>
              </div>
            )}

            {/* Leads found */}
            <div className="flex items-center gap-1 text-xs text-muted-foreground">
              <Users className="h-3.5 w-3.5" />
              <span>
                {job.leads_found} leads trouves ({job.leads_new} nouveaux, {job.leads_duplicate} doublons) / {job.max_leads} maximum
              </span>
            </div>

            {/* Error message */}
            {job.error_message && (
              <p className="text-xs text-danger">{job.error_message}</p>
            )}
          </div>

          {/* Cancel button */}
          {(job.status === "pending" || job.status === "running") && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => cancelMutation.mutate(job.id)}
              isLoading={cancelMutation.isPending}
              className="text-slate-400 hover:text-danger"
            >
              <Ban className="h-4 w-4" />
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
