import {
  LayoutDashboard,
  ShieldCheck,
  Users,
  Search,
  Settings,
  CreditCard,
  Shield,
  KeyRound,
  Workflow,
  Gauge,
  UserCog,
  type LucideIcon,
} from "lucide-react";
import type { UserRole } from "@/types/user";

export const APP_NAME = "Winaity Extractor";

export const APP_DESCRIPTION =
  "Plateforme d'extraction de leads B2B/B2C intelligente";

export interface NavChild {
  label: string;
  href: string;
  icon?: LucideIcon;
  minRole?: UserRole;
}

export interface NavItem {
  label: string;
  href: string;
  icon: LucideIcon;
  minRole?: UserRole;
  section: "pilotage" | "operations" | "administration";
  children?: NavChild[];
}

export const NAV_ITEMS: NavItem[] = [
  {
    label: "Dashboard",
    href: "/dashboard",
    icon: LayoutDashboard,
    section: "pilotage",
  },
  {
    label: "Leads",
    href: "/leads",
    icon: Users,
    section: "operations",
  },
  {
    label: "Extraction",
    href: "/extraction",
    icon: Search,
    minRole: "manager",
    section: "operations",
  },
  {
    label: "Audit",
    href: "/audit",
    icon: ShieldCheck,
    minRole: "manager",
    section: "pilotage",
  },
  {
    label: "Parametres",
    href: "/settings",
    icon: Settings,
    section: "administration",
    children: [
      { label: "Facturation", href: "/settings/billing", icon: CreditCard, minRole: "admin" },
      { label: "Equipe", href: "/settings/team", icon: UserCog, minRole: "admin" },
      { label: "Permissions", href: "/settings/permissions-matrix", icon: Shield, minRole: "admin" },
      { label: "Cles API", href: "/settings/api-keys", icon: KeyRound, minRole: "admin" },
      { label: "Workflows", href: "/settings/workflows", icon: Workflow, minRole: "admin" },
      { label: "Scoring", href: "/settings/scoring", icon: Gauge, minRole: "admin" },
    ],
  },
];

export interface PlanTier {
  id: string;
  name: string;
  price: number;
  leadsPerMonth: number;
  features: string[];
  popular?: boolean;
}

export const PLAN_TIERS: PlanTier[] = [
  {
    id: "starter",
    name: "Starter",
    price: 29,
    leadsPerMonth: 500,
    features: [
      "500 leads par mois",
      "Export CSV",
      "Filtres de base",
      "Support email",
    ],
  },
  {
    id: "pro",
    name: "Pro",
    price: 79,
    leadsPerMonth: 2000,
    popular: true,
    features: [
      "2 000 leads par mois",
      "Export CSV & Excel",
      "Filtres avances",
      "Enrichissement email",
      "Support prioritaire",
      "API access",
    ],
  },
  {
    id: "enterprise",
    name: "Enterprise",
    price: 199,
    leadsPerMonth: 10000,
    features: [
      "10 000 leads par mois",
      "Tous les exports",
      "Filtres illimites",
      "Enrichissement complet",
      "Support dedie",
      "API illimitee",
      "Equipe multi-utilisateurs",
      "Webhooks",
    ],
  },
];

export interface SourceOption {
  value: string;
  label: string;
  description: string;
}

export const SOURCES: SourceOption[] = [
  {
    value: "whiteextractor",
    label: "WhiteExtractor Mode",
    description:
      "Fusion multi-sources (Sirene + Pages Jaunes + Google Maps) avec dedoublonnage intelligent",
  },
  {
    value: "google_maps",
    label: "Google Maps",
    description: "Scraping Google Maps (adresses, tel, sites web)",
  },
  {
    value: "pages_jaunes",
    label: "Pages Jaunes",
    description: "Annuaire Pages Jaunes (entreprises francaises)",
  },
  {
    value: "sirene_api",
    label: "Sirene (INSEE)",
    description: "Registre officiel des entreprises (SIREN, NAF, adresses)",
  },
];

export const SECTORS = [
  "Technologie",
  "Finance",
  "Sante",
  "Education",
  "Commerce",
  "Industrie",
  "Services",
  "Immobilier",
  "Transport",
  "Energie",
  "Alimentation",
  "Tourisme",
  "Media",
  "Autre",
];
