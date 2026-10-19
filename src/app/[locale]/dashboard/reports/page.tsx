"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { TrendingUp, TrendingDown, Wallet } from "lucide-react";
import {
  ExpenseReportRow,
  PaymentReportRow,
  ProductReportRow,
  ProfitReportOut,
  SalesSeriesOut,
  WaiterReportRow,
  reportsApi,
} from "@/lib/api";
import { formatMoney } from "@/lib/format";
import { useBranch } from "@/lib/branch-context";
import { useSubscription } from "@/lib/subscription-context";
import { LockedPanel } from "@/components/dashboard/PlanGate";
import PageHeader from "@/components/dashboard/PageHeader";
import DailyBarChart from "@/components/dashboard/charts/DailyBarChart";
import RankedBars from "@/components/dashboard/charts/RankedBars";

type RangeKey = "today" | "yesterday" | "7d" | "30d" | "custom";

const PAYMENT_METHOD_COLORS: Record<string, string> = {
  CASH: "var(--color-accent-primary)",
  CARD: "var(--color-accent-ai)",
  TRANSFER: "var(--color-success)",
  QR: "var(--color-warning)",
};

function isoDate(d: Date): string {
  return d.toISOString().slice(0, 10);
}

function resolveRange(range: RangeKey, customFrom: string, customTo: string): { from: string; to: string } {
  const today = new Date();
  if (range === "today") return { from: isoDate(today), to: isoDate(today) };
  if (range === "yesterday") {
    const y = new Date(today);
    y.setDate(y.getDate() - 1);
    return { from: isoDate(y), to: isoDate(y) };
  }
  if (range === "7d") {
    const from = new Date(today);
    from.setDate(from.getDate() - 6);
    return { from: isoDate(from), to: isoDate(today) };
  }
  if (range === "30d") {
    const from = new Date(today);
    from.setDate(from.getDate() - 29);
    return { from: isoDate(from), to: isoDate(today) };
  }
  return { from: customFrom, to: customTo };
}

export default function ReportsPage() {
  const t = useTranslations("reportsPage");
  const tc = useTranslations("common");
  const { selectedBranchId } = useBranch();
  const { subscription, has } = useSubscription();
  const advanced = has("advanced_reports");
  const [currency] = useState("UZS");

  const [range, setRange] = useState<RangeKey>("7d");
  const [customFrom, setCustomFrom] = useState(() => isoDate(new Date()));
  const [customTo, setCustomTo] = useState(() => isoDate(new Date()));

  const [sales, setSales] = useState<SalesSeriesOut | null>(null);
  const [products, setProducts] = useState<ProductReportRow[]>([]);
  const [waiters, setWaiters] = useState<WaiterReportRow[]>([]);
  const [payments, setPayments] = useState<PaymentReportRow[]>([]);
  const [expenses, setExpenses] = useState<ExpenseReportRow[]>([]);
  const [profit, setProfit] = useState<ProfitReportOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  const { from, to } = useMemo(() => resolveRange(range, customFrom, customTo), [range, customFrom, customTo]);

  const load = useCallback(async () => {
    // Wait for the plan: waiter/expense/profit reports are Pro-only (402 on Business).
    if (!subscription) return;
    const params = { branch_id: selectedBranchId ?? undefined, date_from: from, date_to: to };
    try {
      const [s, p, w, pay, exp, prof] = await Promise.all([
        reportsApi.sales({ ...params, group_by: "day" }),
        reportsApi.products(params),
        advanced ? reportsApi.waiters(params) : Promise.resolve([] as WaiterReportRow[]),
        reportsApi.payments(params),
        advanced ? reportsApi.expenses(params) : Promise.resolve([] as ExpenseReportRow[]),
        advanced ? reportsApi.profit(params) : Promise.resolve(null),
      ]);
      setSales(s);
      setProducts(p);
      setWaiters(w);
      setPayments(pay);
      setExpenses(exp);
      setProfit(prof);
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    }
  }, [selectedBranchId, from, to, range, subscription, advanced]);

  useEffect(() => {
    void load();
  }, [load]);

  const RANGE_OPTIONS: { key: RangeKey; labelKey: string }[] = [
    { key: "today", labelKey: "today" },
    { key: "yesterday", labelKey: "yesterday" },
    { key: "7d", labelKey: "last7d" },
    { key: "30d", labelKey: "last30d" },
    { key: "custom", labelKey: "custom" },
  ];

  return (
    <div>
      <PageHeader title={t("title")} description={t("description")} />

      <div className="mb-5 flex flex-wrap items-center gap-2">
        {RANGE_OPTIONS.map((opt) => (
          <button
            key={opt.key}
            onClick={() => setRange(opt.key)}
            className={`rounded-full px-3 py-1.5 text-xs font-semibold transition-colors ${
              range === opt.key
                ? "bg-accent-primary/10 text-accent-primary"
                : "bg-background-secondary text-text-secondary hover:text-text-primary"
            }`}
          >
            {t(opt.labelKey)}
          </button>
        ))}
        {range === "custom" && (
          <div className="flex items-center gap-2">
            <input
              type="date"
              value={customFrom}
              onChange={(e) => setCustomFrom(e.target.value)}
              className="rounded-lg border border-border-default bg-surface px-2 py-1.5 text-xs text-text-primary outline-none focus:border-accent-primary"
            />
            <span className="text-text-secondary">—</span>
            <input
              type="date"
              value={customTo}
              onChange={(e) => setCustomTo(e.target.value)}
              className="rounded-lg border border-border-default bg-surface px-2 py-1.5 text-xs text-text-primary outline-none focus:border-accent-primary"
            />
          </div>
        )}
      </div>

      {error && (
        <div className="mb-4 rounded-lg border border-error/30 bg-error/10 px-4 py-2 text-sm text-error">
          {error}
        </div>
      )}

      {/* Profit summary tiles */}
      {!advanced && <LockedPanel feature="advanced_reports" className="mb-6" />}
      {profit && (
        <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div className="rounded-xl border border-border-default bg-surface p-4">
            <div className="flex items-center gap-2 text-text-secondary">
              <TrendingUp className="h-4 w-4 text-success" />
              <span className="text-sm">{t("revenue")}</span>
            </div>
            <p className="mt-1 text-xl font-bold text-text-primary">{formatMoney(profit.revenue, currency)}</p>
          </div>
          <div className="rounded-xl border border-border-default bg-surface p-4">
            <div className="flex items-center gap-2 text-text-secondary">
              <TrendingDown className="h-4 w-4 text-error" />
              <span className="text-sm">{t("expenses")}</span>
            </div>
            <p className="mt-1 text-xl font-bold text-text-primary">{formatMoney(profit.expenses, currency)}</p>
          </div>
          <div className="rounded-xl border border-border-default bg-surface p-4">
            <div className="flex items-center gap-2 text-text-secondary">
              <Wallet className="h-4 w-4 text-accent-primary" />
              <span className="text-sm">{t("profit")}</span>
            </div>
            <p className="mt-1 text-xl font-bold text-text-primary">{formatMoney(profit.profit, currency)}</p>
          </div>
        </div>
      )}

      {/* Sales trend */}
      <div className="mb-6 rounded-xl border border-border-default bg-surface p-4">
        <p className="mb-3 text-sm font-semibold text-text-primary">{t("salesTrend")}</p>
        {sales && sales.points.length > 0 ? (
          <DailyBarChart
            points={sales.points.map((p) => ({ label: p.bucket.slice(5), value: parseFloat(p.revenue) }))}
            formatValue={(v) => formatMoney(v.toFixed(2), currency)}
          />
        ) : (
          <p className="py-8 text-center text-sm text-text-secondary">{t("noData")}</p>
        )}
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="rounded-xl border border-border-default bg-surface p-4">
          <p className="mb-3 text-sm font-semibold text-text-primary">{t("bestSellers")}</p>
          {products.length > 0 ? (
            <RankedBars
              rows={products.slice(0, 8).map((p) => ({ label: p.product_name, value: parseFloat(p.revenue) }))}
              formatValue={(v) => formatMoney(v.toFixed(2), currency)}
            />
          ) : (
            <p className="py-6 text-center text-sm text-text-secondary">{t("noData")}</p>
          )}
        </div>

        <div className="rounded-xl border border-border-default bg-surface p-4">
          <p className="mb-3 text-sm font-semibold text-text-primary">{t("waiterSales")}</p>
          {!advanced ? (
            <LockedPanel feature="advanced_reports" />
          ) : waiters.length > 0 ? (
            <RankedBars
              rows={waiters.slice(0, 8).map((w) => ({ label: w.waiter_name, value: parseFloat(w.total_sales) }))}
              formatValue={(v) => formatMoney(v.toFixed(2), currency)}
              defaultColor="var(--color-accent-ai)"
            />
          ) : (
            <p className="py-6 text-center text-sm text-text-secondary">{t("noData")}</p>
          )}
        </div>

        <div className="rounded-xl border border-border-default bg-surface p-4">
          <p className="mb-3 text-sm font-semibold text-text-primary">{t("paymentMethods")}</p>
          {payments.length > 0 ? (
            <RankedBars
              rows={payments.map((p) => ({
                label: tc(`paymentMethod.${p.method}`),
                value: parseFloat(p.amount),
                color: PAYMENT_METHOD_COLORS[p.method],
              }))}
              formatValue={(v) => formatMoney(v.toFixed(2), currency)}
            />
          ) : (
            <p className="py-6 text-center text-sm text-text-secondary">{t("noData")}</p>
          )}
        </div>

        <div className="rounded-xl border border-border-default bg-surface p-4">
          <p className="mb-3 text-sm font-semibold text-text-primary">{t("expensesByCategory")}</p>
          {!advanced ? (
            <LockedPanel feature="advanced_reports" />
          ) : expenses.length > 0 ? (
            <RankedBars
              rows={expenses.map((e) => ({
                label: tc(`expenseCategory.${e.category}`),
                value: parseFloat(e.amount),
              }))}
              formatValue={(v) => formatMoney(v.toFixed(2), currency)}
              defaultColor="var(--color-warning)"
            />
          ) : (
            <p className="py-6 text-center text-sm text-text-secondary">{t("noData")}</p>
          )}
        </div>
      </div>
    </div>
  );
}
