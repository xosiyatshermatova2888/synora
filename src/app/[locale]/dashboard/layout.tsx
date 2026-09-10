import { setRequestLocale } from "next-intl/server";
import { notFound } from "next/navigation";
import { AuthProvider } from "@/lib/auth-context";
import DashboardGuard from "@/components/dashboard/DashboardGuard";
import { routing } from "@/i18n/routing";

export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }));
}

export default async function DashboardLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  if (!routing.locales.includes(locale as (typeof routing.locales)[number])) {
    notFound();
  }
  setRequestLocale(locale);

  return (
    <AuthProvider>
      <DashboardGuard>{children}</DashboardGuard>
    </AuthProvider>
  );
}