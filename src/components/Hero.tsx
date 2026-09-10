"use client";

import { useTranslations } from "next-intl";
import { ArrowRight, Play } from "lucide-react";
import { motion } from "framer-motion";
import Container from "@/components/Container";
import Badge from "@/components/Badge";
import { useCTA } from "@/components/CTAProvider";

export default function Hero() {
  const t = useTranslations("hero");
  const { openTrial } = useCTA();

  const scrollToDemo = () => {
    document.getElementById("demo")?.scrollIntoView({ behavior: "smooth" });
  };

  return (
    <section className="relative overflow-hidden pb-16 pt-28 sm:pb-20 sm:pt-36">
      <div className="grid-backdrop pointer-events-none absolute inset-0 [mask-image:radial-gradient(ellipse_at_top,black_40%,transparent_75%)]" aria-hidden="true" />
      <div className="ai-glow pointer-events-none absolute -top-24 left-1/2 h-[500px] w-[800px] -translate-x-1/2" aria-hidden="true" />

<Container className="relative">
        <div className="mx-auto max-w-3xl text-center">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            <Badge className="mb-5">
              <span aria-hidden="true">✦</span> {t("badge")}
            </Badge>
            <h1 className="text-4xl font-bold leading-tight tracking-tight sm:text-5xl lg:text-6xl">
              {t("headline1")}{" "}
              <span className="text-brand-gradient">{t("headline2")}</span>
            </h1>
            <p className="mx-auto mt-5 max-w-xl text-lg leading-relaxed text-text-secondary">
              {t("description")}
            </p>
            <div className="mt-8 flex flex-col items-center gap-3 sm:flex-row sm:justify-center">
              <button
                onClick={openTrial}
                className="inline-flex h-14 items-center justify-center gap-2 rounded-xl bg-accent-primary px-8 text-base font-medium text-white shadow-lg shadow-accent-primary/20 transition-all duration-200 hover:brightness-110"
              >
                {t("primaryCta")} <ArrowRight className="h-4 w-4" />
              </button>
              <button
                onClick={scrollToDemo}
                className="inline-flex h-14 items-center justify-center gap-2 rounded-xl border border-border-default bg-surface px-8 text-base font-medium text-text-primary transition-colors hover:border-accent-primary/60"
              >
                <Play className="h-4 w-4" /> {t("secondaryCta")}
              </button>
            </div>
            <p className="mt-4 text-sm text-text-secondary">{t("noCard")}</p>
          </motion.div>
        </div>
      </Container>
    </section>
  );
}

