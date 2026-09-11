"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import {
  TrendingUp,
  ShoppingCart,
  Armchair,
  UtensilsCrossed,
  Wallet,
  ChefHat,
  ChevronRight,
  CheckCircle2,
  Circle,
} from "lucide-react";
import { Link } from "@/i18n/routing";
import {
  branchesApi,
  menuApi,
  ordersApi,
  restaurantsApi,
  tablesApi,
  BranchOut,
} from "@/lib/api";
import type { LoadState } from "@/lib/load-state";
import { loadingState, errorState, dataState } from "@/lib/load-state";
import { formatMoney } from "@/lib/format";
import { useAuth } from "@/lib/auth-context";
import StateView from "@/components/dashboard/StateView";

interface OverviewData {
  currency: string;
  branchName: string;
  todayRevenue: string;
  openOrders: number;
  occupiedTables: number;
  totalTables: number;
  totalProducts: number;
  hasOrders: boolean;
}

export default function DashboardOverviewPage() {
  const t = useTranslations("shell.overview");
  const { user } = useAuth();
  const [state, setState] = useState<LoadState<OverviewData>>(loadingState());

  useEffect(() => {
    void (async () => {
      try {
        const [restaurant, branches, ordersPage, tables, emptyMenuPage] =
          await Promise.all([
            restaurantsApi.getMine(),
            branchesApi.list().catch(() => [] as BranchOut[]),
            // Backend caps this endpoint's limit at 100 (Query(..., le=100)).
            ordersApi.list({ limit: 100 }),
            tablesApi.list(),
            menuApi.listProducts(1, 0),
          ]);

        const now = new Date();
        const startOfToday = new Date(
          now.getFullYear(),
          now.getMonth(),
          now.getDate()
        ).toISOString();
        const todayRevenue = ordersPage.items
          .filter((o) => o.created_at >= startOfToday)
          .reduce((sum, o) => sum + parseFloat(o.total), 0);

        setState(
          dataState({
            currency: restaurant.currency,
            branchName: branches[0]?.name ?? "—",
            todayRevenue: todayRevenue.toFixed(2),
            openOrders: ordersPage.items.filter((o) =>
              ["DRAFT", "OPEN", "PARTIALLY_PAID"].includes(o.status)
            ).length,
            occupiedTables: tables.filter((t) => t.status === "OCCUPIED").length,
            totalTables: tables.length,
            totalProducts: emptyMenuPage.total,
            hasOrders: ordersPage.items.length > 0,
          })
        );
      } catch (err) {
        setState(errorState(err instanceof Error ? err.message : t("loadError")));
      }
    })();
  }, [t]);

  const stats = [
    {
      label: t("todayRevenue"),
      value:
        state.type === "data"
          ? formatMoney(state.data.todayRevenue, state.data.currency)
          : "—",
      icon: TrendingUp,
      tone: "success" as const,
    },
    {
      label: t("openOrders"),
      value: state.type === "data" ? String(state.data.openOrders) : "—",
      icon: ShoppingCart,
      tone: "accent" as const,
    },
    {
      label: t("tablesOccupied"),
      value:
        state.type === "data"
          ? `${state.data.occupiedTables}/${state.data.totalTables}`
          : "—",
      icon: Armchair,
      tone: "ai" as const,
    },
    {
      label: t("menuItems"),
      value: state.type === "data" ? String(state.data.totalProducts) : "—",
      icon: UtensilsCrossed,
      tone: "warning" as const,
    },
  ];

  const toneClasses: Record<string, string> = {
    success: "bg-success/10 text-success",
    accent: "bg-accent-primary/10 text-accent-primary",
    ai: "bg-accent-ai/10 text-accent-ai",
    warning: "bg-warning/10 text-warning",
  };

  const modules = [
    { label: t("menuLabel"), icon: UtensilsCrossed, href: "/dashboard/menu" as const },
    { label: t("ordersLabel"), icon: ShoppingCart, href: "/dashboard/orders" as const },
    { label: t("tablesLabel"), icon: Armchair, href: "/dashboard/tables" as const },
    { label: t("paymentsLabel"), icon: Wallet, href: "/dashboard/payments" as const },
  ];

  const steps =
    state.type === "data"
      ? [
          { label: t("stepRestaurantCreated"), done: true },
          { label: t("stepMenuAdded"), done: state.data.totalProducts > 0 },
          { label: t("stepTableAdded"), done: state.data.totalTables > 0 },
          { label: t("stepFirstOrder"), done: state.data.hasOrders },
        ]
      : [];
  const allStepsDone = steps.length > 0 && steps.every((s) => s.done);

  return (
    <div>
      {/* Welcome banner */}
      <div className="relative mb-6 overflow-hidden rounded-2xl bg-brand-gradient p-6 sm:p-8">
        <div className="ai-glow pointer-events-none absolute inset-0" aria-hidden="true" />
        <div
          className="grid-backdrop pointer-events-none absolute inset-0 opacity-10"
          aria-hidden="true"
        />
        <div className="relative">
          <p className="text-sm font-medium text-white/75">
            {t("welcome", { name: user?.full_name?.split(" ")[0] ?? "" })}
          </p>
          <h1 className="mt-1 text-2xl font-bold text-white sm:text-3xl">
            {user?.restaurant_name ?? t("title")}
          </h1>
          <p className="mt-2 text-sm text-white/75">
            {t("branch")}:{" "}
            {state.type === "data" ? state.data.branchName : "—"}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {stats.map((stat) => {
          const Icon = stat.icon;
          return (
            <div
              key={stat.label}
              className="rounded-xl border border-border-default bg-surface p-5 shadow-sm transition-shadow hover:shadow-md"
            >
              <div className="flex items-center justify-between">
                <p className="text-sm font-medium text-text-secondary">
                  {stat.label}
                </p>
                <div
                  className={`flex h-9 w-9 items-center justify-center rounded-lg ${toneClasses[stat.tone]}`}
                >
                  <Icon className="h-5 w-5" />
                </div>
              </div>
              <p className="mt-3 text-2xl font-bold text-text-primary">
                {stat.value}
              </p>
            </div>
          );
        })}
      </div>

      <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <section className="rounded-xl border border-border-default bg-surface p-5 lg:col-span-2">
          <h2 className="text-base font-semibold text-text-primary">
            {t("modulesTitle")}
          </h2>
          <p className="mt-1 text-sm text-text-secondary">{t("modulesText")}</p>
          <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
            {modules.map((mod) => {
              const MIcon = mod.icon;
              return (
                <Link
                  key={mod.label}
                  href={mod.href}
                  className="group flex items-center gap-3 rounded-lg border border-border-default px-4 py-3 transition-all hover:-translate-y-0.5 hover:border-accent-primary/40 hover:shadow-md"
                >
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-accent-primary/10 text-accent-primary transition-colors group-hover:bg-accent-primary group-hover:text-white">
                    <MIcon className="h-5 w-5" />
                  </div>
                  <span className="flex-1 text-sm font-medium text-text-primary">
                    {mod.label}
                  </span>
                  <ChevronRight className="h-4 w-4 shrink-0 text-text-secondary/50 transition-transform group-hover:translate-x-0.5 group-hover:text-accent-primary" />
                </Link>
              );
            })}
          </div>
        </section>

        <section className="rounded-xl border border-border-default bg-surface p-5">
          <h2 className="flex items-center gap-2 text-base font-semibold text-text-primary">
            <ChefHat className="h-4 w-4 text-accent-primary" aria-hidden="true" />
            {t("quickStart")}
          </h2>
          {state.type === "data" ? (
            <>
              <ul className="mt-4 space-y-3">
                {steps.map((step) => (
                  <li key={step.label} className="flex items-center gap-2.5 text-sm">
                    {step.done ? (
                      <CheckCircle2 className="h-4 w-4 shrink-0 text-success" />
                    ) : (
                      <Circle className="h-4 w-4 shrink-0 text-text-secondary/30" />
                    )}
                    <span
                      className={
                        step.done
                          ? "text-text-secondary line-through decoration-text-secondary/40"
                          : "font-medium text-text-primary"
                      }
                    >
                      {step.label}
                    </span>
                  </li>
                ))}
              </ul>
              {allStepsDone && (
                <p className="mt-4 rounded-lg bg-success/10 px-3 py-2 text-xs font-medium text-success">
                  {t("allSet")}
                </p>
              )}
            </>
          ) : (
            <div className="mt-4">
              <StateView
                kind={state.type}
                message={state.type === "error" ? state.message : undefined}
              />
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
