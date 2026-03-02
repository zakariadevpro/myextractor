import type { ReactNode } from "react";

interface PageHeaderProps {
  title: string;
  description: string;
  actions?: ReactNode;
  badges?: ReactNode;
}

export function PageHeader({ title, description, actions, badges }: PageHeaderProps) {
  return (
    <div className="rounded-xl border border-border bg-gradient-to-r from-white via-slate-50 to-primary-50/30 p-5 sm:p-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">{title}</h1>
          <p className="mt-1 text-sm text-muted-foreground">{description}</p>
          {badges ? <div className="mt-3 flex flex-wrap gap-2">{badges}</div> : null}
        </div>
        {actions ? <div className="flex flex-wrap gap-2">{actions}</div> : null}
      </div>
    </div>
  );
}
