"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Search, Phone } from "lucide-react";
import { CustomerDetailOut, CustomerOut, customersApi } from "@/lib/api";
import { formatMoney, formatDateTime } from "@/lib/format";
import type { LoadState } from "@/lib/load-state";
import { loadingState, errorState, dataState } from "@/lib/load-state";
import Modal from "@/components/Modal";
import StateView from "@/components/dashboard/StateView";
import PageHeader from "@/components/dashboard/PageHeader";
import PlanGate from "@/components/dashboard/PlanGate";

function CustomersPageContent() {
  const t = useTranslations("customersPage");
  const tc = useTranslations("common");

  const [customers, setCustomers] = useState<LoadState<CustomerOut[]>>(loadingState());
  const [search, setSearch] = useState("");
  const [detailId, setDetailId] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const list = await customersApi.list(search || undefined);
      setCustomers(dataState(list));
    } catch (err) {
      setCustomers(errorState((err as Error).message));
    }
  }, [search]);

  useEffect(() => {
    const timer = setTimeout(() => void load(), 250);
    return () => clearTimeout(timer);
  }, [load]);

  const list = customers.type === "data" ? customers.data : [];

  return (
    <div>
      <PageHeader title={t("title")} description={t("description")} />

      <div className="relative mb-5 max-w-sm">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-secondary" />
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder={t("searchPlaceholder")}
          className="w-full rounded-lg border border-border-default bg-surface py-2 pl-9 pr-3 text-sm text-text-primary outline-none focus:border-accent-primary"
        />
      </div>

      {customers.type === "data" ? (
        list.length === 0 ? (
          <StateView kind="empty" message={t("empty")} />
        ) : (
          <div className="overflow-hidden rounded-xl border border-border-default bg-surface">
            <ul className="divide-y divide-border-default">
              {list.map((c) => (
                <li key={c.id}>
                  <button
                    onClick={() => setDetailId(c.id)}
                    className="flex w-full items-center gap-3 px-5 py-4 text-left hover:bg-background"
                  >
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-brand-gradient text-sm font-bold text-white">
                      {(c.full_name ?? "?").charAt(0).toUpperCase()}
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-medium text-text-primary">
                        {c.full_name || t("unnamed")}
                      </p>
                      {c.phone && (
                        <p className="flex items-center gap-1 text-xs text-text-secondary">
                          <Phone className="h-3 w-3" />
                          {c.phone}
                        </p>
                      )}
                    </div>
                    <span className="text-xs text-text-secondary">{formatDateTime(c.created_at)}</span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )
      ) : (
        <StateView
          kind={customers.type}
          message={customers.type === "error" ? customers.message : undefined}
          onRetry={customers.type === "error" ? () => load() : undefined}
        />
      )}

      {detailId && <CustomerDetailModal id={detailId} onClose={() => setDetailId(null)} />}
    </div>
  );
}

function CustomerDetailModal({ id, onClose }: { id: string; onClose: () => void }) {
  const t = useTranslations("customersPage");
  const [detail, setDetail] = useState<CustomerDetailOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    customersApi
      .get(id)
      .then(setDetail)
      .catch((err) => setError((err as Error).message));
  }, [id]);

  return (
    <Modal open onClose={onClose} title={detail?.customer.full_name || t("unnamed")}>
      {error ? (
        <p className="text-sm text-error">{error}</p>
      ) : !detail ? (
        <p className="text-sm text-text-secondary">{t("loading")}</p>
      ) : (
        <div className="space-y-4">
          {detail.customer.phone && (
            <p className="flex items-center gap-1.5 text-sm text-text-secondary">
              <Phone className="h-3.5 w-3.5" />
              {detail.customer.phone}
            </p>
          )}

          <div className="grid grid-cols-2 gap-3">
            <StatTile label={t("totalOrders")} value={String(detail.total_orders)} />
            <StatTile label={t("totalSpent")} value={formatMoney(detail.total_spent, "UZS")} />
            <StatTile
              label={t("lastVisit")}
              value={detail.last_visit ? formatDateTime(detail.last_visit) : "—"}
            />
            <StatTile
              label={t("favoriteProducts")}
              value={detail.favorite_products.slice(0, 2).join(", ") || "—"}
            />
          </div>

          <div>
            <p className="mb-2 text-sm font-semibold text-text-primary">{t("recentOrders")}</p>
            {detail.recent_orders.length === 0 ? (
              <p className="text-sm text-text-secondary">{t("noOrders")}</p>
            ) : (
              <ul className="space-y-1.5">
                {detail.recent_orders.map((o) => (
                  <li
                    key={o.id}
                    className="flex items-center justify-between rounded-lg border border-border-default px-3 py-2 text-sm"
                  >
                    <span className="text-text-primary">#{o.order_number}</span>
                    <span className="text-text-secondary">{formatDateTime(o.created_at)}</span>
                    <span className="font-semibold text-text-primary">{formatMoney(o.total, "UZS")}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </Modal>
  );
}

function StatTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-border-default bg-background p-3">
      <p className="text-xs text-text-secondary">{label}</p>
      <p className="mt-0.5 text-base font-bold text-text-primary">{value}</p>
    </div>
  );
}

export default function CustomersPage() {
  return (
    <PlanGate feature="crm">
      <CustomersPageContent />
    </PlanGate>
  );
}
