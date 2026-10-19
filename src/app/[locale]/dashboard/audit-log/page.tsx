"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { ClipboardList } from "lucide-react";
import { AuditLogOut, auditApi } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { LoadState } from "@/lib/load-state";
import { loadingState, errorState, dataState } from "@/lib/load-state";
import StateView from "@/components/dashboard/StateView";
import PageHeader from "@/components/dashboard/PageHeader";

const ACTIONS = [
  "order.discount",
  "order.cancelled",
  "order.refunded",
  "staff.role_change",
  "staff.activate",
  "staff.deactivate",
  "staff.password_reset",
  "product.price_update",
];

export default function AuditLogPage() {
  const t = useTranslations("auditLogPage");

  const [entries, setEntries] = useState<LoadState<AuditLogOut[]>>(loadingState());
  const [actionFilter, setActionFilter] = useState<string | null>(null);

  const load = useCallback(async () => {
    setEntries(loadingState());
    try {
      const list = await auditApi.list({ action: actionFilter ?? undefined });
      setEntries(dataState(list));
    } catch (err) {
      setEntries(errorState((err as Error).message));
    }
  }, [actionFilter]);

  useEffect(() => {
    void load();
  }, [load]);

  const label = (action: string) => {
    try {
      return t(`action.${action.replace(".", "_")}` as Parameters<typeof t>[0]);
    } catch {
      return action;
    }
  };

  return (
    <div>
      <PageHeader title={t("title")} description={t("description")} />

      <div className="mb-5 flex flex-wrap items-center gap-2">
        <button
          onClick={() => setActionFilter(null)}
          className={`rounded-full px-3 py-1.5 text-xs font-semibold transition-colors ${
            actionFilter === null
              ? "bg-accent-primary/10 text-accent-primary"
              : "bg-background-secondary text-text-secondary hover:text-text-primary"
          }`}
        >
          {t("filterAll")}
        </button>
        {ACTIONS.map((action) => (
          <button
            key={action}
            onClick={() => setActionFilter(action)}
            className={`rounded-full px-3 py-1.5 text-xs font-semibold transition-colors ${
              actionFilter === action
                ? "bg-accent-primary/10 text-accent-primary"
                : "bg-background-secondary text-text-secondary hover:text-text-primary"
            }`}
          >
            {label(action)}
          </button>
        ))}
      </div>

      {entries.type === "data" ? (
        entries.data.length === 0 ? (
          <StateView kind="empty" message={t("empty")} />
        ) : (
          <div className="overflow-hidden rounded-xl border border-border-default bg-surface">
            <ul className="divide-y divide-border-default">
              {entries.data.map((entry) => (
                <li key={entry.id} className="flex items-start gap-3 px-5 py-4">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-background-secondary text-text-secondary">
                    <ClipboardList className="h-4 w-4" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="font-medium text-text-primary">{entry.summary}</p>
                    <p className="mt-0.5 text-xs text-text-secondary">
                      {label(entry.action)} · {formatDateTime(entry.created_at)}
                    </p>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        )
      ) : (
        <StateView
          kind={entries.type}
          message={entries.type === "error" ? entries.message : undefined}
          onRetry={entries.type === "error" ? () => load() : undefined}
        />
      )}
    </div>
  );
}
