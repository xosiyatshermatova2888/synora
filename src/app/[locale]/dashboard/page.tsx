"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import {
  TrendingUp,
  ShoppingCart,
  Armchair,
  UtensilsCrossed,
  Wallet,
} from "lucide-react";
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
import StateView from "@/components/dashboard/StateView";
import PageHeader from "@/components/dashboard/PageHeader";

interface OverviewData {
  currency: string;
  branchName: string;
  todayRevenue: string;
  openOrders: number;
  occupiedTables: number;
  totalTables: number;
  totalProducts: number;
}

export default function DashboardOverviewPage() {
  const t = useTranslations("shell.overview");
  const [state, setState] = useState<LoadState<OverviewData>>(loadingState());

  useEffect(() => {
    void (async () => {
      try {
        const [restaurant, branches, ordersPage, tables, emptyMenuPage] =
          await Promise.all([
            restaurantsApi.getMine(),
            branchesApi.list().catch(() => [] as BranchOut[]),
            ordersApi.list({ limit: 200 }),
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
    },
    {
      label: t("openOrders"),
      value: state.type === "data" ? String(state.data.openOrders) : "—",
      icon: ShoppingCart,
    },
    {
      label: t("tablesOccupied"),
      value:
        state.type === "data"
          ? `${state.data.occupiedTables}/${state.data.totalTables}`
          : "—",
      icon: Armchair,
    },
    {
      label: t("menuItems"),
      value: state.type === "data" ? String(state.data.totalProducts) : "—",
      icon: UtensilsCrossed,
    },
  ];

  return (
    <div>
      <PageHeader
        title={t("title")}
        description={
          state.type === "data" ? `${t("branch")}: ${state.data.branchName}` : t("title")
        }
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {stats.map((stat) => {
          const Icon = stat.icon;
          return (
            <div
              key={stat.label}
              className="rounded-xl border border-border-default bg-surface p-5"
            >
              <div className="flex items-center justify-between">
                <p className="text-sm font-medium text-text-secondary">
                  {stat.label}
                </p>
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent-primary/10">
                  <Icon className="h-5 w-5 text-accent-primary" />
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
            {[
              { label: t("menuLabel"), icon: UtensilsCrossed },
              { label: t("ordersLabel"), icon: ShoppingCart },
              { label: t("tablesLabel"), icon: Armchair },
              { label: t("paymentsLabel"), icon: Wallet },
            ].map((mod) => {
              const MIcon = mod.icon;
              return (
                <div
                  key={mod.label}
                  className="flex items-center gap-3 rounded-lg border border-border-default px-4 py-3"
                >
                  <MIcon className="h-5 w-5 text-accent-primary" />
                  <span className="text-sm font-medium text-text-primary">
                    {mod.label}
                  </span>
                </div>
              );
            })}
          </div>
        </section>

        <section className="rounded-xl border border-border-default bg-surface p-5">
          <h2 className="text-base font-semibold text-text-primary">
            {t("statusTitle")}
          </h2>
          <div className="mt-4 space-y-3">
            {state.type === "data" ? (
              <>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-text-secondary">
                    {t("todayRevenue")}
                  </span>
                  <span className="font-semibold text-text-primary">
                    {formatMoney(state.data.todayRevenue, state.data.currency)}
                  </span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-text-secondary">{t("openOrders")}</span>
                  <span className="font-semibold text-text-primary">
                    {state.data.openOrders}
                  </span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-text-secondary">
                    {t("occupiedTables")}
                  </span>
                  <span className="font-semibold text-text-primary">
                    {state.data.occupiedTables}
                  </span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-text-secondary">{t("menuItems")}</span>
                  <span className="font-semibold text-text-primary">
                    {state.data.totalProducts}
                  </span>
                </div>
              </>
            ) : (
              <StateView
                kind={state.type}
                message={state.type === "error" ? state.message : undefined}
              />
            )}
          </div>
        </section>
      </div>
    </div>
  );
}