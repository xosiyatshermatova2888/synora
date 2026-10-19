"use client";

import { useTranslations } from "next-intl";

const BARS = [38, 52, 44, 66, 58, 80, 72, 92, 70, 84, 96, 78];

const ROWS: { table: string; amount: string; tone: "paid" | "waiting" | "ordered" }[] = [
  { table: "3", amount: "48 000", tone: "paid" },
  { table: "7", amount: "125 000", tone: "waiting" },
  { table: "12", amount: "67 000", tone: "ordered" },
];

const TONE_CLS = {
  paid: "text-emerald-300",
  waiting: "text-amber-300",
  ordered: "text-sky-300",
} as const;

/**
 * Decorative product illustration for the hero (browser frame + a miniature
 * dashboard). The figures are sample values, not live data — the caption says so.
 */
export default function HeroMockup() {
  const t = useTranslations("hero");
  const tn = useTranslations("shell.nav");
  const to = useTranslations("shell.overview");
  const tt = useTranslations("tablesPage");
  const tc = useTranslations("common");
  const tor = useTranslations("ordersPage");

  const rowLabel = {
    paid: tc("paymentStatus.PAID"),
    waiting: tt("awaitingPayment"),
    ordered: tt("stateOrdered"),
  };

  return (
    <figure className="relative" aria-label={t("mockCaption")}>
      <div className="absolute -inset-6 rounded-[2rem] bg-[radial-gradient(ellipse_at_center,rgba(25,179,166,0.22),transparent_70%)]" aria-hidden="true" />
      <div className="relative overflow-hidden rounded-2xl border border-white/10 bg-[#0a1e21] shadow-[0_30px_80px_-20px_rgba(0,0,0,0.7)]" aria-hidden="true">
        <div className="flex items-center gap-1.5 border-b border-white/10 bg-[#0d2428] px-4 py-2.5">
          <span className="h-2.5 w-2.5 rounded-full bg-red-400/80" />
          <span className="h-2.5 w-2.5 rounded-full bg-amber-300/80" />
          <span className="h-2.5 w-2.5 rounded-full bg-emerald-400/80" />
          <span className="ml-3 truncate text-[11px] text-teal-100/50">synora.uz/dashboard</span>
        </div>

        <div className="grid grid-cols-[110px_1fr] sm:grid-cols-[130px_1fr]">
          <div className="space-y-1 border-r border-white/10 bg-[#071619] p-3">
            {(["overview", "orders", "menu", "kitchen", "reports", "staff"] as const).map((k, i) => (
              <div
                key={k}
                className={`truncate rounded-md px-2.5 py-1.5 text-[11px] ${
                  i === 0 ? "bg-white/10 font-medium text-white" : "text-teal-100/60"
                }`}
              >
                {tn(k)}
              </div>
            ))}
          </div>

          <div className="space-y-3 p-4">
            <div className="rounded-xl bg-white/[0.05] p-3.5 ring-1 ring-white/10">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-teal-200/70">
                {to("revenue")} · {tc("ui.today")}
              </p>
              <div className="mt-1 flex items-end justify-between gap-3">
                <p className="tabular text-xl font-semibold text-white sm:text-2xl">4 820 000 <span className="text-xs font-normal text-teal-100/50">UZS</span></p>
              </div>
              <div className="mt-3 flex h-12 items-end gap-1">
                {BARS.map((h, i) => (
                  <span
                    key={i}
                    className="flex-1 rounded-t bg-gradient-to-t from-[#12a89b] to-[#a9cf3a]"
                    style={{ height: `${h}%` }}
                  />
                ))}
              </div>
            </div>

            <div className="grid grid-cols-3 gap-2">
              {[
                { label: to("ordersCount"), value: "47", cls: "text-[#a9cf3a]" },
                { label: to("avgCheck"), value: "102K", cls: "text-[#4fd1c5]" },
                { label: tn("tables"), value: "9/12", cls: "text-amber-300" },
              ].map((s) => (
                <div key={s.label} className="rounded-lg bg-white/[0.05] p-2.5 ring-1 ring-white/10">
                  <p className="truncate text-[10px] uppercase tracking-wide text-teal-100/50">{s.label}</p>
                  <p className={`tabular mt-0.5 text-base font-semibold ${s.cls}`}>{s.value}</p>
                </div>
              ))}
            </div>

            <div className="divide-y divide-white/5 rounded-lg bg-white/[0.04] ring-1 ring-white/10">
              {ROWS.map((r) => (
                <div key={r.table} className="flex items-center justify-between gap-2 px-3 py-2 text-[11px]">
                  <span className="text-teal-100/70">
                    {tor("table")} {r.table}
                  </span>
                  <span className={`font-medium ${TONE_CLS[r.tone]}`}>{rowLabel[r.tone]}</span>
                  <span className="tabular text-white/80">{r.amount}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
      <figcaption className="mt-3 text-center text-xs text-teal-100/40">{t("mockCaption")}</figcaption>
    </figure>
  );
}
