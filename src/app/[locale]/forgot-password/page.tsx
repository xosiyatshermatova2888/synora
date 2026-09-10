import { setRequestLocale, getTranslations } from "next-intl/server";
import { notFound } from "next/navigation";
import { routing } from "@/i18n/routing";
import CTAProvider from "@/components/CTAProvider";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import Container from "@/components/Container";
import ForgotPasswordForm from "@/components/ForgotPasswordForm";
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
  return pageMetadata(locale, "login");
}

export default async function ForgotPasswordPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  if (!routing.locales.includes(locale as (typeof routing.locales)[number])) {
    notFound();
  }
  setRequestLocale(locale);
  const t = await getTranslations({ locale, namespace: "auth" });

  return (
    <CTAProvider>
      <Navbar />
      <main className="flex min-h-[70vh] items-center pt-24 pb-20">
        <Container className="max-w-md">
          <div className="rounded-3xl border border-border-default bg-surface p-8 shadow-sm sm:p-10">
            <h1 className="text-2xl font-bold tracking-tight text-text-primary">
              {t("forgotTitle")}
            </h1>
            <p className="mt-1.5 text-sm text-text-secondary">{t("forgotSubtitle")}</p>
            <div className="mt-8">
              <ForgotPasswordForm />
            </div>
          </div>
        </Container>
      </main>
      <Footer />
    </CTAProvider>
  );
}