"use client";

import Link from "next/link";
import { ArrowLeft, CreditCard, FileBarChart2, Gauge } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { MetricCard } from "@/components/ui/metric-card";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PlanSelector } from "@/components/features/billing/plan-selector";
import { UsageMeter } from "@/components/features/billing/usage-meter";
import { useAuth } from "@/hooks/use-auth";
import {
  useCreateCheckoutSession,
  useCurrentSubscription,
  usePlans,
  useUsage,
} from "@/hooks/use-subscriptions";
import { hasMinimumRole } from "@/lib/authz";
import { formatCurrency } from "@/lib/utils";

export default function BillingPage() {
  const { user } = useAuth();
  const canManageBilling = hasMinimumRole(user?.role, "admin");
  const { data: usage } = useUsage();
  const { data: plans } = usePlans();
  const { data: currentSubscription } = useCurrentSubscription(canManageBilling);
  const createCheckout = useCreateCheckoutSession();

  const currentPlanSlug = currentSubscription?.plan?.slug || "pro";
  const currentPlanPrice = currentSubscription?.plan?.monthly_price_cents || 0;

  const handleSelectPlan = async (planId: string) => {
    if (!canManageBilling) {
      toast.error("Seul un admin peut modifier l'abonnement.");
      return;
    }

    try {
      const origin = window.location.origin;
      const response = await createCheckout.mutateAsync({
        plan_slug: planId,
        success_url: `${origin}/settings/billing`,
        cancel_url: `${origin}/settings/billing`,
      });
      window.location.href = response.checkout_url;
    } catch {
      toast.error("Erreur lors de la creation de la session de paiement.");
    }
  };

  const periodEnd = currentSubscription?.current_period_end
    ? new Date(currentSubscription.current_period_end).toLocaleDateString("fr-FR")
    : "N/A";
  const periodStart = currentSubscription?.current_period_start
    ? new Date(currentSubscription.current_period_start).toLocaleDateString("fr-FR")
    : "N/A";

  return (
    <div className="space-y-6">
      <PageHeader
        title="Facturation"
        description="Pilotage du plan, de la consommation et de la capacite extraction."
        badges={
          <>
            <Badge variant="outline">Plan {currentPlanSlug}</Badge>
            {canManageBilling ? (
              <Badge variant="success">Gestion abonnement active</Badge>
            ) : (
              <Badge variant="secondary">Consultation usage</Badge>
            )}
          </>
        }
        actions={
          <Link href="/settings">
            <Button variant="outline" className="gap-2">
              <ArrowLeft className="h-4 w-4" />
              Retour Parametres
            </Button>
          </Link>
        }
      />

      <div className="grid gap-4 md:grid-cols-3">
        <MetricCard
          label="Plan Actuel"
          value={(currentPlanSlug || "n/a").toUpperCase()}
          helper={currentPlanPrice ? `${formatCurrency(currentPlanPrice / 100)} / mois` : "N/A"}
          icon={<CreditCard className="h-4 w-4" />}
        />
        <MetricCard
          label="Leads Extraits"
          value={usage?.leads_extracted ?? 0}
          helper="Periode active"
          icon={<FileBarChart2 className="h-4 w-4" />}
        />
        <MetricCard
          label="Usage"
          value={`${(usage?.usage_percentage ?? 0).toFixed(1)}%`}
          helper="Charge mensuelle"
          icon={<Gauge className="h-4 w-4" />}
        />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Consommation du mois</CardTitle>
        </CardHeader>
        <CardContent>
          <UsageMeter
            used={usage?.leads_extracted ?? 0}
            limit={usage?.max_leads_per_month ?? 0}
            label="Leads extraits ce mois"
            periodStart={periodStart}
            periodEnd={periodEnd}
          />
        </CardContent>
      </Card>

      <div className="space-y-3">
        <h2 className="text-lg font-semibold text-slate-900">Choisir un plan</h2>
        <p className="text-sm text-muted-foreground">
          {canManageBilling
            ? "Selectionnez un plan pour lancer la session de checkout Stripe."
            : "Vous pouvez consulter les plans, mais seul un admin peut changer l'abonnement."}
        </p>
        <PlanSelector
          currentPlan={currentPlanSlug}
          onSelectPlan={handleSelectPlan}
          plans={plans}
        />
      </div>
    </div>
  );
}
