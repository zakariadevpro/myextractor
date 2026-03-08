import Link from "next/link";
import { ArrowRight, Search, BarChart3, Mail, Zap } from "lucide-react";

export default function HomePage() {
  return (
    <div className="min-h-screen bg-white">
      {/* Header */}
      <header className="border-b border-border">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary">
              <Zap className="h-5 w-5 text-white" />
            </div>
            <span className="text-xl font-bold text-slate-900">
              Winaity Extractor
            </span>
          </div>
          <nav className="flex items-center gap-4">
            <Link
              href="/login"
              className="text-sm font-medium text-slate-600 hover:text-primary transition-colors"
            >
              Connexion
            </Link>
            <Link
              href="/register"
              className="inline-flex h-9 items-center rounded-md bg-primary px-4 text-sm font-medium text-white shadow-sm hover:bg-primary-700 transition-colors"
            >
              Commencer gratuitement
            </Link>
          </nav>
        </div>
      </header>

      {/* Hero */}
      <section className="relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-primary-50 to-white" />
        <div className="relative mx-auto max-w-7xl px-4 py-24 sm:px-6 sm:py-32 lg:px-8">
          <div className="mx-auto max-w-3xl text-center">
            <h1 className="text-4xl font-bold tracking-tight text-slate-900 sm:text-5xl lg:text-6xl">
              Plateforme d&apos;extraction de leads{" "}
              <span className="text-primary">B2B/B2C</span>
            </h1>
            <p className="mt-6 text-lg leading-8 text-slate-600 sm:text-xl">
              Trouvez et enrichissez vos prospects ideaux en quelques clics.
              Extraction intelligente B2B et ingestion B2C consentie pour
              accelerer votre prospection commerciale.
            </p>
            <div className="mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row">
              <Link
                href="/register"
                className="inline-flex h-12 items-center gap-2 rounded-lg bg-primary px-8 text-base font-semibold text-white shadow-lg shadow-primary/25 hover:bg-primary-700 transition-all hover:shadow-xl"
              >
                Demarrer maintenant
                <ArrowRight className="h-5 w-5" />
              </Link>
              <Link
                href="/login"
                className="inline-flex h-12 items-center gap-2 rounded-lg border border-border bg-white px-8 text-base font-semibold text-slate-700 hover:bg-slate-50 transition-colors"
              >
                Se connecter
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="border-t border-border py-24">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="mx-auto max-w-2xl text-center">
            <h2 className="text-3xl font-bold tracking-tight text-slate-900">
              Tout ce dont vous avez besoin pour prospecter efficacement
            </h2>
            <p className="mt-4 text-lg text-slate-600">
              Des outils puissants pour identifier, qualifier et contacter vos
              futurs clients.
            </p>
          </div>
          <div className="mt-16 grid gap-8 sm:grid-cols-2 lg:grid-cols-3">
            {/* Feature 1 */}
            <div className="rounded-xl border border-border p-8 transition-shadow hover:shadow-md">
              <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-primary-100">
                <Search className="h-6 w-6 text-primary" />
              </div>
              <h3 className="mt-4 text-lg font-semibold text-slate-900">
                Extraction intelligente
              </h3>
              <p className="mt-2 text-sm text-slate-600">
                Recherchez des entreprises par mots-cles, secteur d&apos;activite
                et zone geographique. Extraction automatisee et rapide.
              </p>
            </div>

            {/* Feature 2 */}
            <div className="rounded-xl border border-border p-8 transition-shadow hover:shadow-md">
              <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-green-100">
                <Mail className="h-6 w-6 text-green-600" />
              </div>
              <h3 className="mt-4 text-lg font-semibold text-slate-900">
                Enrichissement email
              </h3>
              <p className="mt-2 text-sm text-slate-600">
                Validation et enrichissement automatique des adresses email
                professionnelles. Taux de delivrabilite optimise.
              </p>
            </div>

            {/* Feature 3 */}
            <div className="rounded-xl border border-border p-8 transition-shadow hover:shadow-md">
              <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-purple-100">
                <BarChart3 className="h-6 w-6 text-purple-600" />
              </div>
              <h3 className="mt-4 text-lg font-semibold text-slate-900">
                Scoring automatique
              </h3>
              <p className="mt-2 text-sm text-slate-600">
                Chaque lead recoit un score de qualite. Concentrez-vous sur les
                prospects les plus prometteurs pour maximiser vos conversions.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-border bg-slate-50">
        <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
          <div className="flex flex-col items-center justify-between gap-4 sm:flex-row">
            <div className="flex items-center gap-2">
              <div className="flex h-6 w-6 items-center justify-center rounded bg-primary">
                <Zap className="h-4 w-4 text-white" />
              </div>
              <span className="text-sm font-semibold text-slate-900">
                Winaity Extractor
              </span>
            </div>
            <p className="text-sm text-slate-500">
              &copy; {new Date().getFullYear()} Winaity. Tous droits reserves.
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}
