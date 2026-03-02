"use client";

import { useMemo, useState } from "react";
import { toast } from "sonner";
import { Workflow, PlayCircle, TestTube2 } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { useCreateWorkflow, useRunWorkflows, useWorkflows } from "@/hooks/use-workflows";

const DEFAULT_CONDITIONS = {
  lead_kind: "b2b",
  min_score: 60,
  has_email: true,
};

const DEFAULT_ACTIONS = {
  score_delta: 5,
};

export default function WorkflowsPage() {
  const { data: workflows = [] } = useWorkflows();
  const createWorkflow = useCreateWorkflow();
  const runWorkflows = useRunWorkflows();

  const [name, setName] = useState("Boost B2B Hot");
  const [trigger, setTrigger] = useState<"manual" | "post_extraction">("manual");
  const [conditionsText, setConditionsText] = useState(
    JSON.stringify(DEFAULT_CONDITIONS, null, 2)
  );
  const [actionsText, setActionsText] = useState(JSON.stringify(DEFAULT_ACTIONS, null, 2));
  const [lastRunSummary, setLastRunSummary] = useState<string | null>(null);

  const activeCount = useMemo(
    () => workflows.filter((item) => item.is_active).length,
    [workflows]
  );

  const parseJson = (rawValue: string) => {
    try {
      const parsed = JSON.parse(rawValue);
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        throw new Error("JSON object expected");
      }
      return parsed;
    } catch {
      throw new Error("JSON invalide");
    }
  };

  const onCreate = async () => {
    try {
      const conditions = parseJson(conditionsText);
      const actions = parseJson(actionsText);
      await createWorkflow.mutateAsync({
        name: name.trim(),
        trigger_event: trigger,
        is_active: true,
        conditions,
        actions,
      });
      toast.success("Workflow cree.");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Creation impossible";
      toast.error(message);
    }
  };

  const onRun = async (dryRun: boolean) => {
    try {
      const response = await runWorkflows.mutateAsync({ dry_run: dryRun });
      setLastRunSummary(
        `Workflows: ${response.total_workflows} | Matched: ${response.total_matched} | Updated: ${response.total_updated}`
      );
      toast.success(dryRun ? "Dry run termine." : "Execution terminee.");
    } catch {
      toast.error("Execution des workflows impossible.");
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Workflows"
        description="Automatisations de segmentation, scoring et normalisation des leads."
        actions={
          <>
            <Button
              variant="outline"
              onClick={() => onRun(true)}
              isLoading={runWorkflows.isPending}
            >
              <TestTube2 className="h-4 w-4" />
              Dry Run
            </Button>
            <Button onClick={() => onRun(false)} isLoading={runWorkflows.isPending}>
              <PlayCircle className="h-4 w-4" />
              Executer
            </Button>
          </>
        }
      />

      {lastRunSummary && (
        <Card>
          <CardContent className="py-4">
            <p className="text-sm text-slate-700">{lastRunSummary}</p>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Workflow className="h-5 w-5 text-primary" />
              Nouveau workflow
            </CardTitle>
            <CardDescription>
              Definis des conditions JSON puis les actions appliquees.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Input
              label="Nom"
              value={name}
              onChange={(event) => setName(event.target.value)}
            />
            <Select
              id="trigger"
              label="Trigger"
              value={trigger}
              onChange={(event) =>
                setTrigger(event.target.value as "manual" | "post_extraction")
              }
              options={[
                { value: "manual", label: "Manual" },
                { value: "post_extraction", label: "Post Extraction" },
              ]}
            />
            <div className="space-y-2">
              <p className="text-sm font-medium text-slate-700">Conditions (JSON)</p>
              <textarea
                className="min-h-32 w-full rounded-md border border-border px-3 py-2 font-mono text-xs focus:outline-none focus:ring-2 focus:ring-primary"
                value={conditionsText}
                onChange={(event) => setConditionsText(event.target.value)}
              />
            </div>
            <div className="space-y-2">
              <p className="text-sm font-medium text-slate-700">Actions (JSON)</p>
              <textarea
                className="min-h-32 w-full rounded-md border border-border px-3 py-2 font-mono text-xs focus:outline-none focus:ring-2 focus:ring-primary"
                value={actionsText}
                onChange={(event) => setActionsText(event.target.value)}
              />
            </div>
            <Button onClick={onCreate} isLoading={createWorkflow.isPending}>
              Creer le workflow
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Workflows existants</CardTitle>
            <CardDescription>{activeCount} actifs</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {workflows.length === 0 && (
              <p className="text-sm text-muted-foreground">Aucun workflow configure.</p>
            )}
            {workflows.map((item) => (
              <div key={item.id} className="rounded-lg border border-border p-3">
                <div className="flex items-center justify-between gap-2">
                  <div>
                    <p className="text-sm font-semibold text-slate-900">{item.name}</p>
                    <p className="text-xs text-slate-500">
                      Trigger: {item.trigger_event} | {item.is_active ? "active" : "inactive"}
                    </p>
                    <p className="mt-1 text-xs text-slate-500">
                      Last run: {item.last_run_at ? new Date(item.last_run_at).toLocaleString() : "-"}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
