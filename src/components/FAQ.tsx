"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { ChevronDown } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import Container from "@/components/Container";

export default function FAQ() {
  const t = useTranslations("faq");
  const items = t.raw("items") as { q: string; a: string }[];
  const [open, setOpen] = useState<number | null>(0);

  const toggle = (i: number) => {
    setOpen((cur) => (cur === i ? null : i));
  };

  return (
    <section id="faq" className="scroll-mt-24 py-16 sm:py-24">
      <Container>
        <div className="mx-auto max-w-3xl">
          <h2 className="text-center text-3xl font-semibold tracking-tight sm:text-4xl">
            {t("headline")}
          </h2>
          <div className="mt-12 space-y-3">
            {items.map((item, i) => {
              const isOpen = open === i;
              return (
                <div
                  key={i}
                  className="rounded-xl border border-border-default bg-surface/50"
                >
                  <button
                    onClick={() => toggle(i)}
                    aria-expanded={isOpen}
                    aria-controls={`faq-panel-${i}`}
                    id={`faq-button-${i}`}
                    className="flex w-full items-center justify-between gap-4 rounded-xl px-5 py-4 text-left text-base font-medium text-text-primary transition-colors hover:bg-surface/80"
                  >
                    {item.q}
                    <ChevronDown
                      className={`h-5 w-5 shrink-0 text-text-secondary transition-transform duration-200 ${
                        isOpen ? "rotate-180" : ""
                      }`}
                      aria-hidden="true"
                    />
                  </button>
                  <AnimatePresence initial={false}>
                    {isOpen && (
                      <motion.div
                        id={`faq-panel-${i}`}
                        role="region"
                        aria-labelledby={`faq-button-${i}`}
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: "auto", opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.25 }}
                        className="overflow-hidden"
                      >
                        <p className="px-5 pb-5 text-sm leading-relaxed text-text-secondary">
                          {item.a}
                        </p>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              );
            })}
          </div>
        </div>
      </Container>
    </section>
  );
}

