import { NextResponse } from "next/server";
import { routing } from "@/i18n/routing";

// A dedicated manifest for /waiter (separate from the root site manifest at
// /manifest.webmanifest, which installs the marketing homepage) — so "Add to
// Home Screen" here installs a standalone app that opens straight into the
// ordering flow, under its own name/icon, not "SYNORA" the marketing site.
//
// Implemented as a plain Route Handler rather than the app/manifest.ts file
// convention: Next.js only wires that convention up at the true app/ root,
// not when colocated inside a dynamic segment like [locale]/waiter/ — it
// 404s there. A route.ts always works, at any path.
const COPY: Record<string, { name: string; short_name: string; description: string }> = {
  uz: {
    name: "SYNORA Ofitsiant",
    short_name: "Ofitsiant",
    description: "Ofitsiantlar uchun tezkor buyurtma qabul qilish ilovasi",
  },
  ru: {
    name: "SYNORA Официант",
    short_name: "Официант",
    description: "Приложение для официантов для быстрого приёма заказов",
  },
  en: {
    name: "SYNORA Waiter",
    short_name: "Waiter",
    description: "Fast order-taking app for waiters",
  },
};

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ locale: string }> }
) {
  const { locale: rawLocale } = await params;
  const locale = routing.locales.includes(
    rawLocale as (typeof routing.locales)[number]
  )
    ? rawLocale
    : routing.defaultLocale;
  const copy = COPY[locale] ?? COPY[routing.defaultLocale];

  return NextResponse.json(
    {
      name: copy.name,
      short_name: copy.short_name,
      description: copy.description,
      start_url: `/${locale}/waiter`,
      scope: `/${locale}/waiter`,
      display: "standalone",
      orientation: "portrait",
      background_color: "#f6f7fa",
      theme_color: "#5b46e8",
      icons: [
        { src: "/waiter/icon-192.png", sizes: "192x192", type: "image/png" },
        { src: "/waiter/icon-512.png", sizes: "512x512", type: "image/png" },
      ],
    },
    { headers: { "Content-Type": "application/manifest+json" } }
  );
}
