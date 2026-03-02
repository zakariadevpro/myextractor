import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { Toaster } from "sonner";
import { QueryProvider } from "@/providers/query-provider";
import { AuthProvider } from "@/providers/auth-provider";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-inter",
});

export const metadata: Metadata = {
  title: "Winaity Extractor - Extraction de Leads B2B/B2C",
  description:
    "Plateforme intelligente d'extraction et d'enrichissement de leads B2B/B2C avec garde-fous de consentement.",
  keywords: ["leads", "B2B", "B2C", "extraction", "prospection", "enrichissement"],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="fr" className={inter.variable}>
      <body className="min-h-screen bg-white font-sans antialiased">
        <QueryProvider>
          <AuthProvider>
            {children}
            <Toaster
              position="top-right"
              richColors
              closeButton
              toastOptions={{
                duration: 4000,
              }}
            />
          </AuthProvider>
        </QueryProvider>
      </body>
    </html>
  );
}
