"use client";

import { useState } from "react";
import { UserPlus } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { useCreateB2CLeadIntake } from "@/hooks/use-leads";

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

export function B2CIntakeForm() {
  const createB2CLead = useCreateB2CLeadIntake();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [city, setCity] = useState("");
  const [consentSource, setConsentSource] = useState("web_form");
  const [consentTextVersion, setConsentTextVersion] = useState("v1.0");
  const [consentProofRef, setConsentProofRef] = useState("");
  const [privacyPolicyVersion, setPrivacyPolicyVersion] = useState("pp-2026-01");
  const [sourceCampaign, setSourceCampaign] = useState("");
  const [sourceChannel, setSourceChannel] = useState("");
  const [purpose, setPurpose] = useState("prospection_commerciale");
  const [doubleOptIn, setDoubleOptIn] = useState(false);

  const resetForm = () => {
    setFullName("");
    setEmail("");
    setPhone("");
    setCity("");
    setConsentSource("web_form");
    setConsentTextVersion("v1.0");
    setConsentProofRef("");
    setPrivacyPolicyVersion("pp-2026-01");
    setSourceCampaign("");
    setSourceChannel("");
    setPurpose("prospection_commerciale");
    setDoubleOptIn(false);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!fullName.trim()) {
      toast.error("Le nom complet est requis.");
      return;
    }
    if (!email.trim() && !phone.trim()) {
      toast.error("Email ou telephone requis pour un contact B2C.");
      return;
    }
    if (!consentProofRef.trim()) {
      toast.error("La preuve de consentement est requise.");
      return;
    }

    const now = new Date().toISOString();
    try {
      await createB2CLead.mutateAsync({
        full_name: fullName.trim(),
        email: email.trim() || null,
        phone: phone.trim() || null,
        city: city.trim() || null,
        consent_source: consentSource as
          | "web_form"
          | "meta_lead_ads"
          | "google_lead_form"
          | "partner_api"
          | "crm_import",
        consent_at: now,
        consent_text_version: consentTextVersion.trim(),
        consent_proof_ref: consentProofRef.trim(),
        privacy_policy_version: privacyPolicyVersion.trim(),
        source_campaign: sourceCampaign.trim() || null,
        source_channel: sourceChannel
          ? (sourceChannel as
              | "web"
              | "facebook"
              | "instagram"
              | "google"
              | "tiktok"
              | "partner"
              | "import")
          : null,
        purpose: purpose.trim() || null,
        double_opt_in: doubleOptIn,
        double_opt_in_at: doubleOptIn ? now : null,
      });
      toast.success("Contact B2C integre avec consentement.");
      resetForm();
    } catch {
      toast.error("Erreur lors de l'integration B2C.");
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <UserPlus className="h-5 w-5 text-primary" />
          Intake B2C Consentie
        </CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <Input
            label="Nom complet"
            placeholder="Jean Dupont"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
          />
          <div className="grid gap-4 sm:grid-cols-2">
            <Input
              label="Email"
              placeholder="jean.dupont@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
            <Input
              label="Telephone"
              placeholder="+33611223344"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
            />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <Input
              label="Ville"
              placeholder="Paris"
              value={city}
              onChange={(e) => setCity(e.target.value)}
            />
            <Select
              label="Source consentement"
              options={CONSENT_SOURCES.map((item) => ({ value: item.value, label: item.label }))}
              value={consentSource}
              onChange={(e) => setConsentSource(e.target.value)}
            />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <Input
              label="Version texte consentement"
              value={consentTextVersion}
              onChange={(e) => setConsentTextVersion(e.target.value)}
            />
            <Input
              label="Preuve de consentement"
              placeholder="form-20260301-0001"
              value={consentProofRef}
              onChange={(e) => setConsentProofRef(e.target.value)}
            />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <Input
              label="Version privacy policy"
              value={privacyPolicyVersion}
              onChange={(e) => setPrivacyPolicyVersion(e.target.value)}
            />
            <Select
              label="Canal source"
              options={SOURCE_CHANNELS.map((item) => ({ value: item.value, label: item.label }))}
              value={sourceChannel}
              onChange={(e) => setSourceChannel(e.target.value)}
            />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <Input
              label="Campagne"
              placeholder="landing-assurance-auto"
              value={sourceCampaign}
              onChange={(e) => setSourceCampaign(e.target.value)}
            />
            <Input
              label="Finalite"
              value={purpose}
              onChange={(e) => setPurpose(e.target.value)}
            />
          </div>
          <label className="flex items-center gap-2 text-sm text-slate-700">
            <input
              type="checkbox"
              checked={doubleOptIn}
              onChange={(e) => setDoubleOptIn(e.target.checked)}
              className="h-4 w-4 rounded border-border"
            />
            Double opt-in valide
          </label>
          <Button type="submit" className="w-full gap-2" isLoading={createB2CLead.isPending}>
            <UserPlus className="h-4 w-4" />
            Integrer le contact B2C
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

