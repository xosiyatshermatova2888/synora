"use client";

import { useTranslations } from "next-intl";
import { motion, useInView } from "framer-motion";
import { useRef } from "react";
import { Share2 } from "lucide-react";
import Container from "@/components/Container";

function FlowNode({
  label,
  variant = "source",
}: {
  label: string;
  variant?: "source" | "engine" | "dest";
}) {
  const styles =
    variant === "engine"
      ? "border-accent-ai/50 bg-accent-ai/10 text-accent-ai"
      : variant === "dest"
      ? "bg-surface text-text-primary border-border-default"
      : "bg-background-secondary text-text-primary border-border-default";
  return (
    <div
      className={`rounded-xl border px-3 py-2.5 text-center text-sm font-medium ${styles}`}
    >
      {label}
    </div>
  );
}

export default function SolutionFlow() {
  const t = useTranslations("solution");
  const sources = t.raw("sources") as string[];
  const destinations = t.raw("destinations") as string[];
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, amount: 0.3 });

  return (
    <section id="solution" className="py-16 sm:py-24">
      <Container>
        <h2 className="text-center text-3xl font-semibold tracking-tight sm:text-4xl">
          {t("headline")}
        </h2>

        <div ref={ref} className="mt-14">
          <p className="mb-4 text-center text-sm font-medium uppercase tracking-wider text-text-secondary">
            {t("orderSources")}
          </p>
          <div className="mx-auto flex max-w-3xl flex-wrap justify-center gap-3">
            {sources.map((s) => (
              <FlowNode key={s} label={s} />
            ))}
          </div>

          <div className="my-4 flex justify-center">
            <motion.div
              initial={{ opacity: 0 }}
              animate={inView ? { opacity: 1 } : {}}
              transition={{ duration: 0.5 }}
              className="flex items-center gap-3"
            >
              <div className="flow-line h-0.5 w-24 bg-transparent" aria-hidden="true" />
              <div className="flex items-center gap-2 rounded-2xl border border-accent-ai/40 bg-accent-ai/10 px-6 py-3 shadow-lg shadow-accent-ai/10">
                <Share2 className="h-5 w-5 text-accent-ai" aria-hidden="true" />
                <span className="font-semibold text-accent-ai">
                  {t("engine")}
                </span>
              </div>
              <div className="flow-line h-0.5 w-24 bg-transparent" aria-hidden="true" />
            </motion.div>
          </div>

          <p className="mb-4 text-center text-sm font-medium uppercase tracking-wider text-text-secondary">
            {t("outcomes")}
          </p>
          <div className="mx-auto flex max-w-3xl flex-wrap justify-center gap-3">
            {destinations.map((d) => (
              <FlowNode key={d} label={d} variant="dest" />
            ))}
          </div>
        </div>
      </Container>
    </section>
  );
}

