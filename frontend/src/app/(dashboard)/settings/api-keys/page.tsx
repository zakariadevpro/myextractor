"use client";

import { useMemo, useState } from "react";
import { toast } from "sonner";
import { KeyRound, ShieldCheck } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useApiKeys, useCreateApiKey, useRevokeApiKey } from "@/hooks/use-api-keys";

const AVAILABLE_SCOPES = [
  "leads:read",
  "leads:export",
  "extractions:run",
  "workflows:run",
  "scoring:read",
];

export default function ApiKeysPage() {
  const { data: apiKeys = [] } = useApiKeys();
  const createApiKey = useCreateApiKey();
  const revokeApiKey = useRevokeApiKey();

  const [name, setName] = useState("Public API Key");
  const [scopes, setScopes] = useState<string[]>(["leads:read"]);
  const [expiresAt, setExpiresAt] = useState("");
  const [newApiKey, setNewApiKey] = useState<string | null>(null);

  const activeCount = useMemo(
    () => apiKeys.filter((item) => item.is_active).length,
    [apiKeys]
  );

  const toggleScope = (scope: string) => {
    setScopes((prev) =>
      prev.includes(scope) ? prev.filter((value) => value !== scope) : [...prev, scope]
    );
  };

  const onCreate = async () => {
    if (!name.trim()) {
      toast.error("Le nom de la cle est obligatoire.");
      return;
    }
    if (scopes.length === 0) {
      toast.error("Selectionne au moins un scope.");
      return;
    }

    try {
      const response = await createApiKey.mutateAsync({
        name: name.trim(),
        scopes,
        expires_at: expiresAt ? new Date(expiresAt).toISOString() : null,
      });
      setNewApiKey(response.api_key);
      toast.success("Cle API creee. Copie la valeur maintenant.");
    } catch {
      toast.error("Impossible de creer la cle API.");
    }
  };

  const onRevoke = async (id: string) => {
    try {
      await revokeApiKey.mutateAsync(id);
      toast.success("Cle revoquee.");
    } catch {
      toast.error("Impossible de revoquer la cle.");
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="API Keys"
        description="Gestion des acces API publics pour integrations externes."
      />

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <KeyRound className="h-5 w-5 text-primary" />
              Nouvelle cle
            </CardTitle>
            <CardDescription>
              La cle secrete n&apos;est affichee qu&apos;une seule fois.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Input
              label="Nom de la cle"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Public API Key"
            />
            <Input
              label="Expiration (optionnel)"
              type="datetime-local"
              value={expiresAt}
              onChange={(event) => setExpiresAt(event.target.value)}
            />
            <div className="space-y-2">
              <p className="text-sm font-medium text-slate-700">Scopes</p>
              <div className="grid gap-2 sm:grid-cols-2">
                {AVAILABLE_SCOPES.map((scope) => (
                  <label
                    key={scope}
                    className="flex items-center gap-2 rounded-md border border-border px-3 py-2 text-sm"
                  >
                    <input
                      type="checkbox"
                      checked={scopes.includes(scope)}
                      onChange={() => toggleScope(scope)}
                    />
                    <span>{scope}</span>
                  </label>
                ))}
              </div>
            </div>
            <Button onClick={onCreate} isLoading={createApiKey.isPending}>
              Creer la cle
            </Button>
            {newApiKey && (
              <div className="rounded-md border border-amber-300 bg-amber-50 p-3">
                <p className="text-xs font-semibold uppercase text-amber-700">
                  Copie maintenant cette cle
                </p>
                <p className="mt-2 break-all font-mono text-xs text-amber-900">{newApiKey}</p>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ShieldCheck className="h-5 w-5 text-primary" />
              Cles existantes
            </CardTitle>
            <CardDescription>{activeCount} cles actives</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {apiKeys.length === 0 && (
              <p className="text-sm text-muted-foreground">Aucune cle API pour le moment.</p>
            )}
            {apiKeys.map((item) => (
              <div
                key={item.id}
                className="rounded-lg border border-border p-3"
              >
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <p className="text-sm font-semibold text-slate-900">{item.name}</p>
                    <p className="font-mono text-xs text-slate-500">{item.key_prefix}...</p>
                    <p className="mt-1 text-xs text-slate-500">
                      Scopes: {item.scopes.join(", ")}
                    </p>
                  </div>
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={() => onRevoke(item.id)}
                    disabled={!item.is_active || revokeApiKey.isPending}
                  >
                    {item.is_active ? "Revoquer" : "Revoquee"}
                  </Button>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
