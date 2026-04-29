"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { BrainCircuit, RefreshCw, Save } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  useRecomputeScoring,
  useScoringProfile,
  useUpdateScoringProfile,
} from "@/hooks/use-scoring";

export default function ScoringPage() {
  const { data: profile } = useScoringProfile();
  const updateProfile = useUpdateScoringProfile();
  const recomputeScoring = useRecomputeScoring();

  const [name, setName] = useState("default");
  const [highThreshold, setHighThreshold] = useState("70");
  const [mediumThreshold, setMediumThreshold] = useState("40");
  const [weightsText, setWeightsText] = useState("{}");

  useEffect(() => {
    if (!profile) return;
    setName(profile.name || "default");
    setHighThreshold(String(profile.high_threshold ?? 70));
    setMediumThreshold(String(profile.medium_threshold ?? 40));
    setWeightsText(JSON.stringify(profile.weights ?? {}, null, 2));
  }, [profile]);

  const onSave = async () => {
    try {
      const parsedWeights = JSON.parse(weightsText || "{}");
      if (!parsedWeights || typeof parsedWeights !== "object" || Array.isArray(parsedWeights)) {
        throw new Error("Le JSON weights doit etre un objet.");
      }

      await updateProfile.mutateAsync({
        name: name.trim() || "default",
        high_threshold: Number(highThreshold),
        medium_threshold: Number(mediumThreshold),
        weights: parsedWeights,
      });
      toast.success("Profil de scoring enregistre.");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Erreur de sauvegarde";
      toast.error(message);
    }
  };

  const onRecompute = async () => {
    try {
      const response = await recomputeScoring.mutateAsync();
      toast.success(`${response.scored} leads rescored.`);
    } catch {
      toast.error("Recalcul du scoring impossible.");
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Scoring IA v2"
        description="Configuration des seuils et des poids de qualification."
        actions={
          <Button
            variant="outline"
            onClick={onRecompute}
            isLoading={recomputeScoring.isPending}
          >
            <RefreshCw className="h-4 w-4" />
            Recalcul global
          </Button>
        }
      />

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <BrainCircuit className="h-5 w-5 text-primary" />
            Profil de scoring
          </CardTitle>
          <CardDescription>
            Les poids sont exprimes par signal (email, phone, duplicate, source...).
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 md:grid-cols-3">
            <Input
              label="Nom du profil"
              value={name}
              onChange={(event) => setName(event.target.value)}
            />
            <Input
              label="Seuil Warm (>=)"
              type="number"
              min={1}
              max={100}
              value={highThreshold}
              onChange={(event) => setHighThreshold(event.target.value)}
            />
            <Input
              label="Seuil Tiede (>=)"
              type="number"
              min={0}
              max={99}
              value={mediumThreshold}
              onChange={(event) => setMediumThreshold(event.target.value)}
            />
          </div>

          <div className="space-y-2">
            <p className="text-sm font-medium text-slate-700">Weights JSON</p>
            <textarea
              className="min-h-64 w-full rounded-md border border-border px-3 py-2 font-mono text-xs focus:outline-none focus:ring-2 focus:ring-primary"
              value={weightsText}
              onChange={(event) => setWeightsText(event.target.value)}
            />
          </div>

          <Button onClick={onSave} isLoading={updateProfile.isPending}>
            <Save className="h-4 w-4" />
            Enregistrer
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
