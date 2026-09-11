"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Plus, Pencil, Table2, Armchair } from "lucide-react";
import { BranchOut, TableOut, branchesApi, tablesApi } from "@/lib/api";
import type { LoadState } from "@/lib/load-state";
import { loadingState, errorState, dataState } from "@/lib/load-state";
import { useAuth } from "@/lib/auth-context";
import Modal from "@/components/Modal";
import Button from "@/components/Button";
import StateView from "@/components/dashboard/StateView";
import PageHeader from "@/components/dashboard/PageHeader";

const TABLE_STATUSES = ["AVAILABLE", "OCCUPIED", "RESERVED", "DISABLED"] as const;

const STATUS_STYLES: Record<string, string> = {
  AVAILABLE: "bg-success/10 text-success",
  OCCUPIED: "bg-warning/10 text-warning",
  RESERVED: "bg-accent-primary/10 text-accent-primary",
  DISABLED: "bg-background-secondary text-text-secondary",
};

// Card-level wash so a table's status reads at a glance, not just from its badge.
const STATUS_CARD_STYLES: Record<string, string> = {
  AVAILABLE: "border-success/25 bg-success/[0.04]",
  OCCUPIED: "border-warning/25 bg-warning/[0.04]",
  RESERVED: "border-accent-primary/25 bg-accent-primary/[0.04]",
  DISABLED: "border-border-default bg-background-secondary/50",
};

const MAX_SEAT_ICONS = 6;

export default function TablesPage() {
  const t = useTranslations("tablesPage");
  const tc = useTranslations("common");
  const { can } = useAuth();

  const [branches, setBranches] = useState<BranchOut[]>([]);
  const [branchId, setBranchId] = useState<string | null>(null);
  const [tables, setTables] = useState<LoadState<TableOut[]>>(loadingState());
  const [statusFilter, setStatusFilter] = useState<string | null>(null);
  const [modal, setModal] = useState<
    { type: "create" } | { type: "edit"; table: TableOut } | null
  >(null);
  const [notice, setNotice] = useState<string | null>(null);

  const canCreate = can("users.manage");
  const canUpdate = can("orders.read");

  const loadTables = useCallback(async () => {
    try {
      const list = await tablesApi.list(branchId ?? undefined);
      setTables(dataState(list));
    } catch (err) {
      setTables(errorState((err as Error).message));
    }
  }, [branchId]);

  useEffect(() => {
    void (async () => {
      try {
        const list = await branchesApi.list();
        setBranches(list);
        setBranchId((prev) => prev ?? list[0]?.id ?? null);
      } catch {
        setBranches([]);
      }
    })();
  }, []);

  useEffect(() => {
    if (branchId === null) return;
    void (async () => {
      try {
        const list = await tablesApi.list(branchId ?? undefined);
        setTables(dataState(list));
      } catch (err) {
        setTables(errorState((err as Error).message));
      }
    })();
  }, [branchId]);

  const flash = (message: string) => {
    setNotice(message);
    setTimeout(() => setNotice(null), 3000);
  };

  const handleCreate = async (name: string, capacity: number) => {
    if (!branchId) return;
    try {
      await tablesApi.create({ branch_id: branchId, name, capacity });
      setModal(null);
      flash(tc("actions.saved"));
      loadTables();
    } catch (err) {
      alert((err as Error).message);
    }
  };

  const handleUpdate = async (table: TableOut, updates: {
    name?: string;
    capacity?: number;
    status?: string;
  }) => {
    try {
      await tablesApi.update(table.id, updates);
      setModal(null);
      flash(tc("actions.saved"));
      loadTables();
    } catch (err) {
      alert((err as Error).message);
    }
  };

  const shown = (tables.type === "data" ? tables.data : []).filter(
    (table) => !statusFilter || table.status === statusFilter
  );

  const statusToText = (status: string) =>
    (tc(`tableStatus.${status}`) ?? status);

  const counts = {
    total: tables.type === "data" ? tables.data.length : 0,
    byStatus: (status: string) =>
      tables.type === "data"
        ? tables.data.filter((tb) => tb.status === status).length
        : 0,
  };

  return (
    <div>
      <PageHeader
        title={t("title")}
        description={t("description")}
        actions={
          canCreate ? (
            <Button size="sm" onClick={() => setModal({ type: "create" })}>
              <Plus className="h-4 w-4" />
              {t("addTable")}
            </Button>
          ) : undefined
        }
      />

      {notice && (
        <div className="mb-4 rounded-lg border border-success/30 bg-success/10 px-4 py-2 text-sm text-success">
          {notice}
        </div>
      )}

      {/* Branch + status controls */}
      <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center">
        <select
          value={branchId ?? ""}
          onChange={(e) => setBranchId(e.target.value || null)}
          className="rounded-lg border border-border-default bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent-primary"
        >
          {branches.length === 0 && <option value="">—</option>}
          {branches.map((b) => (
            <option key={b.id} value={b.id}>
              {b.name}
            </option>
          ))}
        </select>

        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={() => setStatusFilter(null)}
            className={`rounded-full px-3 py-1.5 text-xs font-semibold transition-colors ${
              statusFilter === null
                ? "bg-accent-primary/10 text-accent-primary"
                : "bg-background-secondary text-text-secondary hover:text-text-primary"
            }`}
          >
            {t("filterAll")} ({counts.total})
          </button>
          {TABLE_STATUSES.map((status) => (
            <button
              key={status}
              onClick={() => setStatusFilter(status)}
              className={`rounded-full px-3 py-1.5 text-xs font-semibold capitalize transition-colors ${
                statusFilter === status
                  ? "bg-accent-primary/10 text-accent-primary"
                  : "bg-background-secondary text-text-secondary hover:text-text-primary"
              }`}
            >
              {statusToText(status)} ({counts.byStatus(status)})
            </button>
          ))}
        </div>
      </div>

      {tables.type === "data" ? (
        shown.length === 0 ? (
          <StateView kind="empty" message={t("noTables")} />
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {shown.map((table) => (
              <div
                key={table.id}
                className={`group relative flex flex-col rounded-xl border p-4 shadow-sm transition-all hover:-translate-y-0.5 hover:shadow-md ${
                  STATUS_CARD_STYLES[table.status] ??
                  "border-border-default bg-surface"
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div
                    className={`flex h-12 w-12 items-center justify-center rounded-xl ${STATUS_STYLES[table.status] ?? "bg-background-secondary text-text-secondary"}`}
                  >
                    <Table2 className="h-6 w-6" />
                  </div>
                  <span
                    className={`rounded-full px-2.5 py-1 text-xs font-semibold capitalize ${STATUS_STYLES[table.status] ?? "bg-background-secondary text-text-secondary"}`}
                  >
                    {statusToText(table.status)}
                  </span>
                </div>

                <p className="mt-3 font-semibold text-text-primary">
                  {table.name}
                </p>
                <div className="mt-1.5 flex items-center gap-1 text-text-secondary">
                  {Array.from({
                    length: Math.min(table.capacity, MAX_SEAT_ICONS),
                  }).map((_, i) => (
                    <Armchair key={i} className="h-3.5 w-3.5" aria-hidden="true" />
                  ))}
                  {table.capacity > MAX_SEAT_ICONS && (
                    <span className="text-xs font-medium">
                      +{table.capacity - MAX_SEAT_ICONS}
                    </span>
                  )}
                  <span className="sr-only">
                    {t("capacity")}: {table.capacity}
                  </span>
                </div>

                {(canUpdate || canCreate) && (
                  <div className="mt-3 flex justify-end gap-1">
                    <button
                      onClick={() => setModal({ type: "edit", table })}
                      aria-label={t("editTable")}
                      className="flex h-7 w-7 items-center justify-center rounded-lg text-text-secondary hover:bg-surface hover:text-accent-primary"
                    >
                      <Pencil className="h-3.5 w-3.5" />
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )
      ) : (
        <StateView
          kind={tables.type}
          message={tables.type === "error" ? tables.message : undefined}
          onRetry={tables.type === "error" ? () => loadTables() : undefined}
        />
      )}

      {modal?.type === "create" && (
        <TableFormModal
          title={t("addTable")}
          onClose={() => setModal(null)}
          onSubmit={(name, capacity) => handleCreate(name, capacity)}
        />
      )}

      {modal?.type === "edit" && (
        <TableFormModal
          title={t("editTable")}
          initial={modal.table}
          onClose={() => setModal(null)}
          onSubmit={(name, capacity, status) =>
            handleUpdate(modal.table, {
              ...(name && name !== modal.table.name ? { name } : {}),
              ...(capacity !== modal.table.capacity ? { capacity } : {}),
              ...(status && status !== modal.table.status ? { status } : {}),
            })
          }
        />
      )}
    </div>
  );
}

function TableFormModal({
  title,
  initial,
  onClose,
  onSubmit,
}: {
  title: string;
  initial?: TableOut;
  onClose: () => void;
  onSubmit: (name: string, capacity: number, status: string) => void;
}) {
  const t = useTranslations("tablesPage");
  const tc = useTranslations("common");
  const [name, setName] = useState(initial?.name ?? "");
  const [capacity, setCapacity] = useState(String(initial?.capacity ?? 2));
  const [status, setStatus] = useState(initial?.status ?? "AVAILABLE");

  return (
    <Modal open onClose={onClose} title={title}>
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          onSubmit(name.trim(), parseInt(capacity, 10) || 1, status);
        }}
      >
        <div>
          <label className="mb-1 block text-sm font-medium text-text-primary">
            {t("tableName")}
          </label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={t("tableNamePlaceholder")}
            required
            className="w-full rounded-lg border border-border-default bg-background px-3 py-2 text-sm text-text-primary outline-none focus:border-accent-primary"
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-text-primary">
            {t("capacity")}
          </label>
          <input
            type="number"
            min={1}
            value={capacity}
            onChange={(e) => setCapacity(e.target.value)}
            className="w-full rounded-lg border border-border-default bg-background px-3 py-2 text-sm text-text-primary outline-none focus:border-accent-primary"
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-text-primary">
            {t("status")}
          </label>
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="w-full rounded-lg border border-border-default bg-background px-3 py-2 text-sm text-text-primary outline-none focus:border-accent-primary"
          >
            {TABLE_STATUSES.map((s) => (
              <option key={s} value={s}>
                {tc(`tableStatus.${s}`)}
              </option>
            ))}
          </select>
        </div>
        <div className="flex justify-end gap-2">
          <Button variant="secondary" size="sm" onClick={onClose}>
            {tc("actions.cancel")}
          </Button>
          <Button type="submit" size="sm">
            {tc("actions.save")}
          </Button>
        </div>
      </form>
    </Modal>
  );
}