"use client";

import { useTranslations } from "next-intl";
import { ArrowRight } from "lucide-react";
import Container from "@/components/Container";
import { useCTA } from "@/components/CTAProvider";

export default function FinalCTA() {
  const t = useTranslations("final");
  const { openTrial, openContact } = useCTA();

  return (
    <section className="relative overflow-hidden py-24 sm:py-32">
      <div className="ai-glow pointer-events-none absolute inset-0" aria-hidden="true" />
      <Container className="relative">
        <div className="mx-auto max-w-3xl text-center">
          <h2 className="text-4xl font-bold tracking-tight sm:text-5xl">
            {t("headline")}
          </h2>
          <p className="mt-5 text-xl text-text-secondary">{t("subheadline")}</p>
          <div className="mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <button
              onClick={openTrial}
              className="inline-flex h-14 items-center justify-center gap-2 rounded-xl bg-accent-primary px-8 text-base font-medium text-white shadow-lg shadow-accent-primary/20 transition-all duration-200 hover:brightness-110"
            >
              {t("primaryCta")} <ArrowRight className="h-4 w-4" />
            </button>
            <button
              onClick={openContact}
              className="inline-flex h-14 items-center justify-center rounded-xl border border-border-default bg-surface px-8 text-base font-medium text-text-primary transition-colors hover:border-accent-primary/60"
            >
              {t("secondaryCta")}
            </button>
          </div>
        </div>
      </Container>
    </section>
  );
}
