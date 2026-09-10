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
  return pageMetadata(locale, "terms");
}

export default async function TermsPage({
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
            {t("termsTitle")}
          </h1>
          <p className="mt-2 text-sm text-text-secondary">
            {t("lastUpdated")}: 1 September 2026
          </p>
          <div className="mt-8 space-y-8 text-sm leading-relaxed text-text-secondary">
            <section>
              <h2 className="mb-2 text-lg font-semibold text-text-primary">
                1. Website content
              </h2>
              <p>
                This website provides general information about SYNORA, an
                AI-native restaurant operating system. All product descriptions,
                features and pricing shown are subject to change and do not
                constitute a binding offer until a formal agreement is signed.
              </p>
            </section>
            <section>
              <h2 className="mb-2 text-lg font-semibold text-text-primary">
                2. No warranty
              </h2>
              <p>
                The information, demonstrations and mock data shown on this
                website are provided for illustrative purposes only. We make no
                warranties about the accuracy or completeness of this
                marketing content.
              </p>
            </section>
            <section>
              <h2 className="mb-2 text-lg font-semibold text-text-primary">
                3. Placing a trial request
              </h2>
              <p>
                By submitting a trial or contact form, you agree that we may
                contact you about your enquiry. Submitting a form does not
                create a binding contract for the SYNORA product.
              </p>
            </section>
            <section>
              <h2 className="mb-2 text-lg font-semibold text-text-primary">
                4. Intellectual property
              </h2>
              <p>
                SYNORA and the content on this website are our property. You may
                not copy, reproduce or redistribute the content without
                permission.
              </p>
            </section>
            <section>
              <h2 className="mb-2 text-lg font-semibold text-text-primary">
                5. Governing law
              </h2>
              <p>
                These terms are governed by the laws of the Republic of
                Uzbekistan, which is also our primary market.
              </p>
            </section>
            <section>
              <h2 className="mb-2 text-lg font-semibold text-text-primary">
                6. Contact
              </h2>
              <p>
                For questions about these terms, contact{" "}
                <a
                  href="mailto:legal@synora.app"
                  className="text-accent-ai underline"
                >
                  legal@synora.app
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

