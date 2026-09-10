"use client";

import { useTranslations } from "next-intl";
import { Building2, Store, TrendingUp, Package, Users } from "lucide-react";
import { motion } from "framer-motion";
import Container from "@/components/Container";

const branches = [
  { name: "Branch 01", sales: "8 450 000", stock: "92%", staff: "14" },
  { name: "Branch 02", sales: "9 480 000", stock: "96%", staff: "18" },
  { name: "Branch 03", sales: "7 210 000", stock: "81%", staff: "11" },
];

export default function MultiBranch() {
  const t = useTranslations("branches");

  return (
    <section className="border-y border-border-default bg-background-secondary/40 py-16 sm:py-24">
      <Container>
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="text-3xl font-semibold tracking-tight sm:text-4xl">
            {t("headline")}
          </h2>
          <p className="mt-4 text-lg text-text-secondary">{t("description")}</p>
        </div>

        <div className="mt-12 flex flex-col items-center gap-8">
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.4 }}
            className="flex items-center gap-3 rounded-2xl border border-accent-ai/30 bg-background-secondary px-8 py-5"
          >
            <Building2 className="h-6 w-6 text-accent-ai" aria-hidden="true" />
            <div>
              <p className="font-semibold">{t("hq")}</p>
              <p className="text-sm text-text-secondary">SYNORA HQ</p>
            </div>
          </motion.div>

          <div
            className="hidden h-10 w-0.5 bg-border-default md:block"
            aria-hidden="true"
          />
          <div
            className="block h-0.5 w-40 bg-border-default md:hidden"
            aria-hidden="true"
          />

          <div className="grid w-full gap-5 sm:grid-cols-3">
            {branches.map((b, i) => (
              <motion.div
                key={b.name}
                initial={{ opacity: 0, y: 16 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, amount: 0.3 }}
                transition={{ duration: 0.4, delay: i * 0.1 }}
                className="rounded-2xl border border-border-default bg-surface/60 p-6 text-center"
              >
                <div className="mb-3 flex items-center justify-center gap-2">
                  <Store className="h-5 w-5 text-text-secondary" aria-hidden="true" />
                  <p className="font-semibold">{b.name}</p>
                </div>
                <div className="grid grid-cols-3 gap-2 text-sm">
                  <div className="rounded-lg bg-background-secondary/60 p-2">
                    <TrendingUp className="mx-auto mb-1 h-4 w-4 text-success" aria-hidden="true" />
                    <p className="text-[11px] text-text-secondary">{t("sales")}</p>
                    <p className="mt-0.5 font-medium">{b.sales}</p>
                  </div>
                  <div className="rounded-lg bg-background-secondary/60 p-2">
                    <Package className="mx-auto mb-1 h-4 w-4 text-accent-ai" aria-hidden="true" />
                    <p className="text-[11px] text-text-secondary">{t("stock")}</p>
                    <p className="mt-0.5 font-medium">{b.stock}</p>
                  </div>
                  <div className="rounded-lg bg-background-secondary/60 p-2">
                    <Users className="mx-auto mb-1 h-4 w-4 text-warning" aria-hidden="true" />
                    <p className="text-[11px] text-text-secondary">{t("staff")}</p>
                    <p className="mt-0.5 font-medium">{b.staff}</p>
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </Container>
    </section>
  );
}

