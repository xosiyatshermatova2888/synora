import type { Metadata, Viewport } from "next";
import { setRequestLocale } from "next-intl/server";
import { notFound } from "next/navigation";
import { AuthProvider } from "@/lib/auth-context";
import AuthGuard from "@/components/AuthGuard";
import { routing } from "@/i18n/routing";

export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }));
}

// PWA install metadata — separate from the root manifest (see
// waiter/manifest.ts) so "Add to Home Screen" here installs a standalone
// waiter app, not the marketing site. apple-mobile-web-app-* covers iOS
// Safari, which ignores the Web Manifest's own display/icons fields.
export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}): Promise<Metadata> {
  const { locale } = await params;
  return {
    manifest: `/${locale}/waiter/manifest.webmanifest`,
    appleWebApp: {
      capable: true,
      statusBarStyle: "black-translucent",
      title: "Ofitsiant",
    },
    icons: {
      apple: "/waiter/apple-touch-icon.png",
    },
  };
}

export const viewport: Viewport = {
  themeColor: "#5b46e8",
  colorScheme: "light",
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
};

export default async function WaiterLayout({
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
      <AuthGuard>{children}</AuthGuard>
    </AuthProvider>
  );
}
