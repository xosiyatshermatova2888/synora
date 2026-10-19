"use client";

import { useCallback, useEffect, useState } from "react";
import { useLiveReload } from "@/lib/use-live-reload";
import { useTranslations } from "next-intl";
import { Plus, Pencil, Table2, Armchair, ArrowRightLeft, Combine } from "lucide-react";
import { OrderOut, TableOut, ordersApi, tablesApi } from "@/lib/api";
import { formatMoney } from "@/lib/format";
import { useBranch } from "@/lib/branch-context";
import Tabs from "@/components/ui/Tabs";
import StatusBadge, { Tone } from "@/components/ui/StatusBadge";
import { useToast } from "@/components/ui/Toast";
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

const FLOOR_ICON: Record<Tone, string> = {
  success: "bg-success/15 text-success",
  warning: "bg-warning/15 text-warning",
  info: "bg-info/15 text-info",
  accent: "bg-accent-primary/15 text-accent-primary",
  error: "bg-error/15 text-error",
  neutral: "bg-background-secondary text-text-secondary",
};

const FLOOR_CARD: Record<Tone, string> = {
  success: "border-success/30 bg-success/[0.05]",
  warning: "border-warning/35 bg-warning/[0.06]",
  info: "border-info/30 bg-info/[0.05]",
  accent: "border-accent-primary/35 bg-accent-primary/[0.06]",
  error: "border-error/30 bg-error/[0.05]",
  neutral: "border-border-default bg-background-secondary/50",
};

export default function TablesPage() {
  const t = useTranslations("tablesPage");
  const tc = useTranslations("common");
  const { can } = useAuth();

  const toast = useToast();
  const { selectedBranchId: branchId } = useBranch();
  const [zoneFilter, setZoneFilter] = useState<string | null>(null);
  const [tables, setTables] = useState<LoadState<TableOut[]>>(loadingState());
  const [activeOrders, setActiveOrders] = useState<OrderOut[]>([]);
  const [statusFilter, setStatusFilter] = useState<string | null>(null);
  const [modal, setModal] = useState<
    | { type: "create" }
    | { type: "edit"; table: TableOut }
    | { type: "transfer"; table: TableOut; order: OrderOut }
    | { type: "merge"; table: TableOut; order: OrderOut }
    | null
  >(null);

  const canCreate = can("users.manage");
  const canUpdate = can("orders.read");
  const canMoveOrders = can("orders.update");

  const orderForTable = (tableId: string) =>
    activeOrders.find((o) => o.table_id === tableId);

  // Floor state shown on the card: free / ordered / waiting for payment /
  // reserved / disabled — derived from the real table status + its open order.
  const floorState = (table: TableOut): { tone: Tone; label: string } => {
    if (table.status === "DISABLED") return { tone: "neutral", label: tc("tableStatus.DISABLED") };
    if (table.status === "RESERVED") return { tone: "accent", label: tc("tableStatus.RESERVED") };
    if (table.status === "AVAILABLE") return { tone: "success", label: tc("tableStatus.AVAILABLE") };
    const order = orderForTable(table.id);
    if (order?.status === "PARTIALLY_PAID") return { tone: "warning", label: t("awaitingPayment") };
    if (order) return { tone: "info", label: t("stateOrdered") };
    return { tone: "warning", label: tc("tableStatus.OCCUPIED") };
  };

  const loadActiveOrders = useCallback(async () => {
    if (!branchId) {
      setActiveOrders([]);
      return;
    }
    try {
      setActiveOrders(await ordersApi.listActive(branchId));
    } catch {
      setActiveOrders([]);
    }
  }, [branchId]);

  const loadTables = useCallback(async () => {
    try {
      const list = await tablesApi.list(branchId ?? undefined);
      setTables(dataState(list));
    } catch (err) {
      setTables(errorState((err as Error).message));
    }
  }, [branchId]);

  useLiveReload(() => {
    void loadActiveOrders();
    void loadTables();
  });

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
    loadActiveOrders();
  }, [branchId, loadActiveOrders]);

  const flash = (message: string) => toast.success(message);

  const handleCreate = async (name: string, capacity: number, zone: string) => {
    if (!branchId) return;
    try {
      await tablesApi.create({ branch_id: branchId, name, capacity, zone: zone || null });
      setModal(null);
      flash(tc("actions.saved"));
      loadTables();
    } catch (err) {
      toast.error((err as Error).message);
    }
  };

  const handleUpdate = async (table: TableOut, updates: {
    name?: string;
    capacity?: number;
    status?: string;
    zone?: string | null;
  }) => {
    try {
      await tablesApi.update(table.id, updates);
      setModal(null);
      flash(tc("actions.saved"));
      loadTables();
    } catch (err) {
      toast.error((err as Error).message);
    }
  };

  const handleTransfer = async (order: OrderOut, destTableId: string) => {
    try {
      await ordersApi.transferTable(order.id, destTableId);
      setModal(null);
      flash(tc("actions.saved"));
      loadTables();
      loadActiveOrders();
    } catch (err) {
      toast.error((err as Error).message);
    }
  };

  const handleMerge = async (order: OrderOut, targetOrder: OrderOut) => {
    try {
      await ordersApi.mergeInto(order.id, targetOrder.id);
      setModal(null);
      flash(tc("actions.saved"));
      loadTables();
      loadActiveOrders();
    } catch (err) {
      toast.error((err as Error).message);
    }
  };

  const allTables = tables.type === "data" ? tables.data : [];
  const zones = Array.from(new Set(allTables.map((tb) => tb.zone).filter((z): z is string => !!z)));
  const shown = allTables.filter(
    (table) =>
      (!statusFilter || table.status === statusFilter) &&
      (!zoneFilter || table.zone === zoneFilter)
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

      <div className="mb-5 flex flex-col gap-3">
        <Tabs
          value={statusFilter ?? "all"}
          onChange={(k) => setStatusFilter(k === "all" ? null : k)}
          items={[
            { key: "all", label: t("filterAll"), count: counts.total },
            ...TABLE_STATUSES.map((status) => ({
              key: status,
              label: statusToText(status),
              count: counts.byStatus(status),
            })),
          ]}
        />
        {zones.length > 0 && (
          <Tabs
            value={zoneFilter ?? "all"}
            onChange={(k) => setZoneFilter(k === "all" ? null : k)}
            items={[{ key: "all", label: t("allZones") }, ...zones.map((z) => ({ key: z, label: z }))]}
          />
        )}
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
                  FLOOR_CARD[floorState(table).tone]
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div
                    className={`flex h-12 w-12 items-center justify-center rounded-xl ${FLOOR_ICON[floorState(table).tone]}`}
                  >
                    <Table2 className="h-6 w-6" />
                  </div>
                  <StatusBadge tone={floorState(table).tone}>{floorState(table).label}</StatusBadge>
                </div>

                <p className="mt-3 font-semibold text-text-primary">
                  {table.name}
                </p>
                {table.zone && (
                  <p className="text-xs text-text-secondary">{table.zone}</p>
                )}
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

                {orderForTable(table.id) && (
                  <div className="mt-3 flex items-center justify-between rounded-lg bg-surface/80 px-3 py-2 text-sm ring-1 ring-border-default">
                    <span className="font-medium text-text-primary">
                      #{orderForTable(table.id)!.order_number}
                    </span>
                    <span className="tabular font-semibold text-text-primary">
                      {formatMoney(orderForTable(table.id)!.total, orderForTable(table.id)!.currency)}
                    </span>
                    {orderForTable(table.id)!.status === "PARTIALLY_PAID" && (
                      <StatusBadge tone="warning">{t("awaitingPayment")}</StatusBadge>
                    )}
                  </div>
                )}

                {(canUpdate || canCreate || canMoveOrders) && (
                  <div className="mt-3 flex justify-end gap-1">
                    {canMoveOrders && table.status === "OCCUPIED" && orderForTable(table.id) && (
                      <>
                        <button
                          onClick={() =>
                            setModal({ type: "transfer", table, order: orderForTable(table.id)! })
                          }
                          aria-label={t("transferTable")}
                          title={t("transferTable")}
                          className="flex h-7 w-7 items-center justify-center rounded-lg text-text-secondary hover:bg-surface hover:text-accent-primary"
                        >
                          <ArrowRightLeft className="h-3.5 w-3.5" />
                        </button>
                        <button
                          onClick={() =>
                            setModal({ type: "merge", table, order: orderForTable(table.id)! })
                          }
                          aria-label={t("mergeTable")}
                          title={t("mergeTable")}
                          className="flex h-7 w-7 items-center justify-center rounded-lg text-text-secondary hover:bg-surface hover:text-accent-primary"
                        >
                          <Combine className="h-3.5 w-3.5" />
                        </button>
                      </>
                    )}
                    {(canUpdate || canCreate) && (
                      <button
                        onClick={() => setModal({ type: "edit", table })}
                        aria-label={t("editTable")}
                        className="flex h-7 w-7 items-center justify-center rounded-lg text-text-secondary hover:bg-surface hover:text-accent-primary"
                      >
                        <Pencil className="h-3.5 w-3.5" />
                      </button>
                    )}
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
          onSubmit={(name, capacity, _status, zone) => handleCreate(name, capacity, zone)}
        />
      )}

      {modal?.type === "edit" && (
        <TableFormModal
          title={t("editTable")}
          initial={modal.table}
          onClose={() => setModal(null)}
          onSubmit={(name, capacity, status, zone) =>
            handleUpdate(modal.table, {
              ...(name && name !== modal.table.name ? { name } : {}),
              ...(capacity !== modal.table.capacity ? { capacity } : {}),
              ...(status && status !== modal.table.status ? { status } : {}),
              ...(zone !== (modal.table.zone ?? "") ? { zone: zone || null } : {}),
            })
          }
        />
      )}

      {modal?.type === "transfer" && (
        <TransferTableModal
          currentTable={modal.table}
          order={modal.order}
          candidates={(tables.type === "data" ? tables.data : []).filter(
            (tb) => tb.id !== modal.table.id && tb.status === "AVAILABLE"
          )}
          onClose={() => setModal(null)}
          onSubmit={(destTableId) => handleTransfer(modal.order, destTableId)}
        />
      )}

      {modal?.type === "merge" && (
        <MergeTableModal
          currentTable={modal.table}
          order={modal.order}
          candidates={(tables.type === "data" ? tables.data : [])
            .filter((tb) => tb.id !== modal.table.id && tb.status === "OCCUPIED")
            .map((tb) => ({ table: tb, order: orderForTable(tb.id) }))
            .filter((c): c is { table: TableOut; order: OrderOut } => !!c.order)}
          onClose={() => setModal(null)}
          onSubmit={(targetOrder) => handleMerge(modal.order, targetOrder)}
        />
      )}
    </div>
  );
}

function TransferTableModal({
  currentTable,
  order,
  candidates,
  onClose,
  onSubmit,
}: {
  currentTable: TableOut;
  order: OrderOut;
  candidates: TableOut[];
  onClose: () => void;
  onSubmit: (destTableId: string) => void;
}) {
  const t = useTranslations("tablesPage");
  const tc = useTranslations("common");
  const [destTableId, setDestTableId] = useState(candidates[0]?.id ?? "");

  return (
    <Modal open onClose={onClose} title={t("transferTable")}>
      <p className="mb-4 text-sm text-text-secondary">
        {t("transferDescription", { table: currentTable.name, order: order.order_number })}
      </p>
      {candidates.length === 0 ? (
        <p className="text-sm text-text-secondary">{t("noAvailableTables")}</p>
      ) : (
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            if (destTableId) onSubmit(destTableId);
          }}
        >
          <select
            value={destTableId}
            onChange={(e) => setDestTableId(e.target.value)}
            className="w-full rounded-lg border border-border-default bg-background px-3 py-2 text-sm text-text-primary outline-none focus:border-accent-primary"
          >
            {candidates.map((tb) => (
              <option key={tb.id} value={tb.id}>
                {tb.name}
              </option>
            ))}
          </select>
          <div className="flex justify-end gap-2">
            <Button variant="secondary" size="sm" onClick={onClose}>
              {tc("actions.cancel")}
            </Button>
            <Button type="submit" size="sm">
              {t("transferTable")}
            </Button>
          </div>
        </form>
      )}
    </Modal>
  );
}

function MergeTableModal({
  currentTable,
  order,
  candidates,
  onClose,
  onSubmit,
}: {
  currentTable: TableOut;
  order: OrderOut;
  candidates: { table: TableOut; order: OrderOut }[];
  onClose: () => void;
  onSubmit: (targetOrder: OrderOut) => void;
}) {
  const t = useTranslations("tablesPage");
  const tc = useTranslations("common");
  const [targetTableId, setTargetTableId] = useState(candidates[0]?.table.id ?? "");

  return (
    <Modal open onClose={onClose} title={t("mergeTable")}>
      <p className="mb-4 text-sm text-text-secondary">
        {t("mergeDescription", { table: currentTable.name, order: order.order_number })}
      </p>
      {candidates.length === 0 ? (
        <p className="text-sm text-text-secondary">{t("noOccupiedTables")}</p>
      ) : (
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            const target = candidates.find((c) => c.table.id === targetTableId);
            if (target) onSubmit(target.order);
          }}
        >
          <select
            value={targetTableId}
            onChange={(e) => setTargetTableId(e.target.value)}
            className="w-full rounded-lg border border-border-default bg-background px-3 py-2 text-sm text-text-primary outline-none focus:border-accent-primary"
          >
            {candidates.map((c) => (
              <option key={c.table.id} value={c.table.id}>
                {c.table.name} (#{c.order.order_number})
              </option>
            ))}
          </select>
          <div className="flex justify-end gap-2">
            <Button variant="secondary" size="sm" onClick={onClose}>
              {tc("actions.cancel")}
            </Button>
            <Button type="submit" size="sm">
              {t("mergeTable")}
            </Button>
          </div>
        </form>
      )}
    </Modal>
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
  onSubmit: (name: string, capacity: number, status: string, zone: string) => void;
}) {
  const t = useTranslations("tablesPage");
  const tc = useTranslations("common");
  const [name, setName] = useState(initial?.name ?? "");
  const [zone, setZone] = useState(initial?.zone ?? "");
  const [capacity, setCapacity] = useState(String(initial?.capacity ?? 2));
  const [status, setStatus] = useState(initial?.status ?? "AVAILABLE");

  return (
    <Modal open onClose={onClose} title={title}>
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          onSubmit(name.trim(), parseInt(capacity, 10) || 1, status, zone.trim());
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
            {t("zone")}
          </label>
          <input
            value={zone}
            onChange={(e) => setZone(e.target.value)}
            placeholder={t("zonePlaceholder")}
            className="w-full rounded-lg border border-border-default bg-background px-3 py-2 text-sm text-text-primary outline-none focus:border-accent-primary"
          />
          <p className="mt-1 text-xs text-text-secondary">{t("zoneHint")}</p>
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