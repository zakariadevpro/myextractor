"use client";

import { useState } from "react";
import { CircleDot, Download, Filter, Layers, Trash2 } from "lucide-react";
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
import { useAuth } from "@/hooks/use-auth";
import { hasMinimumRole } from "@/lib/authz";
import type { LeadFilters } from "@/types/lead";

export default function LeadsPage() {
  const { user } = useAuth();
  const [filters, setFilters] = useState<LeadFilters>({
    page: 1,
    page_size: 20,
  });
  const canManageLeads = hasMinimumRole(user?.role, "manager");

  const { data, isLoading } = useLeads(filters);
  const { data: suggestedSegments } = useSuggestedSegments();
  const exportMutation = useExportLeads();
  const removeDuplicatesMutation = useRemoveDuplicates();

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
          label="Leads Affiches"
          value={leads.length}
          helper="Resultat de la page courante"
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
          })
        }
      />

      {/* Filters */}
      <LeadFiltersBar filters={filters} onFiltersChange={setFilters} />

      {/* Table */}
      <LeadTable leads={data?.items ?? []} isLoading={isLoading} />

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
