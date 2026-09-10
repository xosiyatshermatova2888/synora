"use client";

import { useTranslations } from "next-intl";
import {
  Monitor,
  Smartphone,
  ChefHat,
  QrCode,
  Send,
  Package,
  Users,
  BarChart3,
  Sparkles,
} from "lucide-react";
import { motion } from "framer-motion";
import Container from "@/components/Container";

const icons: Record<string, typeof Monitor> = {
  pos: Monitor,
  waiter: Smartphone,
  kitchen: ChefHat,
  qr: QrCode,
  telegram: Send,
  inventory: Package,
  crm: Users,
  analytics: BarChart3,
  ai: Sparkles,
};

const order = ["pos", "waiter", "kitchen", "qr", "telegram", "inventory", "crm", "analytics", "ai"];

export default function FeaturesSection() {
  const t = useTranslations("features");
  const tf = useTranslations("features.items");

  return (
    <section id="features" className="relative scroll-mt-24 py-16 sm:py-24">
      <Container>
        <h2 className="text-center text-3xl font-semibold tracking-tight sm:text-4xl">
          {t("headline")}
        </h2>
        <div className="mt-12 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {order.map((k, i) => {
            const Icon = icons[k];
            return (
              <motion.div
                key={k}
                initial={{ opacity: 0, y: 16 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, amount: 0.3 }}
                transition={{ duration: 0.4, delay: (i % 3) * 0.08 }}
                className="group rounded-2xl border border-border-default bg-surface/50 p-6 transition-all duration-200 hover:-translate-y-1 hover:border-accent-primary/50 hover:bg-surface/80"
              >
                <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl bg-accent-primary/10 text-accent-primary transition-colors group-hover:bg-accent-primary/20">
                  <Icon className="h-5 w-5" aria-hidden="true" />
                </div>
                <h3 className="text-lg font-semibold">{tf(`${k}.title`)}</h3>
                <p className="mt-2 text-sm leading-relaxed text-text-secondary">
                  {tf(`${k}.text`)}
                </p>
              </motion.div>
            );
          })}
        </div>
      </Container>
    </section>
  );
}

