"use client";

import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { X, Plus, Search } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { SECTORS, SOURCES } from "@/lib/constants";
import { useCreateExtraction } from "@/hooks/use-extraction";

const extractionSchema = z.object({
  source: z.string().min(1, "La source est requise"),
  city: z.string().min(1, "La ville est requise"),
  radius_km: z
    .number({ invalid_type_error: "Le rayon est requis" })
    .min(1, "Minimum 1 km")
    .max(100, "Maximum 100 km"),
  sector_filter: z.string().optional(),
  max_leads: z
    .number({ invalid_type_error: "Le nombre est requis" })
    .min(1, "Minimum 1 lead")
    .max(1000, "Maximum 1 000 leads"),
});

type ExtractionFormData = z.infer<typeof extractionSchema>;

interface ExtractionFormProps {
  onSuccess?: () => void;
}

export function ExtractionForm({ onSuccess }: ExtractionFormProps) {
  const [keywords, setKeywords] = useState<string[]>([]);
  const [keywordInput, setKeywordInput] = useState("");
  const createExtraction = useCreateExtraction();

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<ExtractionFormData>({
    resolver: zodResolver(extractionSchema),
    defaultValues: {
      source: "whiteextractor",
      city: "",
      radius_km: 20,
      sector_filter: "",
      max_leads: 100,
    },
  });

  const addKeyword = () => {
    const trimmed = keywordInput.trim();
    if (trimmed && !keywords.includes(trimmed)) {
      setKeywords([...keywords, trimmed]);
      setKeywordInput("");
    }
  };

  const removeKeyword = (keyword: string) => {
    setKeywords(keywords.filter((k) => k !== keyword));
  };

  const handleKeywordKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      addKeyword();
    }
  };

  const sourceOptions = SOURCES.map((s) => ({ value: s.value, label: s.label }));
  const sectorOptions = SECTORS.map((s) => ({ value: s, label: s }));

  const onSubmit = async (data: ExtractionFormData) => {
    if (keywords.length === 0) {
      toast.error("Ajoutez au moins un mot-cle.");
      return;
    }

    try {
      await createExtraction.mutateAsync({
        source: data.source,
        keywords,
        city: data.city,
        radius_km: data.radius_km,
        sector_filter: data.sector_filter || undefined,
        max_leads: data.max_leads,
      });
      toast.success("Extraction lancee avec succes !");
      setKeywords([]);
      reset();
      onSuccess?.();
    } catch {
      toast.error("Erreur lors du lancement de l'extraction.");
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Search className="h-5 w-5 text-primary" />
          Nouvelle extraction
        </CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
          {/* Source Selector */}
          <Select
            id="source"
            label="Source de donnees"
            options={sourceOptions}
            error={errors.source?.message}
            {...register("source")}
          />

          {/* Keywords Tag Input */}
          <div>
            <label className="mb-1.5 block text-sm font-medium text-slate-700">
              Mots-cles
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                value={keywordInput}
                onChange={(e) => setKeywordInput(e.target.value)}
                onKeyDown={handleKeywordKeyDown}
                placeholder="Ajouter un mot-cle..."
                className="flex h-10 flex-1 rounded-md border border-border bg-white px-3 py-2 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
              />
              <Button type="button" variant="outline" onClick={addKeyword}>
                <Plus className="h-4 w-4" />
              </Button>
            </div>
            {keywords.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-2">
                {keywords.map((keyword) => (
                  <span
                    key={keyword}
                    className="inline-flex items-center gap-1 rounded-full bg-primary-50 px-3 py-1 text-sm font-medium text-primary-700"
                  >
                    {keyword}
                    <button
                      type="button"
                      onClick={() => removeKeyword(keyword)}
                      className="rounded-full p-0.5 hover:bg-primary-100"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </span>
                ))}
              </div>
            )}
            {keywords.length === 0 && (
              <p className="mt-1 text-xs text-muted-foreground">
                Appuyez sur Entree ou cliquez + pour ajouter un mot-cle
              </p>
            )}
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            {/* City */}
            <Input
              id="city"
              label="Ville"
              placeholder="Paris"
              error={errors.city?.message}
              {...register("city")}
            />

            {/* Radius */}
            <Input
              id="radius_km"
              label="Rayon (km)"
              type="number"
              placeholder="20"
              error={errors.radius_km?.message}
              {...register("radius_km", { valueAsNumber: true })}
            />

            {/* Sector */}
            <Select
              id="sector_filter"
              label="Secteur (optionnel)"
              placeholder="Choisir un secteur"
              options={sectorOptions}
              error={errors.sector_filter?.message}
              {...register("sector_filter")}
            />

            {/* Max leads */}
            <Input
              id="max_leads"
              label="Nombre max de leads"
              type="number"
              placeholder="100"
              error={errors.max_leads?.message}
              {...register("max_leads", { valueAsNumber: true })}
            />
          </div>

          <Button
            type="submit"
            size="lg"
            className="w-full gap-2"
            isLoading={createExtraction.isPending}
          >
            <Search className="h-5 w-5" />
            Lancer l&apos;extraction
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
