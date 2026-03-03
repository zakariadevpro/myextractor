"use client";

import { useState } from "react";
import { Search } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { SECTORS, SOURCES } from "@/lib/constants";
import { useCreateExtraction } from "@/hooks/use-extraction";

function parseKeywordText(raw: string): string[] {
  const seen = new Set<string>();
  const values = raw
    .replace(/\n/g, ",")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
  const deduped: string[] = [];
  for (const item of values) {
    const key = item.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    deduped.push(item);
  }
  return deduped;
}

interface CommonFormFields {
  source: string;
  city: string;
  postal_code: string;
  department: string;
  radius_km: number;
  max_leads: number;
  keywords: string;
}

interface B2BFields extends CommonFormFields {
  company_name: string;
  sector_filter: string;
}

interface B2CFields extends CommonFormFields {
  first_name: string;
  last_name: string;
}

interface BothFields extends CommonFormFields {
  company_name: string;
  first_name: string;
  last_name: string;
  sector_filter: string;
}

export function ExtractionForm() {
  const createExtraction = useCreateExtraction();
  const sourceOptions = SOURCES.map((s) => ({ value: s.value, label: s.label }));
  const sectorOptions = SECTORS.map((s) => ({ value: s, label: s }));

  const [b2b, setB2B] = useState<B2BFields>({
    source: "whiteextractor",
    company_name: "",
    keywords: "",
    city: "",
    postal_code: "",
    department: "",
    radius_km: 20,
    sector_filter: "",
    max_leads: 100,
  });

  const [b2c, setB2C] = useState<B2CFields>({
    source: "whiteextractor",
    first_name: "",
    last_name: "",
    keywords: "",
    city: "",
    postal_code: "",
    department: "",
    radius_km: 20,
    max_leads: 100,
  });

  const [both, setBoth] = useState<BothFields>({
    source: "whiteextractor",
    company_name: "",
    first_name: "",
    last_name: "",
    keywords: "",
    city: "",
    postal_code: "",
    department: "",
    radius_km: 20,
    sector_filter: "",
    max_leads: 100,
  });

  const submitB2B = async (e: React.FormEvent) => {
    e.preventDefault();
    const keywords = parseKeywordText(b2b.keywords);
    if (!b2b.company_name.trim() && keywords.length === 0) {
      toast.error("B2B: saisis une raison sociale ou des mots-cles.");
      return;
    }
    try {
      await createExtraction.mutateAsync({
        source: b2b.source,
        target_kind: "b2b",
        company_name: b2b.company_name.trim() || undefined,
        keywords,
        city: b2b.city.trim() || undefined,
        postal_code: b2b.postal_code.trim() || undefined,
        department: b2b.department.trim() || undefined,
        radius_km: b2b.radius_km,
        sector_filter: b2b.sector_filter.trim() || undefined,
        max_leads: b2b.max_leads,
      });
      toast.success("Extraction B2B lancee.");
    } catch {
      toast.error("Erreur lancement B2B.");
    }
  };

  const submitB2C = async (e: React.FormEvent) => {
    e.preventDefault();
    const keywords = parseKeywordText(b2c.keywords);
    if (!b2c.first_name.trim() && !b2c.last_name.trim() && keywords.length === 0) {
      toast.error("B2C: saisis prenom/nom ou des mots-cles.");
      return;
    }
    try {
      await createExtraction.mutateAsync({
        source: b2c.source,
        target_kind: "b2c",
        first_name: b2c.first_name.trim() || undefined,
        last_name: b2c.last_name.trim() || undefined,
        keywords,
        city: b2c.city.trim() || undefined,
        postal_code: b2c.postal_code.trim() || undefined,
        department: b2c.department.trim() || undefined,
        radius_km: b2c.radius_km,
        max_leads: b2c.max_leads,
      });
      toast.success("Extraction B2C lancee.");
    } catch {
      toast.error("Erreur lancement B2C.");
    }
  };

  const submitBoth = async (e: React.FormEvent) => {
    e.preventDefault();
    const keywords = parseKeywordText(both.keywords);
    const hasB2B = !!both.company_name.trim();
    const hasB2C = !!both.first_name.trim() || !!both.last_name.trim();
    if (!hasB2B && !hasB2C && keywords.length === 0) {
      toast.error("Mixte: renseigne raison sociale, nom/prenom ou mots-cles.");
      return;
    }
    try {
      await createExtraction.mutateAsync({
        source: both.source,
        target_kind: "both",
        company_name: both.company_name.trim() || undefined,
        first_name: both.first_name.trim() || undefined,
        last_name: both.last_name.trim() || undefined,
        keywords,
        city: both.city.trim() || undefined,
        postal_code: both.postal_code.trim() || undefined,
        department: both.department.trim() || undefined,
        radius_km: both.radius_km,
        sector_filter: both.sector_filter.trim() || undefined,
        max_leads: both.max_leads,
      });
      toast.success("Extraction mixte lancee.");
    } catch {
      toast.error("Erreur lancement mixte.");
    }
  };

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Mode B2B - Societes</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={submitB2B} className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <Select
                id="b2b-source"
                label="Source"
                options={sourceOptions}
                value={b2b.source}
                onChange={(e) => setB2B((prev) => ({ ...prev, source: e.target.value }))}
              />
              <Input
                id="b2b-company"
                label="Raison sociale"
                placeholder="Ex: Dupont Services"
                value={b2b.company_name}
                onChange={(e) => setB2B((prev) => ({ ...prev, company_name: e.target.value }))}
              />
              <Input
                id="b2b-city"
                label="Ville"
                placeholder="Paris"
                value={b2b.city}
                onChange={(e) => setB2B((prev) => ({ ...prev, city: e.target.value }))}
              />
              <Input
                id="b2b-postal"
                label="Code postal"
                placeholder="75001"
                value={b2b.postal_code}
                onChange={(e) => setB2B((prev) => ({ ...prev, postal_code: e.target.value }))}
              />
              <Input
                id="b2b-department"
                label="Departement"
                placeholder="75"
                value={b2b.department}
                onChange={(e) => setB2B((prev) => ({ ...prev, department: e.target.value }))}
              />
              <Select
                id="b2b-sector"
                label="Secteur"
                placeholder="Choisir un secteur"
                options={sectorOptions}
                value={b2b.sector_filter}
                onChange={(e) => setB2B((prev) => ({ ...prev, sector_filter: e.target.value }))}
              />
              <Input
                id="b2b-radius"
                label="Rayon (km)"
                type="number"
                value={b2b.radius_km}
                onChange={(e) =>
                  setB2B((prev) => ({ ...prev, radius_km: Number(e.target.value) || 1 }))
                }
              />
              <Input
                id="b2b-max"
                label="Max leads"
                type="number"
                value={b2b.max_leads}
                onChange={(e) =>
                  setB2B((prev) => ({ ...prev, max_leads: Number(e.target.value) || 1 }))
                }
              />
            </div>
            <Input
              id="b2b-keywords"
              label="Mots-cles (optionnel, separes par virgules)"
              placeholder="plomberie, depannage, urgent"
              value={b2b.keywords}
              onChange={(e) => setB2B((prev) => ({ ...prev, keywords: e.target.value }))}
            />
            <Button type="submit" className="w-full gap-2" isLoading={createExtraction.isPending}>
              <Search className="h-4 w-4" />
              Lancer Extraction B2B
            </Button>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Mode B2C - Particuliers</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={submitB2C} className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <Select
                id="b2c-source"
                label="Source"
                options={sourceOptions}
                value={b2c.source}
                onChange={(e) => setB2C((prev) => ({ ...prev, source: e.target.value }))}
              />
              <Input
                id="b2c-first"
                label="Prenom"
                placeholder="Jean"
                value={b2c.first_name}
                onChange={(e) => setB2C((prev) => ({ ...prev, first_name: e.target.value }))}
              />
              <Input
                id="b2c-last"
                label="Nom"
                placeholder="Dupont"
                value={b2c.last_name}
                onChange={(e) => setB2C((prev) => ({ ...prev, last_name: e.target.value }))}
              />
              <Input
                id="b2c-city"
                label="Ville"
                placeholder="Paris"
                value={b2c.city}
                onChange={(e) => setB2C((prev) => ({ ...prev, city: e.target.value }))}
              />
              <Input
                id="b2c-postal"
                label="Code postal"
                placeholder="75001"
                value={b2c.postal_code}
                onChange={(e) => setB2C((prev) => ({ ...prev, postal_code: e.target.value }))}
              />
              <Input
                id="b2c-department"
                label="Departement"
                placeholder="75"
                value={b2c.department}
                onChange={(e) => setB2C((prev) => ({ ...prev, department: e.target.value }))}
              />
              <Input
                id="b2c-radius"
                label="Rayon (km)"
                type="number"
                value={b2c.radius_km}
                onChange={(e) =>
                  setB2C((prev) => ({ ...prev, radius_km: Number(e.target.value) || 1 }))
                }
              />
              <Input
                id="b2c-max"
                label="Max leads"
                type="number"
                value={b2c.max_leads}
                onChange={(e) =>
                  setB2C((prev) => ({ ...prev, max_leads: Number(e.target.value) || 1 }))
                }
              />
            </div>
            <Input
              id="b2c-keywords"
              label="Mots-cles (optionnel)"
              placeholder="assurance, credit, mutuelle"
              value={b2c.keywords}
              onChange={(e) => setB2C((prev) => ({ ...prev, keywords: e.target.value }))}
            />
            <Button type="submit" className="w-full gap-2" isLoading={createExtraction.isPending}>
              <Search className="h-4 w-4" />
              Lancer Extraction B2C
            </Button>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Mode Mixte - B2B + B2C</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={submitBoth} className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <Select
                id="both-source"
                label="Source"
                options={sourceOptions}
                value={both.source}
                onChange={(e) => setBoth((prev) => ({ ...prev, source: e.target.value }))}
              />
              <Input
                id="both-company"
                label="Raison sociale"
                placeholder="Ex: Alpha Conseil"
                value={both.company_name}
                onChange={(e) => setBoth((prev) => ({ ...prev, company_name: e.target.value }))}
              />
              <Input
                id="both-first"
                label="Prenom"
                placeholder="Jean"
                value={both.first_name}
                onChange={(e) => setBoth((prev) => ({ ...prev, first_name: e.target.value }))}
              />
              <Input
                id="both-last"
                label="Nom"
                placeholder="Dupont"
                value={both.last_name}
                onChange={(e) => setBoth((prev) => ({ ...prev, last_name: e.target.value }))}
              />
              <Input
                id="both-city"
                label="Ville"
                placeholder="Paris"
                value={both.city}
                onChange={(e) => setBoth((prev) => ({ ...prev, city: e.target.value }))}
              />
              <Input
                id="both-postal"
                label="Code postal"
                placeholder="75001"
                value={both.postal_code}
                onChange={(e) => setBoth((prev) => ({ ...prev, postal_code: e.target.value }))}
              />
              <Input
                id="both-department"
                label="Departement"
                placeholder="75"
                value={both.department}
                onChange={(e) => setBoth((prev) => ({ ...prev, department: e.target.value }))}
              />
              <Select
                id="both-sector"
                label="Secteur"
                placeholder="Choisir un secteur"
                options={sectorOptions}
                value={both.sector_filter}
                onChange={(e) => setBoth((prev) => ({ ...prev, sector_filter: e.target.value }))}
              />
              <Input
                id="both-radius"
                label="Rayon (km)"
                type="number"
                value={both.radius_km}
                onChange={(e) =>
                  setBoth((prev) => ({ ...prev, radius_km: Number(e.target.value) || 1 }))
                }
              />
              <Input
                id="both-max"
                label="Max leads"
                type="number"
                value={both.max_leads}
                onChange={(e) =>
                  setBoth((prev) => ({ ...prev, max_leads: Number(e.target.value) || 1 }))
                }
              />
            </div>
            <Input
              id="both-keywords"
              label="Mots-cles (optionnel)"
              placeholder="services, nettoyage, assistance"
              value={both.keywords}
              onChange={(e) => setBoth((prev) => ({ ...prev, keywords: e.target.value }))}
            />
            <Button type="submit" className="w-full gap-2" isLoading={createExtraction.isPending}>
              <Search className="h-4 w-4" />
              Lancer Extraction Mixte
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
