"use client";

import { format } from "date-fns";
import { fr } from "date-fns/locale";
import Link from "next/link";
import {
  CheckCircle2,
  XCircle,
  Clock,
  Loader2,
  Ban,
  ExternalLink,
  Trash2,
  Users,
} from "lucide-react";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import {
  useCancelExtraction,
  useDeleteExtraction,
} from "@/hooks/use-extraction";
import { useAuth } from "@/hooks/use-auth";
import { hasMinimumRole } from "@/lib/authz";
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
  const deleteMutation = useDeleteExtraction();
  const { user } = useAuth();
  const canManageLeads = hasMinimumRole(user?.role, "admin");
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [deleteLeads, setDeleteLeads] = useState(true);
  const config = statusConfig[job.status];

  const progressPercent = job.progress ?? 0;
  const canDelete =
    job.status === "completed" ||
    job.status === "failed" ||
    job.status === "cancelled";

  const handleDelete = () => {
    deleteMutation.mutate(
      { id: job.id, deleteLeads },
      { onSuccess: () => setConfirmOpen(false) },
    );
  };

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

          {/* Action icons */}
          <div className="flex shrink-0 items-center gap-1 self-start">
            {job.status === "completed" && (
              <Link
                href={`/leads?extraction_job_id=${job.id}`}
                className="inline-flex h-8 w-8 items-center justify-center rounded-md text-slate-400 transition-colors hover:bg-slate-100 hover:text-primary"
                title="Voir les leads de cette extraction"
              >
                <ExternalLink className="h-4 w-4" />
              </Link>
            )}
            {(job.status === "pending" || job.status === "running") && (
              <button
                type="button"
                onClick={() => cancelMutation.mutate(job.id)}
                disabled={cancelMutation.isPending}
                className="inline-flex h-8 w-8 items-center justify-center rounded-md text-slate-400 transition-colors hover:bg-slate-100 hover:text-danger disabled:opacity-50"
                title="Annuler l'extraction"
              >
                <Ban className="h-4 w-4" />
              </button>
            )}
            {canManageLeads && canDelete && (
              <button
                type="button"
                onClick={() => {
                  if ((job.leads_found ?? 0) === 0) {
                    deleteMutation.mutate({ id: job.id, deleteLeads: false });
                  } else {
                    setConfirmOpen(true);
                  }
                }}
                disabled={deleteMutation.isPending}
                className="inline-flex h-8 w-8 items-center justify-center rounded-md text-slate-400 transition-colors hover:bg-slate-100 hover:text-danger disabled:opacity-50"
                title="Supprimer cette extraction"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            )}
          </div>
        </div>

        {confirmOpen && (
          <div className="mt-4 rounded-lg border border-danger/30 bg-danger/5 p-4">
            <p className="text-sm font-medium text-slate-900">
              Supprimer cette extraction ?
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              {job.leads_found} lead(s) ont ete trouves par ce job.
            </p>
            <label className="mt-3 flex items-start gap-2 text-sm text-slate-700">
              <input
                type="checkbox"
                checked={deleteLeads}
                onChange={(e) => setDeleteLeads(e.target.checked)}
                className="mt-1"
              />
              <span>
                Supprimer aussi les leads associes a cette extraction
                <span className="block text-xs text-muted-foreground">
                  Decoche pour conserver les leads (le rattachement a
                  l&apos;extraction sera retire).
                </span>
              </span>
            </label>
            <div className="mt-3 flex justify-end gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setConfirmOpen(false)}
                disabled={deleteMutation.isPending}
              >
                Annuler
              </Button>
              <Button
                variant="destructive"
                size="sm"
                onClick={handleDelete}
                isLoading={deleteMutation.isPending}
              >
                Supprimer
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
