import DashboardLayoutClient from "./dashboard-layout-client";

export const dynamic = "force-dynamic";
export const revalidate = 0;

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <DashboardLayoutClient>{children}</DashboardLayoutClient>;
}
