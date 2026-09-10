"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Check, Sparkles } from "lucide-react";
import { motion } from "framer-motion";
import Container from "@/components/Container";
import { useCTA } from "@/components/CTAProvider";

export default function PricingSection() {
  const t = useTranslations("pricing");
  const plans = t.raw("plans") as {
    name: string;
    price: string | null;
    unit: string;
    badge: string | null;
    features: string[];
  }[];
  const { openTrial, openContact } = useCTA();
  const [annual, setAnnual] = useState(false); // TODO: annual pricing pending business decision

  return (
    <section id="pricing" className="scroll-mt-24 py-16 sm:py-24">
      <Container>
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="text-3xl font-semibold tracking-tight sm:text-4xl">
            {t("headline")}
          </h2>
        </div>

        <div className="mt-8 flex items-center justify-center gap-3">
          <span
            className={`text-sm ${!annual ? "text-text-primary" : "text-text-secondary"}`}
          >
            {t("monthly")}
          </span>
          <button
            onClick={() => setAnnual((v) => !v)}
            role="switch"
            aria-checked={annual}
            aria-label={t("annual")}
            className="relative h-7 w-12 rounded-full bg-surface transition-colors"
          >
            <span
              className={`absolute top-1 h-5 w-5 rounded-full bg-accent-primary transition-all duration-200 ${
                annual ? "left-6" : "left-1"
              }`}
            />
          </button>
          <span
            className={`text-sm ${annual ? "text-text-primary" : "text-text-secondary"}`}
          >
            {t("annual")}
          </span>
        </div>

        <div className="mt-12 grid gap-6 lg:grid-cols-4">
          {plans.map((plan, i) => {
            const isPro = plan.badge === "Most Popular" || plan.badge === "Популярный" || plan.badge === "Eng ommabop";
            const isAI = plan.name.includes("AI") || plan.name === "AI Premium";
            const featured = isPro;

            return (
              <motion.div
                key={plan.name}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, amount: 0.2 }}
                transition={{ duration: 0.4, delay: i * 0.08 }}
                className={`relative flex flex-col rounded-2xl border p-6 ${
                  featured
                    ? "border-accent-primary bg-background-secondary shadow-xl shadow-accent-primary/10 lg:-mt-3 lg:mb-[-12px]"
                    : isAI
                    ? "border-accent-ai/40 bg-background-secondary/80"
                    : "border-border-default bg-surface/50"
                }`}
              >
                {plan.badge && (
                  <span
                    className={`absolute -top-3 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-full px-3 py-1 text-xs font-semibold ${
                      isAI
                        ? "bg-accent-ai text-background"
                        : "bg-brand-gradient text-white"
                    }`}
                  >
                    {isAI && <Sparkles className="mr-1 inline h-3 w-3" aria-hidden="true" />}
                    {plan.badge}
                  </span>
                )}
                <h3 className="text-lg font-semibold">{plan.name}</h3>
                <div className="mt-4 flex items-end gap-1">
                  {plan.price ? (
                    <>
                      <span className="text-3xl font-bold tracking-tight">
                        {plan.price}
                      </span>
                      <span className="mb-1 text-sm text-text-secondary">
                        {plan.unit}
                      </span>
                    </>
                  ) : (
                    <span className="text-3xl font-bold tracking-tight">
                      {plan.unit}
                    </span>
                  )}
                </div>
                <ul className="mt-6 mb-8 flex-1 space-y-2.5">
                  {plan.features.map((f) => (
                    <li key={f} className="flex items-start gap-2 text-sm">
                      <Check className="mt-0.5 h-4 w-4 shrink-0 text-success" aria-hidden="true" />
                      <span className="text-text-secondary">{f}</span>
                    </li>
                  ))}
                </ul>
                <button
                  onClick={plan.price ? openTrial : openContact}
                  className={`h-11 w-full rounded-xl text-sm font-medium transition-all duration-200 ${
                    featured
                      ? "bg-accent-primary text-white hover:brightness-110"
                      : isAI
                      ? "border border-accent-ai/40 bg-accent-ai/10 text-accent-ai hover:bg-accent-ai/20"
                      : "border border-border-default bg-surface text-text-primary hover:border-accent-primary/50"
                  }`}
                >
                  {plan.price ? t("trial") : t("contact")}
                </button>
              </motion.div>
            );
          })}
        </div>
      </Container>
    </section>
  );
}

