import { getTranslations, setRequestLocale } from "next-intl/server";
import { notFound } from "next/navigation";
import { routing } from "@/i18n/routing";
import { pageMetadata } from "@/lib/metadata";
import CTAProvider from "@/components/CTAProvider";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import Container from "@/components/Container";
import LeadForm from "@/components/LeadForm";

export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  return pageMetadata(locale, "contact");
}

export default async function ContactPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  if (!routing.locales.includes(locale as (typeof routing.locales)[number])) {
    notFound();
  }
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "form" });

  return (
    <CTAProvider>
      <Navbar />
      <main className="pt-28 pb-20">
        <Container className="mx-auto max-w-xl">
          <h1 className="text-center text-3xl font-bold tracking-tight sm:text-4xl">
            {t("contactTitle")}
          </h1>
          <p className="mt-3 text-center text-text-secondary">
            {t("contactDescription")}
          </p>
          <div className="mt-8 rounded-2xl border border-border-default bg-background-secondary p-6 sm:p-8">
            <LeadForm
              fields={[
                { name: "name" },
                { name: "restaurant" },
                { name: "email", type: "email" },
                { name: "message", optional: true },
              ]}
              submitKey="contactSubmit"
            />
          </div>
        </Container>
      </main>
      <Footer />
    </CTAProvider>
  );
}
