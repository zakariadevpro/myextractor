"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Zap, X } from "lucide-react";
import { useAuth } from "@/hooks/use-auth";
import { useUsage } from "@/hooks/use-subscriptions";
import { hasMinimumRole } from "@/lib/authz";
import { cn } from "@/lib/utils";
import { APP_NAME, NAV_ITEMS } from "@/lib/constants";

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

export function Sidebar({ isOpen, onClose }: SidebarProps) {
  const pathname = usePathname();
  const { user } = useAuth();
  const { data: usage } = useUsage();
  const allowedNavItems = NAV_ITEMS.filter(
    (item) => !item.minRole || hasMinimumRole(user?.role, item.minRole)
  );
  const usedLeads = usage?.leads_extracted ?? 0;
  const maxLeads = usage?.max_leads_per_month ?? 0;
  const usagePercent = maxLeads > 0 ? Math.min(100, (usedLeads / maxLeads) * 100) : 0;
  const sectionLabels: Record<string, string> = {
    pilotage: "Pilotage",
    operations: "Operations",
    administration: "Administration",
  };
  const sections = ["pilotage", "operations", "administration"] as const;

  return (
    <>
      {/* Mobile overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 lg:hidden"
          onClick={onClose}
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex w-64 flex-col border-r border-border bg-white transition-transform duration-300 lg:static lg:translate-x-0",
          isOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        {/* Logo */}
        <div className="flex h-16 items-center justify-between border-b border-border px-6">
          <Link href="/dashboard" className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary">
              <Zap className="h-5 w-5 text-white" />
            </div>
            <span className="text-lg font-bold text-slate-900">{APP_NAME}</span>
          </Link>
          <button
            onClick={onClose}
            className="rounded-md p-1 text-slate-400 hover:text-slate-600 lg:hidden"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 space-y-4 px-3 py-4">
          {sections.map((section) => {
            const items = allowedNavItems.filter((item) => item.section === section);
            if (!items.length) return null;

            return (
              <div key={section} className="space-y-1">
                <p className="px-3 pb-1 text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                  {sectionLabels[section]}
                </p>
                {items.map((item) => {
                  const isActive =
                    pathname === item.href ||
                    (item.href !== "/dashboard" && pathname.startsWith(item.href));
                  const Icon = item.icon;

                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      onClick={onClose}
                      className={cn(
                        "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                        isActive
                          ? "bg-primary-50 text-primary-700"
                          : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                      )}
                    >
                      <Icon
                        className={cn(
                          "h-5 w-5 flex-shrink-0",
                          isActive ? "text-primary" : "text-slate-400"
                        )}
                      />
                      {item.label}
                    </Link>
                  );
                })}
              </div>
            );
          })}
        </nav>

        {/* Footer */}
        <div className="border-t border-border p-4">
          <div className="rounded-lg bg-primary-50 px-4 py-3">
            <p className="text-xs font-medium text-primary-700">Usage mensuel</p>
            <p className="mt-1 text-xs text-primary-600">
              {usedLeads.toLocaleString("fr-FR")} / {maxLeads.toLocaleString("fr-FR")} leads utilises
            </p>
            <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-primary-200">
              <div
                className="h-full rounded-full bg-primary"
                style={{ width: `${usagePercent}%` }}
              />
            </div>
          </div>
        </div>
      </aside>
    </>
  );
}
