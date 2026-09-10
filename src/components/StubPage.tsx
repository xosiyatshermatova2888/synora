import { getTranslations } from "next-intl/server";
import CTAProvider from "@/components/CTAProvider";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import Container from "@/components/Container";
import { Link } from "@/i18n/navigation";
import { Construction } from "lucide-react";

export default async function StubPage({
  locale,
  titleKey,
}: {
  locale: string;
  titleKey: string;
}) {
  const t = await getTranslations({ locale, namespace: "stub" });
  const p = await getTranslations({ locale, namespace: "pages" });

  return (
    <CTAProvider>
      <Navbar />
      <main className="flex min-h-[60vh] items-center pt-24 pb-20">
        <Container className="max-w-xl text-center">
          <div className="mx-auto mb-6 flex h-14 w-14 items-center justify-center rounded-2xl bg-accent-primary/10 text-accent-primary">
            <Construction className="h-6 w-6" aria-hidden="true" />
          </div>
          <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">
            {p(titleKey)}
          </h1>
          <p className="mt-3 text-text-secondary">{t("comingSoon")}</p>
          <p className="mt-6">
            <Link
              href="/"
              className="inline-flex h-11 items-center justify-center rounded-xl border border-border-default bg-surface px-6 text-sm font-medium text-text-primary transition-colors hover:border-accent-primary/60"
            >
              {t("backHome")}
            </Link>
          </p>
        </Container>
      </main>
      <Footer />
    </CTAProvider>
  );
}

