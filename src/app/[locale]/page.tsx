import { setRequestLocale, getTranslations } from "next-intl/server";
import { notFound } from "next/navigation";
import { routing } from "@/i18n/routing";
import CTAProvider from "@/components/CTAProvider";
import Navbar from "@/components/Navbar";
import Hero from "@/components/Hero";
import TrustSection from "@/components/TrustSection";
import ProblemsSection from "@/components/ProblemsSection";
import SolutionFlow from "@/components/SolutionFlow";
import FeaturesSection from "@/components/FeaturesSection";
import HowItWorks from "@/components/HowItWorks";
import AISection from "@/components/AISection";
import AIDemo from "@/components/AIDemo";
import MultiBranch from "@/components/MultiBranch";
import Integrations from "@/components/Integrations";
import PricingSection from "@/components/PricingSection";
import TrialCTA from "@/components/TrialCTA";
import FAQ from "@/components/FAQ";
import FinalCTA from "@/components/FinalCTA";
import Footer from "@/components/Footer";

export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "metadata" });

  return {
    title: t("title"),
    description: t("description"),
  };
}

export default async function HomePage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  if (!routing.locales.includes(locale as (typeof routing.locales)[number])) {
    notFound();
  }
  setRequestLocale(locale);

  return (
    <CTAProvider>
      <Navbar />
      <main>
        <Hero />
        <TrustSection />
        <ProblemsSection />
        <SolutionFlow />
        <FeaturesSection />
        <HowItWorks />
        <AISection />
        <AIDemo />
        <MultiBranch />
        <Integrations />
        <PricingSection />
        <TrialCTA />
        <FAQ />
        <FinalCTA />
      </main>
      <Footer />
    </CTAProvider>
  );
}
