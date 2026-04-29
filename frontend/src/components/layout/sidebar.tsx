"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { Zap, X, ChevronRight } from "lucide-react";
import { useAuth } from "@/hooks/use-auth";
import { useUsage } from "@/hooks/use-subscriptions";
import { hasMinimumRole } from "@/lib/authz";
import { cn } from "@/lib/utils";
import { APP_NAME, NAV_ITEMS, type NavItem } from "@/lib/constants";
import type { UserRole } from "@/types/user";

function NavRow({
  item,
  pathname,
  userRole,
  onNavigate,
}: {
  item: NavItem;
  pathname: string;
  userRole?: UserRole;
  onNavigate: () => void;
}) {
  const isActive =
    pathname === item.href ||
    (item.href !== "/dashboard" && pathname.startsWith(item.href));
  const Icon = item.icon;
  const allowedChildren = (item.children ?? []).filter(
    (child) => !child.minRole || hasMinimumRole(userRole, child.minRole),
  );
  const hasChildren = allowedChildren.length > 0;
  const [open, setOpen] = useState<boolean>(isActive && hasChildren);

  useEffect(() => {
    if (isActive && hasChildren) setOpen(true);
  }, [isActive, hasChildren]);

  return (
    <div>
      <div
        className={cn(
          "flex items-center gap-1 rounded-lg pr-1 transition-colors",
          isActive
            ? "bg-primary-50 text-primary-700"
            : "text-slate-600 hover:bg-slate-50 hover:text-slate-900",
        )}
      >
        <Link
          href={item.href}
          onClick={onNavigate}
          className="flex flex-1 items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium"
        >
          <Icon
            className={cn(
              "h-5 w-5 flex-shrink-0",
              isActive ? "text-primary" : "text-slate-400",
            )}
          />
          {item.label}
        </Link>
        {hasChildren && (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              setOpen((prev) => !prev);
            }}
            aria-expanded={open}
            aria-label={`${open ? "Masquer" : "Afficher"} les sous-pages de ${item.label}`}
            className="rounded-md p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
          >
            <ChevronRight
              className={cn(
                "h-4 w-4 transition-transform",
                open && "rotate-90",
              )}
            />
          </button>
        )}
      </div>

      {hasChildren && open && (
        <div className="ml-7 mt-1 space-y-0.5 border-l border-border pl-2">
          {allowedChildren.map((child) => {
            const ChildIcon = child.icon;
            const childActive = pathname === child.href;
            return (
              <Link
                key={child.href}
                href={child.href}
                onClick={onNavigate}
                className={cn(
                  "flex items-center gap-2 rounded-md px-2 py-1.5 text-xs font-medium transition-colors",
                  childActive
                    ? "bg-primary-50 text-primary-700"
                    : "text-slate-500 hover:bg-slate-50 hover:text-slate-900",
                )}
              >
                {ChildIcon && (
                  <ChildIcon
                    className={cn(
                      "h-3.5 w-3.5 flex-shrink-0",
                      childActive ? "text-primary" : "text-slate-400",
                    )}
                  />
                )}
                {child.label}
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}

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
                {items.map((item) => (
                  <NavRow
                    key={item.href}
                    item={item}
                    pathname={pathname}
                    userRole={user?.role}
                    onNavigate={onClose}
                  />
                ))}
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
