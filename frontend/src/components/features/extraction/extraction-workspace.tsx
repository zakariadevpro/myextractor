"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Activity, CheckCircle2, Clock3, History, Loader2, Search } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { ExtractionForm } from "@/components/features/extraction/extraction-form";
import { B2CIntakeForm } from "@/components/features/extraction/b2c-intake-form";
import { ExtractionProgress } from "@/components/features/extraction/extraction-progress";
import { useExtractions } from "@/hooks/use-extraction";
import { MetricCard } from "@/components/ui/metric-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuth } from "@/hooks/use-auth";
import { hasMinimumRole } from "@/lib/authz";
import { cn } from "@/lib/utils";

type WorkspaceMode = "hub" | "b2b" | "b2c" | "both";

interface WorkspaceConfig {
  title: string;
  description: string;
}

const MODE_CONFIG: Record<WorkspaceMode, WorkspaceConfig> = {
  hub: {
    title: "Extraction",
    description: "Choisis un mode dedie: B2B, B2C ou Mixte.",
  },
  b2b: {
    title: "Extraction B2B",
    description: "Recherche des societes via raison sociale, secteur et zone geographique.",
  },
  b2c: {
    title: "Extraction B2C",
    description: "Recherche des particuliers via prenom/nom et localisation.",
  },
  both: {
    title: "Extraction Mixte",
    description: "Combine recherches B2B et B2C dans un workflow unique.",
  },
};

const MODE_LINKS = [
  { label: "Accueil", href: "/extraction", mode: "hub" as const },
  { label: "Mode B2B", href: "/extraction/b2b", mode: "b2b" as const },
  { label: "Mode B2C", href: "/extraction/b2c", mode: "b2c" as const },
  { label: "Mode Mixte", href: "/extraction/mixte", mode: "both" as const },
];

interface ExtractionWorkspaceProps {
  mode: WorkspaceMode;
}

function ModeCards() {
  const cards = [
    {
      title: "Mode B2B",
      description: "Raison sociale, secteur, ville, code postal et departement.",
      href: "/extraction/b2b",
    },
    {
      title: "Mode B2C",
      description: "Prenom, nom, ville, code postal et departement.",
      href: "/extraction/b2c",
    },
    {
      title: "Mode Mixte",
      description: "Un formulaire combine pour societes et particuliers.",
      href: "/extraction/mixte",
    },
  ];

  return (
    <div className="grid gap-4 md:grid-cols-3">
      {cards.map((card) => (
        <Card key={card.href}>
          <CardHeader>
            <CardTitle className="text-base">{card.title}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">{card.description}</p>
            <Link href={card.href} className={cn(buttonVariants({ variant: "outline" }), "w-full")}>
              Ouvrir
            </Link>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

export function ExtractionWorkspace({ mode }: ExtractionWorkspaceProps) {
  const pathname = usePathname();
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

  const config = MODE_CONFIG[mode];

  return (
    <div className="space-y-8">
      <PageHeader
        title={config.title}
        description={config.description}
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

      <div className="flex flex-wrap gap-2">
        {MODE_LINKS.map((item) => {
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                buttonVariants({ variant: isActive ? "default" : "outline", size: "sm" }),
                "h-9"
              )}
            >
              {item.label}
            </Link>
          );
        })}
      </div>

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
        {canManageExtractions ? (
          <div className="space-y-4">
            {mode === "hub" && <ModeCards />}
            {mode === "b2b" && <ExtractionForm mode="b2b" />}
            {mode === "b2c" && (
              <>
                <ExtractionForm mode="b2c" />
                <B2CIntakeForm />
              </>
            )}
            {mode === "both" && <ExtractionForm mode="both" />}
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
                  <Search className="h-5 w-5 text-muted-foreground" />
                  <p className="text-sm font-medium text-slate-900">Aucune extraction</p>
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
