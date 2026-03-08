"use client";

import { useMemo, useState } from "react";
import { FileUp, UploadCloud } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { useImportB2CCsvIntake } from "@/hooks/use-leads";
import type { B2CCsvImportSummary } from "@/types/lead";

const CONSENT_SOURCES = [
  { value: "web_form", label: "Web Form" },
  { value: "meta_lead_ads", label: "Meta Lead Ads" },
  { value: "google_lead_form", label: "Google Lead Form" },
  { value: "partner_api", label: "Partner API" },
  { value: "crm_import", label: "CRM Import" },
] as const;

const SOURCE_CHANNELS = [
  { value: "", label: "Non renseigne" },
  { value: "web", label: "Web" },
  { value: "facebook", label: "Facebook" },
  { value: "instagram", label: "Instagram" },
  { value: "google", label: "Google" },
  { value: "tiktok", label: "TikTok" },
  { value: "partner", label: "Partner" },
  { value: "import", label: "Import" },
] as const;

type MappingKey =
  | "full_name"
  | "first_name"
  | "last_name"
  | "email"
  | "phone"
  | "city"
  | "consent_proof_ref"
  | "consent_at"
  | "source_campaign"
  | "source_channel"
  | "purpose"
  | "double_opt_in";

const MAPPING_FIELDS: { key: MappingKey; label: string; required?: boolean }[] = [
  { key: "full_name", label: "Nom complet (ou prenom+nom)", required: false },
  { key: "first_name", label: "Prenom" },
  { key: "last_name", label: "Nom" },
  { key: "email", label: "Email" },
  { key: "phone", label: "Telephone" },
  { key: "city", label: "Ville" },
  { key: "consent_proof_ref", label: "Preuve consentement" },
  { key: "consent_at", label: "Date consentement" },
  { key: "source_campaign", label: "Campagne" },
  { key: "source_channel", label: "Canal source" },
  { key: "purpose", label: "Finalite" },
  { key: "double_opt_in", label: "Double opt-in" },
];

function detectDelimiter(line: string): string {
  const candidates = [",", ";", "\t", "|"];
  let winner = ",";
  let maxCount = -1;
  for (const sep of candidates) {
    const count = line.split(sep).length;
    if (count > maxCount) {
      maxCount = count;
      winner = sep;
    }
  }
  return winner;
}

function parseCsvLine(line: string, delimiter: string): string[] {
  const result: string[] = [];
  let current = "";
  let inQuotes = false;
  for (let i = 0; i < line.length; i += 1) {
    const char = line[i];
    if (char === '"') {
      if (inQuotes && line[i + 1] === '"') {
        current += '"';
        i += 1;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }
    if (char === delimiter && !inQuotes) {
      result.push(current.trim());
      current = "";
      continue;
    }
    current += char;
  }
  result.push(current.trim());
  return result.map((item) => item.replace(/^"|"$/g, "").trim());
}

function extractHeaders(content: string): string[] {
  const firstLine = content
    .split(/\r?\n/)
    .map((line) => line.trim())
    .find((line) => line.length > 0);
  if (!firstLine) return [];
  const delimiter = detectDelimiter(firstLine);
  return parseCsvLine(firstLine, delimiter).filter(Boolean);
}

export function B2CIntakeForm() {
  const importCsv = useImportB2CCsvIntake();
  const [file, setFile] = useState<File | null>(null);
  const [headers, setHeaders] = useState<string[]>([]);
  const [result, setResult] = useState<B2CCsvImportSummary | null>(null);
  const [mapping, setMapping] = useState<Partial<Record<MappingKey, string>>>({});

  const [consentSource, setConsentSource] = useState("crm_import");
  const [consentTextVersion, setConsentTextVersion] = useState("v1.0");
  const [privacyPolicyVersion, setPrivacyPolicyVersion] = useState("pp-2026-01");
  const [sourceChannel, setSourceChannel] = useState("");
  const [purpose, setPurpose] = useState("prospection_commerciale");
  const [proofPrefix, setProofPrefix] = useState("csv-b2c");
  const [doubleOptInDefault, setDoubleOptInDefault] = useState(false);

  const headerOptions = useMemo(
    () => [{ value: "", label: "Non mappe" }, ...headers.map((h) => ({ value: h, label: h }))],
    [headers]
  );

  const handleFileChange = async (selected: File | null) => {
    setResult(null);
    setFile(selected);
    if (!selected) {
      setHeaders([]);
      setMapping({});
      return;
    }
    const content = await selected.text();
    const foundHeaders = extractHeaders(content);
    setHeaders(foundHeaders);
    if (foundHeaders.length === 0) {
      toast.error("Impossible de lire les en-tetes du CSV.");
    }
  };

  const handleImport = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) {
      toast.error("Choisis un fichier CSV.");
      return;
    }
    const hasFullName = !!mapping.full_name;
    const hasSplitName = !!mapping.first_name && !!mapping.last_name;
    if (!hasFullName && !hasSplitName) {
      toast.error("Mappe au moins Nom complet, ou Prenom + Nom.");
      return;
    }

    const mappingPayload: Record<string, string> = {};
    for (const [key, value] of Object.entries(mapping)) {
      if (value) mappingPayload[key] = value;
    }

    try {
      const response = await importCsv.mutateAsync({
        file,
        mapping: mappingPayload,
        defaults: {
          consent_source: consentSource,
          consent_text_version: consentTextVersion,
          privacy_policy_version: privacyPolicyVersion,
          source_channel: sourceChannel,
          purpose,
          proof_prefix: proofPrefix,
          double_opt_in: doubleOptInDefault,
        },
      });
      setResult(response);
      if (response.failed > 0) {
        toast.warning(
          `Import termine: ${response.imported} importes, ${response.failed} en erreur.`
        );
      } else {
        toast.success(`Import termine: ${response.imported} leads B2C importes.`);
      }
    } catch {
      toast.error("Erreur lors de l'import CSV B2C.");
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <UploadCloud className="h-5 w-5 text-primary" />
          Import CSV B2C Avec Mapping
        </CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleImport} className="space-y-5">
          <div className="space-y-2">
            <label className="block text-sm font-medium text-slate-700">Fichier CSV</label>
            <input
              type="file"
              accept=".csv,text/csv"
              onChange={(e) => handleFileChange(e.target.files?.[0] ?? null)}
              className="block w-full text-sm file:mr-4 file:rounded-md file:border file:border-border file:bg-slate-50 file:px-3 file:py-2 file:text-sm file:font-medium"
            />
            {file && <p className="text-xs text-muted-foreground">Fichier: {file.name}</p>}
          </div>

          {headers.length > 0 && (
            <>
              <div className="rounded-md border border-border p-3">
                <p className="mb-2 text-xs font-medium text-slate-700">Mapping manuel des colonnes</p>
                <div className="grid gap-3 sm:grid-cols-2">
                  {MAPPING_FIELDS.map((field) => (
                    <Select
                      key={field.key}
                      label={field.label}
                      options={headerOptions}
                      value={mapping[field.key] ?? ""}
                      onChange={(e) =>
                        setMapping((prev) => ({ ...prev, [field.key]: e.target.value }))
                      }
                    />
                  ))}
                </div>
              </div>

              <div className="rounded-md border border-border p-3">
                <p className="mb-2 text-xs font-medium text-slate-700">
                  Valeurs par defaut (si non mappees dans le CSV)
                </p>
                <div className="grid gap-3 sm:grid-cols-2">
                  <Select
                    label="Source consentement"
                    options={CONSENT_SOURCES.map((item) => ({ value: item.value, label: item.label }))}
                    value={consentSource}
                    onChange={(e) => setConsentSource(e.target.value)}
                  />
                  <Select
                    label="Canal source"
                    options={SOURCE_CHANNELS.map((item) => ({ value: item.value, label: item.label }))}
                    value={sourceChannel}
                    onChange={(e) => setSourceChannel(e.target.value)}
                  />
                  <Input
                    label="Version texte consentement"
                    value={consentTextVersion}
                    onChange={(e) => setConsentTextVersion(e.target.value)}
                  />
                  <Input
                    label="Version privacy policy"
                    value={privacyPolicyVersion}
                    onChange={(e) => setPrivacyPolicyVersion(e.target.value)}
                  />
                  <Input
                    label="Finalite"
                    value={purpose}
                    onChange={(e) => setPurpose(e.target.value)}
                  />
                  <Input
                    label="Prefixe preuve auto"
                    value={proofPrefix}
                    onChange={(e) => setProofPrefix(e.target.value)}
                  />
                </div>
                <label className="mt-3 flex items-center gap-2 text-sm text-slate-700">
                  <input
                    type="checkbox"
                    checked={doubleOptInDefault}
                    onChange={(e) => setDoubleOptInDefault(e.target.checked)}
                    className="h-4 w-4 rounded border-border"
                  />
                  Double opt-in par defaut
                </label>
              </div>
            </>
          )}

          <Button type="submit" className="w-full gap-2" isLoading={importCsv.isPending}>
            <FileUp className="h-4 w-4" />
            Importer Le CSV B2C
          </Button>
        </form>

        {result && (
          <div className="mt-5 rounded-md border border-border bg-slate-50 p-3">
            <p className="text-sm font-semibold text-slate-900">Resume import</p>
            <p className="mt-1 text-xs text-muted-foreground">
              {result.imported} importes, {result.duplicates} doublons, {result.failed} erreurs sur{" "}
              {result.total_rows} lignes.
            </p>
            {result.errors.length > 0 && (
              <ul className="mt-2 max-h-40 list-disc space-y-1 overflow-auto pl-4 text-xs text-danger">
                {result.errors.map((error, idx) => (
                  <li key={`${error.row_number}-${idx}`}>
                    Ligne {error.row_number}: {error.message}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
