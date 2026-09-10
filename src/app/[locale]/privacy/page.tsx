import { getTranslations, setRequestLocale } from "next-intl/server";
import { notFound } from "next/navigation";
import { routing } from "@/i18n/routing";
import { pageMetadata } from "@/lib/metadata";
import CTAProvider from "@/components/CTAProvider";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import Container from "@/components/Container";
import { Link } from "@/i18n/navigation";

export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  return pageMetadata(locale, "privacy");
}

export default async function PrivacyPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  if (!routing.locales.includes(locale as (typeof routing.locales)[number])) {
    notFound();
  }
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "legal" });
  const stub = await getTranslations({ locale, namespace: "stub" });

  return (
    <CTAProvider>
      <Navbar />
      <main className="pt-28 pb-20">
        <Container className="max-w-3xl">
          <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">
            {t("privacyTitle")}
          </h1>
          <p className="mt-2 text-sm text-text-secondary">
            {t("lastUpdated")}: 1 September 2026
          </p>
          <div className="prose-invert mt-8 space-y-8 text-sm leading-relaxed text-text-secondary">
            <section>
              <h2 className="mb-2 text-lg font-semibold text-text-primary">
                1. Introduction
              </h2>
              <p>
                This website is the official marketing site for SYNORA, an
                AI-native restaurant operating system. This Privacy Policy
                explains what data we collect through this marketing website
                today.
              </p>
            </section>
            <section>
              <h2 className="mb-2 text-lg font-semibold text-text-primary">
                2. Data we collect
              </h2>
              <p>
                We currently collect only the information you choose to provide
                through our contact and trial forms, such as your name,
                restaurant name, email address and phone number. We may also
                collect standard, aggregated analytics data (for example, page
                views) to improve the website, if analytics is enabled.
              </p>
            </section>
            <section>
              <h2 className="mb-2 text-lg font-semibold text-text-primary">
                3. Marketing-site scope
              </h2>
              <p>
                Please note that this is a marketing website. The data policy
                for the future SYNORA product and platform will be published
                separately before the product launches.
              </p>
            </section>
            <section>
              <h2 className="mb-2 text-lg font-semibold text-text-primary">
                4. How we use data
              </h2>
              <p>
                Information provided through forms is used to respond to your
                enquiry and, if you opt in, to contact you about SYNORA. We do
                not sell or share your personal data with third parties for
                their own marketing purposes.
              </p>
            </section>
            <section>
              <h2 className="mb-2 text-lg font-semibold text-text-primary">
                5. Your rights
              </h2>
              <p>
                You may request access to, correction of, or deletion of the
                personal data you have provided at any time.
              </p>
            </section>
            <section>
              <h2 className="mb-2 text-lg font-semibold text-text-primary">
                6. Contact
              </h2>
              <p>
                {t("contact")}:{" "}
                <a
                  href="mailto:privacy@synora.app"
                  className="text-accent-ai underline"
                >
                  privacy@synora.app
                </a>
              </p>
            </section>
          </div>
          <p className="mt-10">
            <Link href="/" className="text-accent-ai underline">
              ← {stub("backHome")}
            </Link>
          </p>
        </Container>
      </main>
      <Footer />
    </CTAProvider>
  );
}

