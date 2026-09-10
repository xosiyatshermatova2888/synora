"use client";

import { useState, useRef, useEffect } from "react";
import { useTranslations } from "next-intl";
import { Sparkles, Send } from "lucide-react";
import { motion } from "framer-motion";
import Container from "@/components/Container";

type Message = { role: "user" | "ai"; text: string; key: number };

function renderBold(text: string) {
  const parts = text.split(/\*\*(.+?)\*\*/g);
  return parts.map((p, i) =>
    i % 2 === 1 ? (
      <span key={i} className="font-semibold text-accent-ai">
        {p}
      </span>
    ) : (
      <span key={i}>{p}</span>
    )
  );
}

export default function AIDemo() {
  const t = useTranslations("demo");
  const [messages, setMessages] = useState<Message[]>(() => {
    const convo = t.raw("conversation") as { role: string; text: string }[];
    return convo.map((m, i) => ({
      role: m.role as "user" | "ai",
      text: m.text,
      key: i,
    }));
  });
  const [selected, setSelected] = useState<string | null>(null);
  const nextKey = useRef(100);
  const bottomRef = useRef<HTMLDivElement>(null);
  const canned = t.raw("canned") as Record<string, string>;
  const chipKeys = ["restock", "profit", "down", "branch"];

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleChip = (key: string) => {
    setSelected((prev) => (prev === key ? null : key));
    const chipIndex = chipKeys.indexOf(key);
    const question = (t.raw("chips") as string[])[chipIndex];

    setMessages((msgs) => [
      ...msgs,
      { role: "user", text: question, key: nextKey.current++ },
    ]);

    setTimeout(() => {
      setMessages((msgs) => [
        ...msgs,
        { role: "ai", text: canned[key], key: nextKey.current++ },
      ]);
    }, 600);
  };

  return (
    <section id="demo" className="scroll-mt-24 py-16 sm:py-24">
      <Container>
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="text-3xl font-semibold tracking-tight sm:text-4xl">
            {t("title")}
          </h2>
        </div>

        <div className="mx-auto mt-10 max-w-2xl overflow-hidden rounded-2xl border border-border-default bg-background-secondary">
          <div className="flex items-center gap-3 border-b border-border-default bg-surface/60 px-5 py-3">
            <div className="ai-pulse flex h-8 w-8 items-center justify-center rounded-full bg-accent-ai/15">
              <Sparkles className="h-4 w-4 text-accent-ai" />
            </div>
            <div>
              <p className="text-sm font-semibold">{t("ai")}</p>
              <p className="text-xs text-accent-ai">● online</p>
            </div>
          </div>

          <div className="max-h-[420px] space-y-4 overflow-y-auto p-5">
            {messages.map((m) => (
              <motion.div
                key={m.key}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3 }}
                className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
              >
                {m.role === "ai" && (
                  <span className="mr-2 mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-accent-ai/15">
                    <Sparkles className="h-3 w-3 text-accent-ai" aria-hidden="true" />
                  </span>
                )}
                <div
                  className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                    m.role === "user"
                      ? "rounded-br-sm bg-accent-primary text-white"
                      : "rounded-bl-sm bg-surface text-text-primary"
                  }`}
                >
                  {m.role === "ai" ? renderBold(m.text) : m.text}
                </div>
              </motion.div>
            ))}
            <div ref={bottomRef} />
          </div>

          <div className="border-t border-border-default bg-surface/40 p-4">
            <p className="mb-3 text-xs text-text-secondary">{t("demoMode")}</p>
            <div className="flex flex-wrap gap-2">
              {(t.raw("chips") as string[]).map((chip, i) => {
                const key = chipKeys[i];
                return (
                  <button
                    key={key}
                    onClick={() => handleChip(key)}
                    className={`rounded-full border px-3.5 py-2 text-xs font-medium transition-colors duration-200 ${
                      selected === key
                        ? "border-accent-ai bg-accent-ai/15 text-accent-ai"
                        : "border-border-default bg-background-secondary text-text-secondary hover:border-accent-ai/50 hover:text-text-primary"
                    }`}
                  >
                    {chip}
                  </button>
                );
              })}
            </div>
            <div className="mt-3 flex items-center gap-2 opacity-60">
              <input
                readOnly
                value={t("demoMode")}
                aria-label={t("demoMode")}
                className="flex-1 rounded-xl border border-border-default bg-background-secondary px-4 py-2.5 text-sm text-text-secondary"
              />
              <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-surface text-text-secondary">
                <Send className="h-4 w-4" aria-hidden="true" />
              </span>
            </div>
          </div>
        </div>
      </Container>
    </section>
  );
}

