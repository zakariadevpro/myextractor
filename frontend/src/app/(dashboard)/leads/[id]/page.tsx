"use client";

import { use } from "react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { format } from "date-fns";
import { fr } from "date-fns/locale";
import {
  ArrowLeft,
  Building2,
  Mail,
  Phone,
  MapPin,
  Globe,
  Calendar,
  ShieldCheck,
} from "lucide-react";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { LeadScoreBadge } from "@/components/features/leads/lead-score-badge";
import { useLead, useLeadConsent, useUpdateLeadConsent } from "@/hooks/use-leads";
import { useAuth } from "@/hooks/use-auth";
import { hasMinimumRole } from "@/lib/authz";
import type {
  ConsentScope,
  ConsentStatus,
  LawfulBasis,
  LeadConsentUpdatePayload,
} from "@/types/lead";

const CONSENT_STATUS_OPTIONS: { value: ConsentStatus; label: string }[] = [
  { value: "granted", label: "Accorde" },
  { value: "denied", label: "Refuse" },
  { value: "revoked", label: "Revoque" },
  { value: "unknown", label: "Inconnu" },
];

const CONSENT_SCOPE_OPTIONS: { value: ConsentScope; label: string }[] = [
  { value: "all", label: "Tous canaux" },
  { value: "phone", label: "Telephone" },
  { value: "email", label: "Email" },
  { value: "sms", label: "SMS" },
  { value: "whatsapp", label: "WhatsApp" },
];

const LAWFUL_BASIS_OPTIONS: { value: LawfulBasis; label: string }[] = [
  { value: "consent", label: "Consentement" },
  { value: "contract", label: "Contrat" },
  { value: "legitimate_interest", label: "Interet legitime" },
];

function toDateTimeLocal(input: string | null): string {
  if (!input) return "";
  const date = new Date(input);
  if (Number.isNaN(date.getTime())) return "";
  return date.toISOString().slice(0, 16);
}

function toIsoOrNull(input: string): string | null {
  if (!input) return null;
  const date = new Date(input);
  if (Number.isNaN(date.getTime())) return null;
  return date.toISOString();
}

function emptyToNull(value: string): string | null {
  const next = value.trim();
  return next.length > 0 ? next : null;
}

export default function LeadDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const { user } = useAuth();
  const canEditConsent = hasMinimumRole(user?.role, "manager");
  const { data: lead, isLoading } = useLead(id);
  const { data: consent, isLoading: isConsentLoading } = useLeadConsent(id);
  const updateLeadConsent = useUpdateLeadConsent();
  const [consentStatus, setConsentStatus] = useState<ConsentStatus>("unknown");
  const [consentScope, setConsentScope] = useState<ConsentScope>("all");
  const [lawfulBasis, setLawfulBasis] = useState<LawfulBasis>("consent");
  const [consentSource, setConsentSource] = useState("");
  const [purpose, setPurpose] = useState("");
  const [consentAt, setConsentAt] = useState("");
  const [doubleOptIn, setDoubleOptIn] = useState(false);
  const [doubleOptInAt, setDoubleOptInAt] = useState("");
  const [consentTextVersion, setConsentTextVersion] = useState("");
  const [privacyPolicyVersion, setPrivacyPolicyVersion] = useState("");
  const [consentProofRef, setConsentProofRef] = useState("");

  useEffect(() => {
    if (!consent) return;
    setConsentStatus(consent.consent_status);
    setConsentScope(consent.consent_scope);
    setLawfulBasis(consent.lawful_basis);
    setConsentSource(consent.consent_source ?? "");
    setPurpose(consent.purpose ?? "");
    setConsentAt(toDateTimeLocal(consent.consent_at));
    setDoubleOptIn(consent.double_opt_in);
    setDoubleOptInAt(toDateTimeLocal(consent.double_opt_in_at));
    setConsentTextVersion(consent.consent_text_version ?? "");
    setPrivacyPolicyVersion(consent.privacy_policy_version ?? "");
    setConsentProofRef(consent.consent_proof_ref ?? "");
  }, [consent]);

  const handleConsentSave = async () => {
    if (!canEditConsent) {
      toast.error("Seul un manager/admin peut modifier le consentement.");
      return;
    }

    const payload: LeadConsentUpdatePayload = {
      consent_status: consentStatus,
      consent_scope: consentScope,
      lawful_basis: lawfulBasis,
      consent_source: emptyToNull(consentSource),
      purpose: emptyToNull(purpose),
      consent_text_version: emptyToNull(consentTextVersion),
      privacy_policy_version: emptyToNull(privacyPolicyVersion),
      consent_proof_ref: emptyToNull(consentProofRef),
      consent_at: toIsoOrNull(consentAt),
      double_opt_in: doubleOptIn,
      double_opt_in_at: doubleOptIn ? toIsoOrNull(doubleOptInAt) : null,
    };

    try {
      await updateLeadConsent.mutateAsync({ leadId: id, payload });
      toast.success("Consentement mis a jour.");
    } catch {
      toast.error("Echec de mise a jour du consentement.");
    }
  };

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          <p className="text-sm text-muted-foreground">
            Chargement du lead...
          </p>
        </div>
      </div>
    );
  }

  if (!lead) {
    return (
      <div className="flex h-64 flex-col items-center justify-center gap-4">
        <p className="text-lg font-medium text-slate-900">Lead non trouve</p>
        <Link href="/leads">
          <Button variant="outline">Retour aux leads</Button>
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link href="/leads">
          <Button variant="ghost" size="icon">
            <ArrowLeft className="h-5 w-5" />
          </Button>
        </Link>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-slate-900">
              {lead.company_name}
            </h1>
            <LeadScoreBadge score={lead.quality_score} />
            {lead.is_duplicate && (
              <Badge variant="warning">Doublon</Badge>
            )}
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            {lead.sector ?? "-"} - {lead.city ?? "-"}
            {lead.siren && ` - SIREN: ${lead.siren}`}
          </p>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Company Info */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Building2 className="h-5 w-5 text-primary" />
              Informations entreprise
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-start gap-3">
              <MapPin className="mt-0.5 h-4 w-4 text-slate-400" />
              <div>
                <p className="text-sm font-medium text-slate-900">Adresse</p>
                <p className="text-sm text-slate-600">
                  {lead.address || "-"}
                  {lead.postal_code && `, ${lead.postal_code}`} {lead.city || ""}
                  {lead.department && `, ${lead.department}`}
                  {lead.region && ` (${lead.region})`}
                </p>
              </div>
            </div>
            {lead.website && (
              <div className="flex items-start gap-3">
                <Globe className="mt-0.5 h-4 w-4 text-slate-400" />
                <div>
                  <p className="text-sm font-medium text-slate-900">
                    Site web
                  </p>
                  <a
                    href={lead.website}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm text-primary hover:underline"
                  >
                    {lead.website}
                  </a>
                </div>
              </div>
            )}
            {lead.naf_code && (
              <div className="flex items-start gap-3">
                <Building2 className="mt-0.5 h-4 w-4 text-slate-400" />
                <div>
                  <p className="text-sm font-medium text-slate-900">Code NAF</p>
                  <p className="text-sm text-slate-600">{lead.naf_code}</p>
                </div>
              </div>
            )}
            <div className="flex items-start gap-3">
              <Calendar className="mt-0.5 h-4 w-4 text-slate-400" />
              <div>
                <p className="text-sm font-medium text-slate-900">
                  Date d&apos;extraction
                </p>
                <p className="text-sm text-slate-600">
                  {format(new Date(lead.created_at), "dd MMMM yyyy", {
                    locale: fr,
                  })}
                </p>
              </div>
            </div>
            <div className="text-xs text-muted-foreground">
              Source: {lead.source}
            </div>
          </CardContent>
        </Card>

        {/* Contact Info */}
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <ShieldCheck className="h-5 w-5 text-primary" />
                Conformite & Consentement
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {isConsentLoading ? (
                <p className="text-sm text-muted-foreground">
                  Chargement du consentement...
                </p>
              ) : (
                <>
                  <div className="flex items-center gap-2">
                    <Badge variant={consentStatus === "granted" ? "success" : "secondary"}>
                      {consentStatus}
                    </Badge>
                    <Badge variant="outline">{lawfulBasis}</Badge>
                    {canEditConsent ? (
                      <Badge variant="success">Edition autorisee</Badge>
                    ) : (
                      <Badge variant="secondary">Lecture seule</Badge>
                    )}
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <Select
                      label="Statut consentement"
                      value={consentStatus}
                      options={CONSENT_STATUS_OPTIONS}
                      onChange={(e) => setConsentStatus(e.target.value as ConsentStatus)}
                      disabled={!canEditConsent}
                    />
                    <Select
                      label="Portee"
                      value={consentScope}
                      options={CONSENT_SCOPE_OPTIONS}
                      onChange={(e) => setConsentScope(e.target.value as ConsentScope)}
                      disabled={!canEditConsent}
                    />
                    <Select
                      label="Base legale"
                      value={lawfulBasis}
                      options={LAWFUL_BASIS_OPTIONS}
                      onChange={(e) => setLawfulBasis(e.target.value as LawfulBasis)}
                      disabled={!canEditConsent}
                    />
                    <Input
                      label="Source consentement"
                      value={consentSource}
                      onChange={(e) => setConsentSource(e.target.value)}
                      placeholder="web_form, meta_ads..."
                      disabled={!canEditConsent}
                    />
                    <Input
                      type="datetime-local"
                      label="Date consentement"
                      value={consentAt}
                      onChange={(e) => setConsentAt(e.target.value)}
                      disabled={!canEditConsent}
                    />
                    <Input
                      label="Finalite"
                      value={purpose}
                      onChange={(e) => setPurpose(e.target.value)}
                      placeholder="prospection_commerciale"
                      disabled={!canEditConsent}
                    />
                    <Input
                      label="Version texte consentement"
                      value={consentTextVersion}
                      onChange={(e) => setConsentTextVersion(e.target.value)}
                      placeholder="v1.0"
                      disabled={!canEditConsent}
                    />
                    <Input
                      label="Version politique privacy"
                      value={privacyPolicyVersion}
                      onChange={(e) => setPrivacyPolicyVersion(e.target.value)}
                      placeholder="2026-02"
                      disabled={!canEditConsent}
                    />
                  </div>
                  <Input
                    label="Reference preuve"
                    value={consentProofRef}
                    onChange={(e) => setConsentProofRef(e.target.value)}
                    placeholder="form_submission_id / event_id"
                    disabled={!canEditConsent}
                  />
                  <div className="rounded-lg border border-border p-3">
                    <label className="flex items-center gap-2 text-sm text-slate-700">
                      <input
                        type="checkbox"
                        checked={doubleOptIn}
                        onChange={(e) => setDoubleOptIn(e.target.checked)}
                        disabled={!canEditConsent}
                      />
                      Double opt-in valide
                    </label>
                    <div className="mt-2">
                      <Input
                        type="datetime-local"
                        label="Date double opt-in"
                        value={doubleOptInAt}
                        onChange={(e) => setDoubleOptInAt(e.target.value)}
                        disabled={!canEditConsent || !doubleOptIn}
                      />
                    </div>
                  </div>
                  {canEditConsent ? (
                    <div className="flex justify-end">
                      <Button onClick={handleConsentSave} isLoading={updateLeadConsent.isPending}>
                        Enregistrer consentement
                      </Button>
                    </div>
                  ) : null}
                </>
              )}
            </CardContent>
          </Card>

          {/* Emails */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Mail className="h-5 w-5 text-primary" />
                Emails ({lead.emails.length})
              </CardTitle>
            </CardHeader>
            <CardContent>
              {lead.emails.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  Aucun email trouve
                </p>
              ) : (
                <div className="space-y-3">
                  {lead.emails.map((email, index) => (
                    <div
                      key={index}
                      className="flex items-center justify-between rounded-lg border border-border p-3"
                    >
                      <div>
                        <p className="text-sm font-medium text-slate-900">
                          {email.email}
                        </p>
                        {email.is_primary && (
                          <p className="text-xs text-muted-foreground">
                            Email principal
                          </p>
                        )}
                      </div>
                      <Badge
                        variant={email.is_valid ? "success" : email.is_valid === false ? "danger" : "secondary"}
                      >
                        {email.is_valid ? "Valide" : email.is_valid === false ? "Non valide" : "Non verifie"}
                      </Badge>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Phones */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Phone className="h-5 w-5 text-primary" />
                Telephones ({lead.phones.length})
              </CardTitle>
            </CardHeader>
            <CardContent>
              {lead.phones.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  Aucun telephone trouve
                </p>
              ) : (
                <div className="space-y-3">
                  {lead.phones.map((phone, index) => (
                    <div
                      key={index}
                      className="flex items-center justify-between rounded-lg border border-border p-3"
                    >
                      <div>
                        <p className="text-sm font-medium text-slate-900">
                          {phone.phone_normalized || phone.phone_raw || "-"}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {phone.phone_type}{phone.is_primary ? " - Principal" : ""}
                        </p>
                      </div>
                      <Badge
                        variant={phone.is_valid ? "success" : phone.is_valid === false ? "danger" : "secondary"}
                      >
                        {phone.is_valid ? "Valide" : phone.is_valid === false ? "Non valide" : "Non verifie"}
                      </Badge>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
