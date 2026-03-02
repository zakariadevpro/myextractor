"use client";

import { Users, BarChart3, Mail, Activity } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { useDashboardOverview } from "@/hooks/use-dashboard";
import { formatNumber, formatPercentage } from "@/lib/utils";

interface StatCard {
  title: string;
  value: string;
  icon: React.ReactNode;
  description: string;
  color: string;
  bgColor: string;
}

export function StatsCards() {
  const { data: overview } = useDashboardOverview();

  const stats: StatCard[] = [
    {
      title: "Leads Aujourd'hui",
      value: formatNumber(overview?.leads_today ?? 0),
      icon: <Users className="h-5 w-5" />,
      description: `${formatNumber(overview?.leads_total ?? 0)} total`,
      color: "text-primary",
      bgColor: "bg-primary-50",
    },
    {
      title: "Score Moyen",
      value: formatNumber(overview?.avg_score ?? 0),
      icon: <BarChart3 className="h-5 w-5" />,
      description: "Sur 100 points",
      color: "text-warning",
      bgColor: "bg-warning-light",
    },
    {
      title: "Taux Emails Valides",
      value: formatPercentage(overview?.email_valid_rate ?? 0),
      icon: <Mail className="h-5 w-5" />,
      description: "Emails verifies",
      color: "text-green-600",
      bgColor: "bg-green-50",
    },
    {
      title: "Extractions Actives",
      value: formatNumber(overview?.active_extractions ?? 0),
      icon: <Activity className="h-5 w-5" />,
      description: "En cours d'execution",
      color: "text-orange-600",
      bgColor: "bg-orange-50",
    },
  ];

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {stats.map((stat) => (
        <Card key={stat.title} className="card-hover">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-muted-foreground">
                  {stat.title}
                </p>
                <p className="mt-2 text-3xl font-bold text-slate-900">
                  {stat.value}
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {stat.description}
                </p>
              </div>
              <div
                className={`flex h-12 w-12 items-center justify-center rounded-lg ${stat.bgColor} ${stat.color}`}
              >
                {stat.icon}
              </div>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
