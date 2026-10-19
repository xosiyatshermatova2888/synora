"use client";

import { useTranslations } from "next-intl";
import { ArrowRight, Check } from "lucide-react";
import { motion } from "framer-motion";
import Container from "@/components/Container";
import HeroMockup from "@/components/HeroMockup";
import { useCTA } from "@/components/CTAProvider";

export default function Hero() {
  const t = useTranslations("hero");
  const { openTrial } = useCTA();

  const points = [t("noCard"), t("pointOffline"), t("pointQr"), t("pointLangs")];

  return (
    <section className="relative overflow-hidden bg-[#071a1c] pb-16 pt-28 text-white sm:pb-24 sm:pt-36">
      <div
        className="grid-backdrop-dark pointer-events-none absolute inset-0 [mask-image:radial-gradient(ellipse_at_top_left,black_35%,transparent_75%)]"
        aria-hidden="true"
      />
      <div
        className="pointer-events-none absolute -top-32 left-[-10%] h-[520px] w-[720px] bg-[radial-gradient(ellipse_at_center,rgba(18,168,155,0.18),transparent_70%)]"
        aria-hidden="true"
      />

      <Container className="relative">
        <div className="grid items-center gap-12 lg:grid-cols-[1.05fr_1fr] lg:gap-10">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            <span className="mb-5 inline-flex items-center gap-1.5 rounded-full border border-white/15 bg-white/5 px-3.5 py-1.5 text-xs font-medium tracking-wide text-teal-100/80">
              <span aria-hidden="true">✦</span> {t("badge")}
            </span>
            <h1 className="text-4xl font-bold leading-[1.1] tracking-tight sm:text-5xl lg:text-[3.4rem]">
              {t("headline1")} <span className="text-brand-gradient">{t("headline2")}</span>
            </h1>
            <p className="mt-5 max-w-xl text-lg leading-relaxed text-slate-300">{t("description")}</p>

            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <button
                onClick={openTrial}
                className="inline-flex h-13 items-center justify-center gap-2 rounded-xl bg-accent-primary px-7 py-3.5 text-base font-medium text-white transition-colors hover:bg-accent-hover"
              >
                {t("primaryCta")} <ArrowRight className="h-4 w-4" />
              </button>
            </div>

            <ul className="mt-7 grid gap-2 text-sm text-slate-300 sm:grid-cols-2">
              {points.map((p) => (
                <li key={p} className="flex items-center gap-2">
                  <Check className="h-4 w-4 shrink-0 text-[#a9cf3a]" aria-hidden="true" />
                  {p}
                </li>
              ))}
            </ul>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 28 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.1 }}
          >
            <HeroMockup />
          </motion.div>
        </div>
      </Container>
    </section>
  );
}
