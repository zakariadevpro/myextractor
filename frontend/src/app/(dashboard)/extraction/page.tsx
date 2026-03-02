"use client";

import { Activity, CheckCircle2, Clock3, History, Loader2 } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { Badge } from "@/components/ui/badge";
import { ExtractionForm } from "@/components/features/extraction/extraction-form";
import { B2CIntakeForm } from "@/components/features/extraction/b2c-intake-form";
import { ExtractionProgress } from "@/components/features/extraction/extraction-progress";
import { useExtractions } from "@/hooks/use-extraction";
import { MetricCard } from "@/components/ui/metric-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuth } from "@/hooks/use-auth";
import { hasMinimumRole } from "@/lib/authz";

export default function ExtractionPage() {
  const { user } = useAuth();
  const canManageExtractions = hasMinimumRole(user?.role, "manager");
  const { data: extractions, isLoading } = useExtractions({
    page: 1,
    page_size: 10,
    ordering: "-created_at",
  });
  const jobs = extractions?.items ?? [];
  const runningCount = jobs.filter((job) => job.status === "running").length;
  const pendingCount = jobs.filter((job) => job.status === "pending").length;
  const completedCount = jobs.filter((job) => job.status === "completed").length;
  const avgProgress = jobs.length
    ? Math.round(jobs.reduce((acc, job) => acc + (job.progress || 0), 0) / jobs.length)
    : 0;

  return (
    <div className="space-y-8">
      <PageHeader
        title="Extraction"
        description="Orchestre tes jobs d'extraction avec suivi en temps reel et controle de qualite."
        badges={
          <>
            {canManageExtractions ? (
              <Badge variant="success">Creation autorisee</Badge>
            ) : (
              <Badge variant="secondary">Lecture seule</Badge>
            )}
            <Badge variant="outline">{jobs.length} jobs affiches</Badge>
          </>
        }
      />

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          label="Jobs En Cours"
          value={runningCount}
          helper={`${pendingCount} en attente`}
          icon={<Loader2 className="h-4 w-4" />}
        />
        <MetricCard
          label="Jobs Termines"
          value={completedCount}
          helper="Statut completed"
          icon={<CheckCircle2 className="h-4 w-4" />}
        />
        <MetricCard
          label="Progression Moyenne"
          value={`${avgProgress}%`}
          helper="Fenetre courante"
          icon={<Activity className="h-4 w-4" />}
        />
        <MetricCard
          label="Files En Attente"
          value={pendingCount}
          helper="Pending / schedulable"
          icon={<Clock3 className="h-4 w-4" />}
        />
      </div>

      <div className="grid gap-8 lg:grid-cols-2">
        {/* Extraction Form */}
        {canManageExtractions ? (
          <div className="space-y-4">
            <ExtractionForm />
            <B2CIntakeForm />
          </div>
        ) : (
          <Card>
            <CardHeader>
              <CardTitle>Extraction</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                La creation d&apos;extraction est reservee aux roles manager/admin.
              </p>
            </CardContent>
          </Card>
        )}

        {/* Recent Jobs */}
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <History className="h-5 w-5 text-primary" />
                Extractions recentes
              </CardTitle>
            </CardHeader>
            <CardContent>
              {isLoading ? (
                <div className="flex h-32 items-center justify-center">
                  <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
                </div>
              ) : extractions?.items && extractions.items.length > 0 ? (
                <div className="space-y-3">
                  {extractions.items.map((job) => (
                    <ExtractionProgress key={job.id} job={job} />
                  ))}
                </div>
              ) : (
                <div className="flex h-32 flex-col items-center justify-center gap-2">
                  <p className="text-sm font-medium text-slate-900">
                    Aucune extraction
                  </p>
                  <p className="text-xs text-muted-foreground">
                    Lancez votre premiere extraction pour voir les resultats ici.
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
