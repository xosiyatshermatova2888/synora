"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import {
  ShoppingCart,
  Armchair,
  Receipt,
  ChevronRight,
  CheckCircle2,
  Circle,
  AlertTriangle,
} from "lucide-react";
import { Link } from "@/i18n/routing";
import {
  InventoryItemOut,
  OrderOut,
  ProductReportRow,
  SalesPoint,
  inventoryApi,
  menuApi,
  ordersApi,
  reportsApi,
  restaurantsApi,
  tablesApi,
} from "@/lib/api";
import type { LoadState } from "@/lib/load-state";
import { loadingState, errorState, dataState } from "@/lib/load-state";
import { formatMoney, formatDateTime } from "@/lib/format";
import { useAuth } from "@/lib/auth-context";
import { useBranch } from "@/lib/branch-context";
import { useSubscription } from "@/lib/subscription-context";
import StateView from "@/components/dashboard/StateView";
import PageHeader from "@/components/dashboard/PageHeader";
import Tabs from "@/components/ui/Tabs";
import StatusBadge, { orderStatusTone } from "@/components/ui/StatusBadge";
import DailyBarChart from "@/components/dashboard/charts/DailyBarChart";
import RankedBars from "@/components/dashboard/charts/RankedBars";
import DonutChart from "@/components/dashboard/charts/DonutChart";

type Period = "today" | "last7" | "last30";

interface OverviewData {
  currency: string;
  revenue: number;
  orderCount: number;
  occupiedTables: number;
  totalTables: number;
  totalProducts: number;
  series: SalesPoint[];
  topProducts: ProductReportRow[];
  recentOrders: OrderOut[];
  statusCounts: Record<string, number>;
  lowStock: InventoryItemOut[];
  branchRevenue: { name: string; revenue: number }[];
  hasAnalytics: boolean;
}

function ymd(d: Date): string {
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${m}-${day}`;
}

function rangeFor(period: Period): { from: string; to: string } {
  const to = new Date();
  const from = new Date();
  if (period === "last7") from.setDate(from.getDate() - 6);
  if (period === "last30") from.setDate(from.getDate() - 29);
  return { from: ymd(from), to: ymd(to) };
}

const STATUS_COLOR: Record<string, string> = {
  OPEN: "var(--color-info)",
  COMPLETED: "var(--color-success)",
  PARTIALLY_PAID: "var(--color-warning)",
  CANCELLED: "var(--color-error)",
  REFUNDED: "#9b2c2c",
  DRAFT: "#9aa4b2",
};

export default function DashboardOverviewPage() {
  const t = useTranslations("shell.overview");
  const tc = useTranslations("common");
  const { user, can } = useAuth();
  const { branches, selectedBranchId } = useBranch();
  const [period, setPeriod] = useState<Period>("today");
  const [state, setState] = useState<LoadState<OverviewData>>(loadingState());
  const [reloadKey, setReloadKey] = useState(0);

  const hasAnalytics = can("analytics.read");
  const canInventory = can("inventory.read");
  const { subscription, has } = useSubscription();
  // Inventory is a Pro feature: don't request it (a 402) on a plan without it.
  const fetchInventory = canInventory && !!subscription && has("inventory");

  useEffect(() => {
    let cancelled = false;
    setState(loadingState());
    void (async () => {
      try {
        const branchId = selectedBranchId ?? undefined;
        const { from, to } = rangeFor(hasAnalytics ? period : "today");
        const startOfToday = new Date();
        startOfToday.setHours(0, 0, 0, 0);

        const [restaurant, ordersPage, tables, products] = await Promise.all([
          restaurantsApi.getMine(),
          ordersApi.list({ limit: 100, branch_id: branchId }),
          tablesApi.list(branchId),
          menuApi.listProducts(1, 0),
        ]);

        let revenue = 0;
        let orderCount = 0;
        let series: SalesPoint[] = [];
        let topProducts: ProductReportRow[] = [];
        let branchRevenue: { name: string; revenue: number }[] = [];

        if (hasAnalytics) {
          const range = { branch_id: branchId, date_from: from, date_to: to };
          const [sales, top] = await Promise.all([
            reportsApi.sales({ ...range, group_by: "day" }),
            reportsApi.products(range),
          ]);
          series = sales.points;
          revenue = sales.points.reduce((s, p) => s + parseFloat(p.revenue), 0);
          orderCount = sales.points.reduce((s, p) => s + p.order_count, 0);
          topProducts = top.slice(0, 5);
          if (branches.length > 1) {
            const perBranch = await Promise.all(
              branches.map((b) =>
                reportsApi
                  .sales({ branch_id: b.id, date_from: from, date_to: to, group_by: "day" })
                  .then((s) => ({
                    name: b.name,
                    revenue: s.points.reduce((sum, p) => sum + parseFloat(p.revenue), 0),
                  }))
                  .catch(() => ({ name: b.name, revenue: 0 }))
              )
            );
            branchRevenue = perBranch.sort((a, b) => b.revenue - a.revenue);
          }
        } else {
          // Roles without analytics.read (cashier, waiter): same-day slice of
          // the latest-100 orders, the only data they are allowed to see.
          const today = ordersPage.items.filter(
            (o) => new Date(o.created_at) >= startOfToday && o.status !== "CANCELLED"
          );
          revenue = today.reduce((s, o) => s + parseFloat(o.total), 0);
          orderCount = today.length;
        }

        const statusCounts: Record<string, number> = {};
        for (const o of ordersPage.items) statusCounts[o.status] = (statusCounts[o.status] ?? 0) + 1;

        const lowStock = fetchInventory
          ? (await inventoryApi.list(branchId).catch(() => [] as InventoryItemOut[])).filter(
              (i) => i.is_low_stock && i.is_active
            )
          : [];

        if (cancelled) return;
        setState(
          dataState({
            currency: restaurant.currency,
            revenue,
            orderCount,
            occupiedTables: tables.filter((x) => x.status === "OCCUPIED").length,
            totalTables: tables.length,
            totalProducts: products.total,
            series,
            topProducts,
            recentOrders: ordersPage.items.slice(0, 6),
            statusCounts,
            lowStock,
            branchRevenue,
            hasAnalytics,
          })
        );
      } catch (err) {
        if (!cancelled) setState(errorState(err instanceof Error ? err.message : t("loadError")));
      }
    })();
    return () => {
      cancelled = true;
    };
    // `branches` identity changes on reload only; period/branch drive refetches.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [period, selectedBranchId, hasAnalytics, fetchInventory, reloadKey, t]);

  const d = state.type === "data" ? state.data : null;
  const loading = state.type === "loading";
  const money = (v: number) => formatMoney(v.toFixed(2), d?.currency);
  const avgCheck = d && d.orderCount > 0 ? d.revenue / d.orderCount : 0;
  const periodLabel = period === "today" ? tc("ui.today") : period === "last7" ? tc("ui.last7") : tc("ui.last30");

  const steps = d
    ? [
        { label: t("stepRestaurantCreated"), done: true },
        { label: t("stepMenuAdded"), done: d.totalProducts > 0 },
        { label: t("stepTableAdded"), done: d.totalTables > 0 },
        { label: t("stepFirstOrder"), done: Object.keys(d.statusCounts).length > 0 },
      ]
    : [];
  const showOnboarding = steps.length > 0 && !steps.every((s) => s.done);

  return (
    <div>
      <PageHeader
        title={user?.restaurant_name ?? t("title")}
        description={t("welcome", { name: user?.full_name?.split(" ")[0] ?? "" })}
        actions={
          hasAnalytics ? (
            <Tabs
              value={period}
              onChange={(k) => setPeriod(k as Period)}
              items={[
                { key: "today", label: tc("ui.today") },
                { key: "last7", label: tc("ui.last7") },
                { key: "last30", label: tc("ui.last30") },
              ]}
            />
          ) : undefined
        }
      />

      {state.type === "error" ? (
        <div className="rounded-xl border border-border-default bg-surface">
          <StateView kind="error" message={state.message} onRetry={() => setReloadKey((k) => k + 1)} />
        </div>
      ) : (
        <>
          <section className="relative overflow-hidden rounded-2xl bg-[#0b1f22] p-5 text-white shadow-card sm:p-6">
            <div className="grid-backdrop pointer-events-none absolute inset-0 opacity-[0.07]" aria-hidden="true" />
            <div className="relative grid gap-6 lg:grid-cols-[1.1fr_1fr] lg:items-end">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wider text-teal-200/70">
                  {t("revenue")} · {periodLabel}
                </p>
                {loading ? (
                  <div className="mt-3 h-10 w-56 animate-pulse rounded-md bg-white/10" />
                ) : (
                  <p className="tabular mt-2 text-4xl font-semibold tracking-tight">
                    {d ? money(d.revenue) : "—"}
                  </p>
                )}
                <div className="mt-5 flex h-14 items-end gap-1" aria-hidden="true">
                  {(d?.series ?? []).slice(-24).map((p, i, arr) => {
                    const max = Math.max(1, ...arr.map((x) => parseFloat(x.revenue)));
                    return (
                      <span
                        key={i}
                        className="flex-1 rounded-t bg-gradient-to-t from-[#12a89b] to-[#a9cf3a]"
                        style={{ height: Math.max(4, (parseFloat(p.revenue) / max) * 56) }}
                      />
                    );
                  })}
                </div>
              </div>

              <div className="grid grid-cols-3 gap-3">
                {[
                  {
                    label: t("ordersCount"),
                    value: d ? String(d.orderCount) : "—",
                    icon: ShoppingCart,
                    tone: "text-[#a9cf3a]",
                  },
                  {
                    label: t("avgCheck"),
                    value: d ? money(avgCheck) : "—",
                    icon: Receipt,
                    tone: "text-[#4fd1c5]",
                  },
                  {
                    label: t("tablesOccupied"),
                    value: d ? `${d.occupiedTables}/${d.totalTables}` : "—",
                    icon: Armchair,
                    tone: "text-amber-300",
                  },
                ].map((tile) => (
                  <div key={tile.label} className="rounded-xl bg-white/[0.06] p-3 ring-1 ring-white/10">
                    <tile.icon className={`h-4 w-4 ${tile.tone}`} aria-hidden="true" />
                    <p className="mt-2 text-[11px] uppercase tracking-wide text-teal-100/60">{tile.label}</p>
                    <p className={`tabular mt-0.5 truncate text-lg font-semibold ${tile.tone}`}>
                      {loading ? "…" : tile.value}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          </section>

          <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-3">
            <section className="rounded-xl border border-border-default bg-surface p-5 shadow-card lg:col-span-2">
              <h2 className="text-[15px] font-semibold text-text-primary">{t("revenueOverTime")}</h2>
              <div className="mt-4">
                {loading ? (
                  <StateView kind="loading" />
                ) : d && d.hasAnalytics && d.series.length > 0 ? (
                  <DailyBarChart
                    points={d.series.map((p) => ({
                      label: p.bucket.slice(5),
                      value: parseFloat(p.revenue),
                    }))}
                    formatValue={money}
                  />
                ) : (
                  <StateView kind="empty" message={d?.hasAnalytics ? t("noSalesYet") : t("noAnalyticsAccess")} />
                )}
              </div>
            </section>

            <section className="rounded-xl border border-border-default bg-surface p-5 shadow-card">
              <h2 className="text-[15px] font-semibold text-text-primary">{t("statusDistribution")}</h2>
              <p className="mb-4 text-xs text-text-secondary">{t("statusNote")}</p>
              {loading ? (
                <StateView kind="loading" />
              ) : d && Object.keys(d.statusCounts).length > 0 ? (
                <DonutChart
                  centerLabel={t("ordersCount")}
                  segments={Object.entries(d.statusCounts).map(([status, value]) => ({
                    label: tc(`orderStatus.${status}` as "orderStatus.OPEN"),
                    value,
                    color: STATUS_COLOR[status] ?? "#9aa4b2",
                  }))}
                />
              ) : (
                <StateView kind="empty" message={t("noOrdersYet")} />
              )}
            </section>
          </div>

          <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-3">
            <section className="rounded-xl border border-border-default bg-surface p-5 shadow-card">
              <h2 className="mb-4 text-[15px] font-semibold text-text-primary">{t("topProducts")}</h2>
              {loading ? (
                <StateView kind="loading" />
              ) : d && d.topProducts.length > 0 ? (
                <RankedBars
                  rows={d.topProducts.map((p) => ({ label: p.product_name, value: p.quantity }))}
                  formatValue={(v) => t("pcs", { n: v })}
                />
              ) : (
                <StateView kind="empty" message={d?.hasAnalytics ? t("noSalesYet") : t("noAnalyticsAccess")} />
              )}
            </section>

            <section className="rounded-xl border border-border-default bg-surface shadow-card">
              <div className="flex items-center justify-between px-5 pt-5">
                <h2 className="text-[15px] font-semibold text-text-primary">{t("recentOrders")}</h2>
                <Link href="/dashboard/orders" className="flex items-center gap-0.5 text-xs font-medium text-accent-primary hover:underline">
                  {t("viewAll")}
                  <ChevronRight className="h-3.5 w-3.5" />
                </Link>
              </div>
              {loading ? (
                <StateView kind="loading" />
              ) : d && d.recentOrders.length > 0 ? (
                <ul className="mt-3 divide-y divide-border-default">
                  {d.recentOrders.map((o) => (
                    <li key={o.id} className="flex items-center gap-3 px-5 py-3">
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium text-text-primary">
                          #{o.order_number} <span className="font-normal text-text-secondary">· {o.source}</span>
                        </p>
                        <p className="text-xs text-text-secondary">{formatDateTime(o.created_at)}</p>
                      </div>
                      <div className="text-right">
                        <p className="tabular text-sm font-semibold text-text-primary">{formatMoney(o.total, o.currency)}</p>
                        <StatusBadge tone={orderStatusTone[o.status] ?? "neutral"}>
                          {tc(`orderStatus.${o.status}` as "orderStatus.OPEN")}
                        </StatusBadge>
                      </div>
                    </li>
                  ))}
                </ul>
              ) : (
                <StateView kind="empty" message={t("noOrdersYet")} />
              )}
            </section>

            <section className="rounded-xl border border-border-default bg-surface p-5 shadow-card">
              <div className="flex items-center justify-between">
                <h2 className="flex items-center gap-2 text-[15px] font-semibold text-text-primary">
                  <AlertTriangle className="h-4 w-4 text-warning" aria-hidden="true" />
                  {t("lowStock")}
                </h2>
                {canInventory && (
                  <Link href="/dashboard/inventory" className="text-xs font-medium text-accent-primary hover:underline">
                    {t("viewAll")}
                  </Link>
                )}
              </div>
              {loading ? (
                <StateView kind="loading" />
              ) : d && d.lowStock.length > 0 ? (
                <ul className="mt-3 space-y-2.5">
                  {d.lowStock.slice(0, 6).map((i) => (
                    <li key={i.id} className="flex items-center justify-between gap-3 text-sm">
                      <span className="truncate text-text-primary">{i.name}</span>
                      <span className="tabular shrink-0 font-medium text-warning">
                        {parseFloat(i.quantity)} {i.unit}
                      </span>
                    </li>
                  ))}
                </ul>
              ) : (
                <StateView kind="empty" message={canInventory ? t("noLowStock") : t("noAnalyticsAccess")} />
              )}
            </section>
          </div>

          {d && d.branchRevenue.length > 1 && (
            <section className="mt-4 rounded-xl border border-border-default bg-surface p-5 shadow-card">
              <h2 className="mb-4 text-[15px] font-semibold text-text-primary">{t("branchPerformance")}</h2>
              <RankedBars
                rows={d.branchRevenue.map((b) => ({ label: b.name, value: b.revenue }))}
                formatValue={money}
              />
            </section>
          )}

          {showOnboarding && (
            <section className="mt-4 rounded-xl border border-accent-primary/30 bg-accent-primary/5 p-5">
              <h2 className="text-[15px] font-semibold text-text-primary">{t("quickStart")}</h2>
              <ul className="mt-3 grid gap-2.5 sm:grid-cols-2">
                {steps.map((step) => (
                  <li key={step.label} className="flex items-center gap-2.5 text-sm">
                    {step.done ? (
                      <CheckCircle2 className="h-4 w-4 shrink-0 text-success" />
                    ) : (
                      <Circle className="h-4 w-4 shrink-0 text-text-secondary/40" />
                    )}
                    <span className={step.done ? "text-text-secondary line-through" : "font-medium text-text-primary"}>
                      {step.label}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </>
      )}
    </div>
  );
}
