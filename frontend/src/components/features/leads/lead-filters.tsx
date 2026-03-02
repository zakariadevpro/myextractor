"use client";

import { useState } from "react";
import { Search, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { SECTORS } from "@/lib/constants";
import type { LeadFilters } from "@/types/lead";

interface LeadFiltersBarProps {
  filters: LeadFilters;
  onFiltersChange: (filters: LeadFilters) => void;
}

export function LeadFiltersBar({
  filters,
  onFiltersChange,
}: LeadFiltersBarProps) {
  const [localFilters, setLocalFilters] = useState<LeadFilters>(filters);

  const handleApply = () => {
    onFiltersChange(localFilters);
  };

  const handleReset = () => {
    const resetFilters: LeadFilters = {
      page: 1,
      page_size: 20,
    };
    setLocalFilters(resetFilters);
    onFiltersChange(resetFilters);
  };

  const sectorOptions = [
    { value: "", label: "Tous les secteurs" },
    ...SECTORS.map((s) => ({ value: s, label: s })),
  ];
  const consentOptions = [
    { value: "", label: "Tous les consentements" },
    { value: "granted", label: "Consentement accorde uniquement" },
  ];
  const leadKindOptions = [
    { value: "", label: "Tous (B2B + B2C)" },
    { value: "b2b", label: "B2B uniquement" },
    { value: "b2c", label: "B2C uniquement" },
  ];

  return (
    <div className="rounded-lg border border-border bg-white p-4">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-6">
        {/* Search */}
        <div className="relative lg:col-span-2">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="Rechercher une entreprise..."
            value={localFilters.search || ""}
            onChange={(e) =>
              setLocalFilters({ ...localFilters, search: e.target.value })
            }
            onKeyDown={(e) => e.key === "Enter" && handleApply()}
            className="flex h-10 w-full rounded-md border border-border bg-white pl-10 pr-3 py-2 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
          />
        </div>

        {/* Score Min */}
        <Input
          type="number"
          placeholder="Score min"
          min={0}
          max={100}
          value={localFilters.min_score ?? ""}
          onChange={(e) =>
            setLocalFilters({
              ...localFilters,
              min_score: e.target.value ? Number(e.target.value) : undefined,
            })
          }
        />

        {/* Sector */}
        <Select
          options={sectorOptions}
          value={localFilters.sector || ""}
          onChange={(e) =>
            setLocalFilters({
              ...localFilters,
              sector: e.target.value || undefined,
            })
          }
        />

        {/* City */}
        <Input
          type="text"
          placeholder="Ville"
          value={localFilters.city || ""}
          onChange={(e) =>
            setLocalFilters({
              ...localFilters,
              city: e.target.value || undefined,
            })
          }
        />

        <Select
          options={leadKindOptions}
          value={localFilters.lead_kind || ""}
          onChange={(e) =>
            setLocalFilters({
              ...localFilters,
              lead_kind:
                e.target.value === "b2b" || e.target.value === "b2c"
                  ? e.target.value
                  : undefined,
            })
          }
        />
      </div>

      {/* Date range */}
      <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-6">
        <Input
          type="date"
          label="Date debut"
          value={localFilters.date_from || ""}
          onChange={(e) =>
            setLocalFilters({
              ...localFilters,
              date_from: e.target.value || undefined,
            })
          }
        />
        <Input
          type="date"
          label="Date fin"
          value={localFilters.date_to || ""}
          onChange={(e) =>
            setLocalFilters({
              ...localFilters,
              date_to: e.target.value || undefined,
            })
          }
        />
        <Select
          options={consentOptions}
          value={localFilters.consent_granted_only ? "granted" : ""}
          onChange={(e) =>
            setLocalFilters({
              ...localFilters,
              consent_granted_only:
                e.target.value === "granted" ? true : undefined,
            })
          }
        />
        <div className="flex items-end gap-2 lg:col-span-3">
          <Button onClick={handleApply} className="gap-2">
            <Search className="h-4 w-4" />
            Appliquer
          </Button>
          <Button onClick={handleReset} variant="outline" className="gap-2">
            <RotateCcw className="h-4 w-4" />
            Reinitialiser
          </Button>
        </div>
      </div>
    </div>
  );
}
