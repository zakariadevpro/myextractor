"use client";

import { Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { PLAN_TIERS } from "@/lib/constants";
import type { Plan as ApiPlan } from "@/types/subscription";
import { formatCurrency } from "@/lib/utils";
import { cn } from "@/lib/utils";

interface PlanSelectorProps {
  currentPlan?: string;
  onSelectPlan?: (planId: string) => void;
  plans?: ApiPlan[];
}

interface DisplayPlan {
  id: string;
  name: string;
  price: number;
  leadsPerMonth: number;
  features: string[];
  popular?: boolean;
}

function toDisplayPlan(plan: ApiPlan): DisplayPlan {
  return {
    id: plan.slug,
    name: plan.name,
    price: plan.monthly_price_cents / 100,
    leadsPerMonth: plan.max_leads_per_month,
    features: [
      `${plan.max_leads_per_month.toLocaleString("fr-FR")} leads par mois`,
      `${plan.max_users} utilisateurs`,
      `${plan.max_extractions_per_day} extractions / jour`,
    ],
    popular: plan.slug === "pro",
  };
}

export function PlanSelector({
  currentPlan = "pro",
  onSelectPlan,
  plans,
}: PlanSelectorProps) {
  const plansToShow: DisplayPlan[] = plans?.length
    ? plans.map(toDisplayPlan)
    : (PLAN_TIERS as DisplayPlan[]);

  return (
    <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
      {plansToShow.map((plan: DisplayPlan) => {
        const isCurrent = currentPlan === plan.id;
        return (
          <Card
            key={plan.id}
            className={cn(
              "relative",
              plan.popular && "border-primary shadow-md",
              isCurrent && "ring-2 ring-primary"
            )}
          >
            {plan.popular && (
              <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                <Badge className="bg-primary text-white">Populaire</Badge>
              </div>
            )}
            <CardHeader className="text-center">
              <CardTitle className="text-lg">{plan.name}</CardTitle>
              <div className="mt-2">
                <span className="text-4xl font-bold text-slate-900">
                  {formatCurrency(plan.price)}
                </span>
                <span className="text-sm text-muted-foreground"> / mois</span>
              </div>
              <p className="mt-1 text-sm text-muted-foreground">
                {plan.leadsPerMonth.toLocaleString("fr-FR")} leads par mois
              </p>
            </CardHeader>
            <CardContent>
              <ul className="space-y-3">
                {plan.features.map((feature) => (
                  <li key={feature} className="flex items-start gap-2">
                    <Check className="mt-0.5 h-4 w-4 flex-shrink-0 text-success" />
                    <span className="text-sm text-slate-600">{feature}</span>
                  </li>
                ))}
              </ul>
              <div className="mt-6">
                {isCurrent ? (
                  <Button variant="outline" className="w-full" disabled>
                    Plan actuel
                  </Button>
                ) : (
                  <Button
                    variant={plan.popular ? "default" : "outline"}
                    className="w-full"
                    onClick={() => onSelectPlan?.(plan.id)}
                  >
                    Choisir ce plan
                  </Button>
                )}
              </div>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
