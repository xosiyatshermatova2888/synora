"use client";

import { useTranslations } from "next-intl";
import {
  Monitor,
  ChefHat,
  Smartphone,
  QrCode,
  Send,
  Users,
  Package,
  BarChart3,
  Sparkles,
} from "lucide-react";
import { motion } from "framer-motion";
import Container from "@/components/Container";

const modules = [
  { key: "pos", icon: Monitor },
  { key: "kitchen", icon: ChefHat },
  { key: "waiter", icon: Smartphone },
  { key: "qr", icon: QrCode },
  { key: "telegram", icon: Send },
  { key: "crm", icon: Users },
  { key: "inventory", icon: Package },
  { key: "analytics", icon: BarChart3 },
  { key: "ai", icon: Sparkles },
];

export default function TrustSection() {
  const t = useTranslations("trust");
  const tf = useTranslations("features.items");

  return (
    <section className="border-y border-border-default bg-background-secondary/40 py-16 sm:py-20">
      <Container>
        <h2 className="text-center text-2xl font-semibold tracking-tight sm:text-3xl">
          {t("headline")}
        </h2>
        <div className="mt-10 grid grid-cols-3 gap-4 sm:grid-cols-9">
          {modules.map((m, i) => {
            const Icon = m.icon;
            return (
              <motion.div
                key={m.key}
                initial={{ opacity: 0, y: 12 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, amount: 0.4 }}
                transition={{ duration: 0.35, delay: i * 0.05 }}
                className="group flex flex-col items-center gap-2 rounded-2xl border border-border-default bg-surface/60 p-4 text-center transition-all duration-200 hover:-translate-y-1 hover:border-accent-primary/50"
              >
                <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-accent-primary/10 text-accent-primary transition-colors group-hover:bg-accent-primary/20">
                  <Icon className="h-5 w-5" aria-hidden="true" />
                </div>
                <span className="text-sm font-medium text-text-secondary">
                  {tf(`${m.key}.title`)}
                </span>
              </motion.div>
            );
          })}
        </div>
      </Container>
    </section>
  );
}

