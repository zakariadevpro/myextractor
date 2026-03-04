"use client";

import { useState } from "react";
import { usePathname } from "next/navigation";
import Link from "next/link";
import { Menu, ChevronRight, User, LogOut, Settings } from "lucide-react";
import { useAuth } from "@/hooks/use-auth";
import { getInitials } from "@/lib/utils";

interface TopbarProps {
  onMenuClick: () => void;
}

export function Topbar({ onMenuClick }: TopbarProps) {
  const { user, logout } = useAuth();
  const pathname = usePathname();
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const breadcrumbLabels: Record<string, string> = {
    dashboard: "Dashboard",
    leads: "Leads",
    extraction: "Extraction",
    settings: "Parametres",
    team: "Equipe",
    "permissions-matrix": "Matrice Permissions",
    billing: "Facturation",
    audit: "Audit",
  };

  // Generate breadcrumbs from pathname
  const segments = pathname.split("/").filter(Boolean);
  const breadcrumbs = segments.map((segment, index) => {
    const href = "/" + segments.slice(0, index + 1).join("/");
    const label =
      breadcrumbLabels[segment] || segment.charAt(0).toUpperCase() + segment.slice(1);
    return { label, href };
  });

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-border bg-white px-4 sm:px-6">
      {/* Left: Menu + Breadcrumbs */}
      <div className="flex items-center gap-4">
        <button
          onClick={onMenuClick}
          className="rounded-md p-2 text-slate-400 hover:bg-slate-50 hover:text-slate-600 lg:hidden"
        >
          <Menu className="h-5 w-5" />
        </button>

        <nav className="hidden items-center gap-1 text-sm sm:flex">
          {breadcrumbs.map((crumb, index) => (
            <div key={crumb.href} className="flex items-center gap-1">
              {index > 0 && (
                <ChevronRight className="h-4 w-4 text-slate-300" />
              )}
              {index === breadcrumbs.length - 1 ? (
                <span className="font-medium text-slate-900">
                  {crumb.label}
                </span>
              ) : (
                <Link
                  href={crumb.href}
                  className="text-slate-500 hover:text-slate-700"
                >
                  {crumb.label}
                </Link>
              )}
            </div>
          ))}
        </nav>
      </div>

      {/* Right: User Menu */}
      <div className="relative">
        <button
          onClick={() => setDropdownOpen(!dropdownOpen)}
          className="flex items-center gap-3 rounded-lg px-3 py-2 hover:bg-slate-50 transition-colors"
        >
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-xs font-semibold text-white">
            {user ? getInitials(user.first_name && user.last_name ? `${user.first_name} ${user.last_name}` : user.email) : "U"}
          </div>
          <span className="hidden text-sm font-medium text-slate-700 sm:inline">
            {user ? `${user.first_name || ""} ${user.last_name || ""}`.trim() || "Utilisateur" : "Utilisateur"}
          </span>
        </button>

        {/* Dropdown */}
        {dropdownOpen && (
          <>
            <div
              className="fixed inset-0 z-40"
              onClick={() => setDropdownOpen(false)}
            />
            <div className="absolute right-0 z-50 mt-2 w-56 rounded-lg border border-border bg-white py-1 shadow-lg">
              <div className="border-b border-border px-4 py-3">
                <p className="text-sm font-medium text-slate-900">
                  {user ? `${user.first_name || ""} ${user.last_name || ""}`.trim() : ""}
                </p>
                <p className="text-xs text-slate-500">{user?.email}</p>
              </div>
              <Link
                href="/settings"
                onClick={() => setDropdownOpen(false)}
                className="flex items-center gap-2 px-4 py-2 text-sm text-slate-600 hover:bg-slate-50"
              >
                <Settings className="h-4 w-4" />
                Parametres
              </Link>
              <Link
                href="/settings/team"
                onClick={() => setDropdownOpen(false)}
                className="flex items-center gap-2 px-4 py-2 text-sm text-slate-600 hover:bg-slate-50"
              >
                <User className="h-4 w-4" />
                Profil
              </Link>
              <div className="border-t border-border">
                <button
                  onClick={() => {
                    setDropdownOpen(false);
                    logout();
                  }}
                  className="flex w-full items-center gap-2 px-4 py-2 text-sm text-danger hover:bg-slate-50"
                >
                  <LogOut className="h-4 w-4" />
                  Deconnexion
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </header>
  );
}
