"use client";

import { useEffect, useMemo, useState } from "react";
import { format } from "date-fns";
import { fr } from "date-fns/locale";
import { CircleDot, Download, Filter, Layers, Trash2, X } from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { MetricCard } from "@/components/ui/metric-card";
import { LeadTable } from "@/components/features/leads/lead-table";
import { LeadFiltersBar } from "@/components/features/leads/lead-filters";
import { SuggestedSegments } from "@/components/features/leads/suggested-segments";
import {
  useLeads,
  useExportLeads,
  useRemoveDuplicates,
  useSuggestedSegments,
} from "@/hooks/use-leads";
import { useExtractions } from "@/hooks/use-extraction";
import { useAuth } from "@/hooks/use-auth";
import { hasMinimumRole } from "@/lib/authz";
import type { LeadFilters } from "@/types/lead";

export default function LeadsPage() {
  const { user } = useAuth();
  const [filters, setFilters] = useState<LeadFilters>({
    page: 1,
    page_size: 20,
    ordering: "-updated_at",
  });
  const canManageLeads = hasMinimumRole(user?.role, "manager");

  const { data, isLoading } = useLeads(filters);
  const { data: suggestedSegments } = useSuggestedSegments();
  const exportMutation = useExportLeads();
  const removeDuplicatesMutation = useRemoveDuplicates();
  const { data: extractionsData } = useExtractions({
    page: 1,
    page_size: 50,
    ordering: "-created_at",
  });

  const activeExtraction = useMemo(() => {
    if (!filters.extraction_job_id) return null;
    return (
      extractionsData?.items.find((j) => j.id === filters.extraction_job_id) ??
      null
    );
  }, [extractionsData, filters.extraction_job_id]);

  const clearExtractionFilter = () => {
    setFilters((prev) => {
      const next = { ...prev };
      delete next.extraction_job_id;
      next.page = 1;
      return next;
    });
    if (typeof window !== "undefined") {
      const url = new URL(window.location.href);
      url.searchParams.delete("extraction_job_id");
      window.history.replaceState({}, "", url.toString());
    }
  };

  useEffect(() => {
    const extractionJobId = new URLSearchParams(window.location.search).get("extraction_job_id");
    if (extractionJobId) {
      setFilters((prev) => ({
        ...prev,
        extraction_job_id: extractionJobId,
        page: 1,
        ordering: "-updated_at",
      }));
    }
  }, []);

  const handleExport = async () => {
    try {
      await exportMutation.mutateAsync({ filters, format: "csv" });
      toast.success("Export CSV telecharge avec succes.");
    } catch {
      toast.error("Erreur lors de l'export. Veuillez reessayer.");
    }
  };

  const handleExportXlsx = async () => {
    try {
      await exportMutation.mutateAsync({ filters, format: "xlsx" });
      toast.success("Export Excel telecharge avec succes.");
    } catch {
      toast.error("Erreur lors de l'export Excel. Veuillez reessayer.");
    }
  };

  const handleRemoveDuplicates = async () => {
    try {
      const result = await removeDuplicatesMutation.mutateAsync();
      toast.success(result.message || "Deduplication terminee.");
    } catch {
      toast.error("Erreur lors de la suppression des doublons.");
    }
  };

  const handlePageChange = (page: number) => {
    setFilters((prev) => ({ ...prev, page }));
  };

  const totalPages = data?.total_pages ?? 0;
  const currentPage = data?.page ?? 1;
  const leads = data?.items ?? [];
  const avgScore = leads.length
    ? Math.round(leads.reduce((acc, lead) => acc + lead.quality_score, 0) / leads.length)
    : 0;
  const duplicates = leads.filter((lead) => lead.is_duplicate).length;
  const withContacts = leads.filter((lead) => lead.emails.length > 0 || lead.phones.length > 0).length;
  const contactCoverage = leads.length ? Math.round((withContacts / leads.length) * 100) : 0;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Leads"
        description={`${data?.total ?? 0} leads indexes dans ton CRM d'extraction.`}
        badges={
          <>
            <Badge variant="outline">Page {currentPage}</Badge>
            <Badge variant="outline">{filters.page_size ?? 20} / page</Badge>
            {canManageLeads ? (
              <Badge variant="success">Mode manager</Badge>
            ) : (
              <Badge variant="secondary">Lecture seule</Badge>
            )}
            {filters.extraction_job_id && <Badge variant="outline">Extraction filtree</Badge>}
          </>
        }
        actions={
          canManageLeads ? (
            <>
              <Button
                variant="outline"
                className="gap-2"
                onClick={handleExport}
                isLoading={exportMutation.isPending}
              >
                <Download className="h-4 w-4" />
                Export CSV
              </Button>
              <Button
                variant="outline"
                className="gap-2"
                onClick={handleExportXlsx}
                isLoading={exportMutation.isPending}
              >
                <Download className="h-4 w-4" />
                Export Excel
              </Button>
              <Button
                variant="outline"
                className="gap-2"
                onClick={handleRemoveDuplicates}
                isLoading={removeDuplicatesMutation.isPending}
              >
                <Trash2 className="h-4 w-4" />
                Dedoublonner
              </Button>
            </>
          ) : null
        }
      />

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          label="Total Leads"
          value={data?.total ?? 0}
          helper={`${leads.length} affiches sur cette page`}
          icon={<Layers className="h-4 w-4" />}
        />
        <MetricCard
          label="Score Moyen"
          value={avgScore}
          helper="Qualite moyenne sur 100"
          icon={<CircleDot className="h-4 w-4" />}
        />
        <MetricCard
          label="Couverture Contact"
          value={`${contactCoverage}%`}
          helper="Au moins email ou telephone"
          icon={<Filter className="h-4 w-4" />}
        />
        <MetricCard
          label="Doublons Detectes"
          value={duplicates}
          helper="Sur la page courante"
          icon={<Trash2 className="h-4 w-4" />}
        />
      </div>

      <SuggestedSegments
        segments={suggestedSegments ?? []}
        onApply={(segmentFilters) =>
          setFilters({
            ...segmentFilters,
            page: 1,
            page_size: 20,
            ordering: "-updated_at",
          })
        }
      />

      {/* Active extraction filter banner */}
      {filters.extraction_job_id && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-primary/30 bg-primary/5 px-4 py-3">
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <Filter className="h-4 w-4 text-primary" />
            <span className="font-medium text-slate-900">
              Filtre extraction actif
            </span>
            {activeExtraction ? (
              <span className="text-muted-foreground">
                {activeExtraction.created_at
                  ? format(new Date(activeExtraction.created_at), "dd MMM yyyy HH:mm", { locale: fr })
                  : ""}
                {" - "}
                {(activeExtraction.keywords || []).slice(0, 3).join(", ") || "-"}
                {activeExtraction.city ? ` / ${activeExtraction.city}` : ""}
                {" "}
                ({activeExtraction.leads_found ?? 0} leads)
              </span>
            ) : (
              <span className="text-muted-foreground">
                ID: {filters.extraction_job_id.slice(0, 8)}...
              </span>
            )}
          </div>
          <Button
            variant="outline"
            size="sm"
            className="gap-2"
            onClick={clearExtractionFilter}
          >
            <X className="h-3.5 w-3.5" />
            Retirer le filtre
          </Button>
        </div>
      )}

      {/* Filters */}
      <LeadFiltersBar filters={filters} onFiltersChange={setFilters} />

      {/* Table */}
      <LeadTable
        leads={data?.items ?? []}
        isLoading={isLoading}
        canDelete={canManageLeads}
      />

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between rounded-lg border border-border bg-white px-4 py-3">
          <p className="text-sm text-muted-foreground">
            Page {currentPage} sur {totalPages} ({data?.total} resultats)
          </p>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={currentPage <= 1}
              onClick={() => handlePageChange(currentPage - 1)}
            >
              Precedent
            </Button>
            {/* Page numbers */}
            {Array.from({ length: Math.min(totalPages, 5) }, (_, i) => {
              const pageNum =
                totalPages <= 5
                  ? i + 1
                  : Math.max(1, Math.min(currentPage - 2, totalPages - 4)) + i;
              return (
                <Button
                  key={pageNum}
                  variant={pageNum === currentPage ? "default" : "outline"}
                  size="sm"
                  onClick={() => handlePageChange(pageNum)}
                >
                  {pageNum}
                </Button>
              );
            })}
            <Button
              variant="outline"
              size="sm"
              disabled={currentPage >= totalPages}
              onClick={() => handlePageChange(currentPage + 1)}
            >
              Suivant
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
