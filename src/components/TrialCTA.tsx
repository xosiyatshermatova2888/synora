"use client";

import { useTranslations } from "next-intl";
import { ArrowRight } from "lucide-react";
import Container from "@/components/Container";
import { useCTA } from "@/components/CTAProvider";

export default function TrialCTA() {
  const t = useTranslations("trial");
  const { openTrial, openContact } = useCTA();

  return (
    <section className="border-y border-border-default bg-background-secondary/50 py-16 sm:py-20">
      <Container>
        <div className="mx-auto max-w-3xl text-center">
          <h2 className="text-3xl font-semibold tracking-tight sm:text-4xl">
            {t("headline")}
          </h2>
          <p className="mt-4 text-lg text-text-secondary">{t("description")}</p>
          <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
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
          <p className="mt-4 text-sm text-text-secondary">{t("noCard")}</p>
        </div>
      </Container>
    </section>
  );
}
