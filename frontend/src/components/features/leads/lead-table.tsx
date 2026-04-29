"use client";

import { useMemo } from "react";
import Link from "next/link";
import {
  useReactTable,
  getCoreRowModel,
  flexRender,
  createColumnHelper,
  type ColumnDef,
} from "@tanstack/react-table";
import { format } from "date-fns";
import { fr } from "date-fns/locale";
import { ExternalLink, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { LeadScoreBadge } from "./lead-score-badge";
import { Badge } from "@/components/ui/badge";
import { useDeleteLead } from "@/hooks/use-leads";
import type { Lead } from "@/types/lead";

interface LeadTableProps {
  leads: Lead[];
  isLoading?: boolean;
  canDelete?: boolean;
}

const columnHelper = createColumnHelper<Lead>();

function getConsentBadgeMeta(status: Lead["consent_status"]): {
  label: string;
  variant: "success" | "danger" | "warning" | "outline";
} {
  if (status === "granted") return { label: "Accorde", variant: "success" };
  if (status === "denied") return { label: "Refuse", variant: "danger" };
  if (status === "revoked") return { label: "Revoque", variant: "warning" };
  return { label: "Inconnu", variant: "outline" };
}

export function LeadTable({ leads, isLoading, canDelete = false }: LeadTableProps) {
  const deleteMutation = useDeleteLead();

  const handleDelete = (lead: Lead) => {
    if (typeof window === "undefined") return;
    const confirmed = window.confirm(
      `Supprimer definitivement le lead "${lead.company_name}" ?`,
    );
    if (!confirmed) return;
    deleteMutation.mutate(lead.id, {
      onSuccess: () => toast.success("Lead supprime."),
      onError: () => toast.error("Impossible de supprimer ce lead."),
    });
  };

  const columns = useMemo<ColumnDef<Lead, unknown>[]>(
    () => [
      columnHelper.accessor("company_name", {
        header: "Entreprise",
        cell: (info) => (
          <Link
            href={`/leads/${info.row.original.id}`}
            className="font-medium text-slate-900 hover:text-primary"
          >
            {info.getValue()}
          </Link>
        ),
      }) as ColumnDef<Lead, unknown>,
      columnHelper.accessor("lead_kind", {
        header: "Type",
        cell: (info) => (
          <Badge variant={info.getValue() === "b2c" ? "warning" : "outline"}>
            {info.getValue().toUpperCase()}
          </Badge>
        ),
      }) as ColumnDef<Lead, unknown>,
      columnHelper.accessor("sector", {
        header: "Secteur",
        cell: (info) => (
          <span className="text-sm text-slate-600">{info.getValue() || "-"}</span>
        ),
      }) as ColumnDef<Lead, unknown>,
      columnHelper.accessor("emails", {
        header: "Email",
        cell: (info) => {
          const emails = info.getValue();
          const primaryEmail = emails?.[0];
          return primaryEmail ? (
            <span className="text-sm text-slate-600">
              {primaryEmail.email}
            </span>
          ) : (
            <span className="text-sm text-slate-400">-</span>
          );
        },
      }) as ColumnDef<Lead, unknown>,
      columnHelper.accessor("phones", {
        header: "Telephone",
        cell: (info) => {
          const phones = info.getValue();
          const primaryPhone = phones?.[0];
          return primaryPhone ? (
            <span className="text-sm text-slate-600">
              {primaryPhone.phone_normalized || primaryPhone.phone_raw || "-"}
            </span>
          ) : (
            <span className="text-sm text-slate-400">-</span>
          );
        },
      }) as ColumnDef<Lead, unknown>,
      columnHelper.accessor("consent_status", {
        header: "Consentement",
        cell: (info) => {
          const meta = getConsentBadgeMeta(info.getValue());
          return <Badge variant={meta.variant}>{meta.label}</Badge>;
        },
      }) as ColumnDef<Lead, unknown>,
      columnHelper.accessor("city", {
        header: "Ville",
        cell: (info) => (
          <span className="text-sm text-slate-600">{info.getValue() || "-"}</span>
        ),
      }) as ColumnDef<Lead, unknown>,
      columnHelper.accessor("quality_score", {
        header: "Score",
        cell: (info) => <LeadScoreBadge score={info.getValue()} />,
      }) as ColumnDef<Lead, unknown>,
      columnHelper.accessor("created_at", {
        header: "Date",
        cell: (info) => (
          <span className="text-sm text-slate-500">
            {format(new Date(info.getValue()), "dd MMM yyyy", { locale: fr })}
          </span>
        ),
      }) as ColumnDef<Lead, unknown>,
      columnHelper.display({
        id: "actions",
        header: "",
        cell: (info) => (
          <div className="flex items-center justify-end gap-2">
            <Link
              href={`/leads/${info.row.original.id}`}
              className="text-slate-400 hover:text-primary"
              title="Ouvrir la fiche"
            >
              <ExternalLink className="h-4 w-4" />
            </Link>
            {canDelete && (
              <button
                type="button"
                onClick={() => handleDelete(info.row.original)}
                className="text-slate-400 hover:text-danger disabled:opacity-50"
                disabled={deleteMutation.isPending}
                title="Supprimer ce lead"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            )}
          </div>
        ),
      }) as ColumnDef<Lead, unknown>,
    ],
    [canDelete, deleteMutation.isPending]
  );

  const table = useReactTable({
    data: leads,
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  if (isLoading) {
    return (
      <div className="rounded-lg border border-border bg-white">
        <div className="flex h-64 items-center justify-center">
          <div className="flex flex-col items-center gap-3">
            <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
            <p className="text-sm text-muted-foreground">
              Chargement des leads...
            </p>
          </div>
        </div>
      </div>
    );
  }

  if (leads.length === 0) {
    return (
      <div className="rounded-lg border border-border bg-white">
        <div className="flex h-64 flex-col items-center justify-center gap-2">
          <p className="text-sm font-medium text-slate-900">
            Aucun lead trouve
          </p>
          <p className="text-sm text-muted-foreground">
            Modifiez vos filtres ou lancez une nouvelle extraction.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-lg border border-border bg-white">
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            {table.getHeaderGroups().map((headerGroup) => (
              <tr
                key={headerGroup.id}
                className="border-b border-border bg-slate-50"
              >
                {headerGroup.headers.map((header) => (
                  <th
                    key={header.id}
                    className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-500"
                  >
                    {header.isPlaceholder
                      ? null
                      : flexRender(
                          header.column.columnDef.header,
                          header.getContext()
                        )}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody className="divide-y divide-border">
            {table.getRowModel().rows.map((row) => (
              <tr
                key={row.id}
                className="transition-colors hover:bg-slate-50"
              >
                {row.getVisibleCells().map((cell) => (
                  <td key={cell.id} className="px-4 py-3">
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
