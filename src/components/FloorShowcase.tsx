"use client";

import { useTranslations } from "next-intl";
import { Check } from "lucide-react";
import Container from "@/components/Container";

type State = "free" | "ordered" | "waiting" | "paid";

// Sample floor for illustration only (not live data).
const FLOOR: State[] = [
  "free", "paid", "waiting", "ordered",
  "free", "paid", "waiting", "ordered",
  "free", "paid", "waiting", "ordered",
];

const STATE_CLS: Record<State, string> = {
  free: "border-emerald-400/40 bg-emerald-400/10 text-emerald-300",
  ordered: "border-sky-400/40 bg-sky-400/10 text-sky-300",
  waiting: "border-amber-400/45 bg-amber-400/10 text-amber-300",
  paid: "border-teal-300/40 bg-teal-300/10 text-teal-200",
};

export default function FloorShowcase() {
  const t = useTranslations("floorShowcase");
  const tt = useTranslations("tablesPage");
  const tc = useTranslations("common");
  const to = useTranslations("ordersPage");

  const label: Record<State, string> = {
    free: tc("tableStatus.AVAILABLE"),
    ordered: tt("stateOrdered"),
    waiting: tt("awaitingPayment"),
    paid: tc("paymentStatus.PAID"),
  };
  const points = [t("p1"), t("p2"), t("p3"), t("p4")];

  return (
    <section className="py-20 sm:py-24" id="floor">
      <Container>
        <div className="grid items-center gap-12 lg:grid-cols-2">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-accent-primary">{t("eyebrow")}</p>
            <h2 className="mt-2 text-3xl font-bold tracking-tight sm:text-4xl">{t("title")}</h2>
            <p className="mt-4 max-w-lg text-lg text-text-secondary">{t("description")}</p>
            <ul className="mt-6 space-y-3">
              {points.map((p) => (
                <li key={p} className="flex items-start gap-3 text-text-primary">
                  <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-accent-primary/10 text-accent-primary">
                    <Check className="h-3.5 w-3.5" aria-hidden="true" />
                  </span>
                  {p}
                </li>
              ))}
            </ul>
          </div>

          <figure>
            <div
              className="rounded-2xl border border-white/10 bg-[#0a1e21] p-5 shadow-[0_30px_70px_-25px_rgba(7,26,28,0.7)]"
              aria-hidden="true"
            >
              <div className="mb-4 flex items-center justify-between">
                <p className="text-xs font-semibold uppercase tracking-wider text-teal-200/70">
                  {t("floorLabel", { n: FLOOR.length })}
                </p>
                <span className="inline-flex items-center gap-1.5 text-[11px] text-emerald-300">
                  <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-400" />
                  {t("live")}
                </span>
              </div>
              <div className="grid grid-cols-4 gap-2.5">
                {FLOOR.map((s, i) => (
                  <div key={i} className={`rounded-xl border px-2 py-3 text-center ${STATE_CLS[s]}`}>
                    <p className="text-sm font-semibold">
                      {to("table")} {i + 1}
                    </p>
                    <p className="mt-0.5 truncate text-[10px] opacity-90">{label[s]}</p>
                  </div>
                ))}
              </div>
              <div className="mt-4 flex flex-wrap gap-x-4 gap-y-1.5 border-t border-white/10 pt-3 text-[11px] text-teal-100/60">
                {(Object.keys(STATE_CLS) as State[]).map((s) => (
                  <span key={s} className="inline-flex items-center gap-1.5">
                    <span className={`h-2 w-2 rounded-sm border ${STATE_CLS[s]}`} />
                    {label[s]}
                  </span>
                ))}
              </div>
            </div>
            <figcaption className="mt-3 text-center text-xs text-text-secondary">{t("caption")}</figcaption>
          </figure>
        </div>
      </Container>
    </section>
  );
}
