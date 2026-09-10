"use client";

import { useTranslations } from "next-intl";
import { ClipboardList, HelpCircle, TrendingUp, Lightbulb, ArrowRight } from "lucide-react";
import { motion } from "framer-motion";
import Container from "@/components/Container";
import Badge from "@/components/Badge";

const icons = [ClipboardList, HelpCircle, TrendingUp, Lightbulb];
const order = ["whatHappened", "why", "whatNext", "whatDo"];

export default function AISection() {
  const t = useTranslations("ai");
  const tc = useTranslations("ai.cards");

  const scrollToDemo = () => {
    document.getElementById("demo")?.scrollIntoView({ behavior: "smooth" });
  };

  return (
    <section
      id="ai"
      className="relative scroll-mt-24 overflow-hidden bg-background-secondary/60 py-16 sm:py-24"
    >
      <div
        className="ai-glow pointer-events-none absolute inset-0"
        aria-hidden="true"
      />
      <Container className="relative">
        <div className="mx-auto max-w-2xl text-center">
          <Badge variant="ai" className="mb-5">
            <span aria-hidden="true">✦</span> {t("badge")}
          </Badge>
          <h2 className="text-3xl font-semibold tracking-tight sm:text-4xl">
            {t("headline")}
          </h2>
          <p className="mt-4 text-lg leading-relaxed text-text-secondary">
            {t("description")}
          </p>
        </div>

        <div className="mt-14 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {order.map((k, i) => {
            const Icon = icons[i];
            return (
              <motion.div
                key={k}
                initial={{ opacity: 0, y: 16 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, amount: 0.3 }}
                transition={{ duration: 0.4, delay: i * 0.08 }}
                className="rounded-2xl border border-accent-ai/20 bg-background-secondary/80 p-6 transition-colors duration-200 hover:border-accent-ai/40"
              >
                <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl bg-accent-ai/10 text-accent-ai">
                  <Icon className="h-5 w-5" aria-hidden="true" />
                </div>
                <h3 className="text-lg font-semibold">{tc(`${k}.title`)}</h3>
                <p className="mt-2 text-sm leading-relaxed text-text-secondary">
                  {tc(`${k}.text`)}
                </p>
              </motion.div>
            );
          })}
        </div>

        <div className="mt-12 text-center">
          <button
            onClick={scrollToDemo}
            className="inline-flex items-center gap-2 rounded-xl border border-accent-ai/40 bg-accent-ai/10 px-6 py-3 text-sm font-medium text-accent-ai transition-colors hover:bg-accent-ai/20"
          >
            {t("cta")} <ArrowRight className="h-4 w-4" />
          </button>
        </div>
      </Container>
    </section>
  );
}

