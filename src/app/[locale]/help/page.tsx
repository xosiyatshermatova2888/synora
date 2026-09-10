import { setRequestLocale, getTranslations } from "next-intl/server";
import { notFound } from "next/navigation";
import { routing } from "@/i18n/routing";
import CTAProvider from "@/components/CTAProvider";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import MarketingHeader from "@/components/MarketingHeader";
import HelpContent from "@/components/HelpContent";
import FAQ from "@/components/FAQ";
import TrialCTA from "@/components/TrialCTA";
import FinalCTA from "@/components/FinalCTA";
import { pageMetadata } from "@/lib/metadata";

export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  return pageMetadata(locale, "help");
}

export default async function HelpPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  if (!routing.locales.includes(locale as (typeof routing.locales)[number])) {
    notFound();
  }
  setRequestLocale(locale);
  const h = await getTranslations({ locale, namespace: "landing.help" });

  return (
    <CTAProvider>
      <Navbar />
      <main>
        <MarketingHeader eyebrow={h("eyebrow")} title={h("title")} subtitle={h("subtitle")} />
        <HelpContent locale={locale} />
        <FAQ />
        <TrialCTA />
        <FinalCTA />
      </main>
      <Footer />
    </CTAProvider>
  );
}