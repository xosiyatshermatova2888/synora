"use client";

import { useTranslations } from "next-intl";
import { motion } from "framer-motion";
import Container from "@/components/Container";

export default function HowItWorks() {
  const t = useTranslations("how");
  const steps = [0, 1, 2, 3].map((i) => ({
    title: t(`steps.${i}.title`),
    text: t(`steps.${i}.text`),
  }));

  return (
    <section className="border-y border-border-default bg-background-secondary/40 py-16 sm:py-24">
      <Container>
        <h2 className="max-w-3xl text-3xl font-semibold tracking-tight sm:text-4xl">
          {t("headline")}
        </h2>
        <div className="mt-12 grid gap-8 lg:grid-cols-4">
          {steps.map((s, i) => (
            <motion.div
              key={s.title}
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, amount: 0.3 }}
              transition={{ duration: 0.4, delay: i * 0.1 }}
              className="relative"
            >
              <div className="mb-4">
                <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-gradient text-lg font-bold text-white">
                  0{i + 1}
                </span>
              </div>
              <h3 className="text-lg font-semibold">{s.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-text-secondary">
                {s.text}
              </p>
              {i < 3 && (
                <div
                  className="absolute -right-4 top-6 hidden h-0.5 w-6 bg-border-default lg:block"
                  aria-hidden="true"
                />
              )}
            </motion.div>
          ))}
        </div>
      </Container>
    </section>
  );
}

