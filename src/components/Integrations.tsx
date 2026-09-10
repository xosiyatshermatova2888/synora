"use client";

import { useTranslations } from "next-intl";
import {
  Send,
  CreditCard,
  Landmark,
  Printer,
  Monitor,
  QrCode,
  Bike,
  Plug,
} from "lucide-react";
import { motion } from "framer-motion";
import Container from "@/components/Container";

const icons = [Send, CreditCard, Landmark, Printer, Monitor, QrCode, Bike, Plug];

export default function Integrations() {
  const t = useTranslations("integrations");
  const categories = t.raw("categories") as { title: string; text: string }[];

  return (
    <section className="py-16 sm:py-24">
      <Container>
        <h2 className="max-w-3xl text-3xl font-semibold tracking-tight sm:text-4xl">
          {t("headline")}
        </h2>
        <div className="mt-12 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {categories.map((c, i) => {
            const Icon = icons[i];
            return (
              <motion.div
                key={c.title}
                initial={{ opacity: 0, y: 16 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, amount: 0.3 }}
                transition={{ duration: 0.4, delay: (i % 4) * 0.08 }}
                className="group rounded-2xl border border-border-default bg-surface/50 p-6 transition-all duration-200 hover:-translate-y-1 hover:border-accent-primary/50"
              >
                <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl bg-text-secondary/10 text-text-primary transition-colors group-hover:bg-accent-primary/20 group-hover:text-accent-primary">
                  <Icon className="h-5 w-5" aria-hidden="true" />
                </div>
                <h3 className="text-lg font-semibold">{c.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-text-secondary">
                  {c.text}
                </p>
              </motion.div>
            );
          })}
        </div>
      </Container>
    </section>
  );
}

