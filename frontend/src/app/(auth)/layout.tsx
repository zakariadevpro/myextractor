import Link from "next/link";
import { Zap } from "lucide-react";

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-slate-50 px-4">
      <div className="mb-8 flex items-center gap-2">
        <Link href="/" className="flex items-center gap-2">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary">
            <Zap className="h-6 w-6 text-white" />
          </div>
          <span className="text-2xl font-bold text-slate-900">
            Winaity Extractor
          </span>
        </Link>
      </div>
      <div className="w-full max-w-md">{children}</div>
      <p className="mt-8 text-sm text-slate-500">
        &copy; {new Date().getFullYear()} Winaity. Tous droits reserves.
      </p>
    </div>
  );
}
