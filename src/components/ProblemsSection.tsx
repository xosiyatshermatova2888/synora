"use client";

import { useTranslations } from "next-intl";
import { Boxes, FileX2, Calculator, Timer } from "lucide-react";
import Container from "@/components/Container";

const icons = [Boxes, FileX2, Calculator, Timer];

export default function ProblemsSection() {
  const t = useTranslations("problems");
  const tc = useTranslations("problems.cards");
  const keys = ["tooMany", "lost", "unclear", "reactive"];

  return (
    <section className="py-16 sm:py-24">
      <Container>
        <h2 className="max-w-3xl text-3xl font-semibold tracking-tight sm:text-4xl">
          {t("headline")}
        </h2>
        <div className="mt-12 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {keys.map((k, i) => {
            const Icon = icons[i];
            return (
              <div
                key={k}
                className="rounded-2xl border border-border-default bg-surface/50 p-6 transition-colors duration-200 hover:border-border-default/80"
              >
                <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl bg-error/10 text-error">
                  <Icon className="h-5 w-5" aria-hidden="true" />
                </div>
                <h3 className="text-lg font-semibold">{tc(`${k}.title`)}</h3>
                <p className="mt-2 text-sm leading-relaxed text-text-secondary">
                  {tc(`${k}.text`)}
                </p>
              </div>
            );
          })}
        </div>
        <p className="mt-10 text-center">
          <span className="text-brand-gradient text-2xl font-semibold sm:text-3xl">
            {t("closing")}
          </span>
        </p>
      </Container>
    </section>
  );
}
