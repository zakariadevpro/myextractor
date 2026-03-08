"use client";

import { Badge } from "@/components/ui/badge";
import { PageHeader } from "@/components/layout/page-header";
import { useAuth } from "@/hooks/use-auth";
import { StatsCards } from "@/components/features/dashboard/stats-cards";
import { B2CCompliancePanel } from "@/components/features/dashboard/b2c-compliance-panel";
import { DataQualityPanel } from "@/components/features/dashboard/data-quality-panel";
import { LeadIntelligencePanel } from "@/components/features/dashboard/lead-intelligence-panel";
import { RoleActionsPanel } from "@/components/features/dashboard/role-actions-panel";
import {
  LeadsBySectorChart,
  LeadsByZoneChart,
} from "@/components/features/dashboard/leads-chart";

export default function DashboardPage() {
  const { user } = useAuth();

  return (
    <div className="space-y-8">
      <PageHeader
        title="Dashboard"
        description="Vue d'ensemble operationnelle de ton CRM d'extraction."
        badges={
          <>
            <Badge variant="outline">Organisation {user?.organization_name || "N/A"}</Badge>
            <Badge variant="success">Role {user?.role || "user"}</Badge>
          </>
        }
      />

      <StatsCards />
      <LeadIntelligencePanel />
      <B2CCompliancePanel />

      <div className="grid gap-6 xl:grid-cols-5">
        <div className="xl:col-span-3">
          <DataQualityPanel />
        </div>
        <div className="xl:col-span-2">
          <RoleActionsPanel />
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <LeadsBySectorChart />
        <LeadsByZoneChart />
      </div>
    </div>
  );
}
