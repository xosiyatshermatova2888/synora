"use client";

import { useCallback, useEffect, useState } from "react";
import { useLiveReload } from "@/lib/use-live-reload";
import { useTranslations } from "next-intl";
import { Plus, Minus, Trash2, ChevronDown, ChevronUp, MapPin, Phone } from "lucide-react";
import {
  BranchOut,
  OrderOut,
  ProductOut,
  TableOut,
  menuApi,
  ordersApi,
  restaurantsApi,
  tablesApi,
} from "@/lib/api";
import { formatMoney, formatDateTime } from "@/lib/format";
import { useAuth } from "@/lib/auth-context";
import { useBranch } from "@/lib/branch-context";
import Modal from "@/components/Modal";
import Button from "@/components/Button";
import PageHeader from "@/components/dashboard/PageHeader";
import ReceiptButton from "@/components/ReceiptButton";
import DataTable, { Column } from "@/components/ui/DataTable";
import Pagination from "@/components/ui/Pagination";
import SearchField from "@/components/ui/SearchField";
import Tabs from "@/components/ui/Tabs";
import StatusBadge, { kitchenStatusTone, orderStatusTone } from "@/components/ui/StatusBadge";
import { useToast } from "@/components/ui/Toast";
import SafeImage from "@/components/ui/SafeImage";

const ORDER_STATUSES = ["DRAFT", "OPEN", "PARTIALLY_PAID", "COMPLETED", "CANCELLED", "REFUNDED"];
const ORDER_SOURCES = ["POS", "WAITER", "QR", "TELEGRAM", "DELIVERY", "ONLINE"];
const PAGE_SIZE = 25;

// Used by the order-detail modal below.
const STATUS_STYLES: Record<string, string> = {
  DRAFT: "bg-background-secondary text-text-secondary",
  OPEN: "bg-info/10 text-info",
  PARTIALLY_PAID: "bg-warning/10 text-warning",
  COMPLETED: "bg-success/10 text-success",
  CANCELLED: "bg-error/10 text-error",
  REFUNDED: "bg-error/10 text-error",
};

interface CartLine {
  key: string;
  product: ProductOut;
  quantity: number;
  notes: string;
  selectedByGroup: Record<string, string[]>;
}

export default function OrdersPage() {
  const t = useTranslations("ordersPage");
  const tc = useTranslations("common");
  const toast = useToast();
  const { can } = useAuth();
  const { branches, selectedBranchId } = useBranch();

  const [rows, setRows] = useState<OrderOut[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tableMap, setTableMap] = useState<Map<string, string>>(new Map());
  const [statusFilter, setStatusFilter] = useState<string | null>(null);
  const [sourceFilter, setSourceFilter] = useState<string>("");
  const [search, setSearch] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [detailOrder, setDetailOrder] = useState<OrderOut | null>(null);
  const [currency, setCurrency] = useState("UZS");

  const canCreate = can("orders.create");
  const canUpdate = can("orders.update");
  const searching = search.trim() !== "";

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true); // live refreshes keep the list on screen
    setError(null);
    try {
      // While searching by number, scan the latest 100 orders (the API has no
      // number filter); otherwise page through the server-side list.
      const page = await ordersApi.list({
        branch_id: selectedBranchId ?? undefined,
        status: statusFilter ?? undefined,
        limit: searching ? 100 : PAGE_SIZE,
        offset: searching ? 0 : offset,
      });
      setRows(page.items);
      setTotal(page.total);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }, [selectedBranchId, statusFilter, offset, searching]);

  useEffect(() => {
    void load();
  }, [load]);

  // New / changed orders appear by themselves (waiter, Telegram, QR, kitchen, cashier).
  useLiveReload(() => void load(true));

  useEffect(() => {
    tablesApi
      .list()
      .then((list) => setTableMap(new Map(list.map((tb) => [tb.id, tb.name]))))
      .catch(() => {});
    restaurantsApi.getMine().then((r) => setCurrency(r.currency)).catch(() => {});
  }, []);

  const shown = rows.filter((order) => {
    if (sourceFilter && order.source !== sourceFilter) return false;
    if (searching && !String(order.order_number).includes(search.trim())) return false;
    return true;
  });

  const statusToText = (status: string) => tc(`orderStatus.${status}` as "orderStatus.OPEN");

  const handleStatus = async (order: OrderOut, status: string) => {
    try {
      await ordersApi.updateStatus(order.id, status);
      setDetailOrder(null);
      toast.success(t("statusChanged"));
      void load();
    } catch (err) {
      toast.error((err as Error).message);
    }
  };

  const handleKitchen = async (order: OrderOut, kitchenStatus: string) => {
    try {
      await ordersApi.updateKitchenStatus(order.id, kitchenStatus);
      setDetailOrder(null);
      toast.success(t("statusChanged"));
      void load();
    } catch (err) {
      toast.error((err as Error).message);
    }
  };

  const columns: Column<OrderOut>[] = [
    {
      key: "number",
      header: t("orderNumber"),
      sortValue: (o) => o.order_number,
      render: (o) => (
        <div>
          <p className="font-semibold text-text-primary">#{o.order_number}</p>
          <p className="text-xs text-text-secondary">{formatDateTime(o.created_at)}</p>
        </div>
      ),
    },
    {
      key: "source",
      header: t("source"),
      hideOnMobile: true,
      render: (o) => (
        <StatusBadge tone={o.source === "TELEGRAM" || o.source === "QR" ? "accent" : "neutral"}>
          {t(`sources.${o.source}` as "sources.POS")}
        </StatusBadge>
      ),
    },
    {
      key: "table",
      header: t("table"),
      render: (o) => (o.table_id ? (tableMap.get(o.table_id) ?? "—") : "—"),
    },
    {
      key: "waiter",
      header: t("colWaiter"),
      hideOnMobile: true,
      render: (o) => <span className="text-text-secondary">{o.waiter_name ?? "—"}</span>,
    },
    {
      key: "items",
      header: t("items"),
      hideOnMobile: true,
      sortValue: (o) => o.items.length,
      render: (o) => (
        <span className="text-text-secondary">
          {o.items.length} {t("itemsCount")}
        </span>
      ),
    },
    {
      key: "status",
      header: t("colStatus"),
      render: (o) => (
        <StatusBadge tone={orderStatusTone[o.status] ?? "neutral"}>{statusToText(o.status)}</StatusBadge>
      ),
    },
    {
      key: "kitchen",
      header: t("kitchen"),
      hideOnMobile: true,
      render: (o) => (
        <StatusBadge tone={kitchenStatusTone[o.kitchen_status] ?? "neutral"}>
          {tc(`kitchenStatus.${o.kitchen_status}` as "kitchenStatus.NEW")}
        </StatusBadge>
      ),
    },
    {
      key: "total",
      header: t("total"),
      align: "right",
      sortValue: (o) => parseFloat(o.total),
      render: (o) => <span className="font-semibold">{formatMoney(o.total, currency)}</span>,
    },
  ];

  return (
    <div>
      <PageHeader
        title={t("title")}
        description={t("description")}
        actions={
          canCreate ? (
            <Button size="sm" onClick={() => setCreateOpen(true)}>
              <Plus className="h-4 w-4" />
              {t("newOrder")}
            </Button>
          ) : undefined
        }
      />

      <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <Tabs
          value={statusFilter ?? "all"}
          onChange={(k) => {
            setOffset(0);
            setStatusFilter(k === "all" ? null : k);
          }}
          items={[
            { key: "all", label: t("filterAll") },
            ...ORDER_STATUSES.map((s) => ({ key: s, label: statusToText(s) })),
          ]}
        />
        <div className="flex flex-col gap-2 sm:flex-row">
          <select
            value={sourceFilter}
            onChange={(e) => setSourceFilter(e.target.value)}
            aria-label={t("filterSource")}
            className="h-10 rounded-lg border border-border-default bg-surface px-3 text-sm text-text-primary outline-none focus:border-accent-primary"
          >
            <option value="">{t("allSources")}</option>
            {ORDER_SOURCES.map((s) => (
              <option key={s} value={s}>
                {t(`sources.${s}` as "sources.POS")}
              </option>
            ))}
          </select>
          <SearchField
            value={search}
            onChange={(v) => {
              setOffset(0);
              setSearch(v);
            }}
            placeholder={t("searchPlaceholder")}
            clearLabel={tc("ui.clear")}
            className="sm:w-56"
          />
        </div>
      </div>

      <DataTable
        columns={columns}
        rows={shown}
        rowKey={(o) => o.id}
        loading={loading}
        error={error}
        onRetry={() => void load()}
        emptyMessage={t("empty")}
        onRowClick={setDetailOrder}
        footer={
          !searching && (
            <Pagination total={total} limit={PAGE_SIZE} offset={offset} onChange={setOffset} />
          )
        }
      />

      {createOpen && (
        <OrderCreateModal
          branches={branches}
          branchId={selectedBranchId}
          currency={currency}
          onClose={() => setCreateOpen(false)}
          onCreated={() => {
            setCreateOpen(false);
            toast.success(t("orderCreated"));
            setOffset(0);
            void load();
          }}
        />
      )}

      {detailOrder && (
        <OrderDetailModal
          order={detailOrder}
          currency={currency}
          tableName={detailOrder.table_id ? tableMap.get(detailOrder.table_id) : undefined}
          canUpdate={canUpdate}
          onClose={() => setDetailOrder(null)}
          onStatus={(status) => handleStatus(detailOrder, status)}
          onKitchen={(kitchenStatus) => handleKitchen(detailOrder, kitchenStatus)}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Create order modal
// ---------------------------------------------------------------------------
function OrderCreateModal({
  branches,
  branchId,
  currency,
  onClose,
  onCreated,
}: {
  branches: BranchOut[];
  branchId: string | null;
  currency: string;
  onClose: () => void;
  onCreated: () => void;
}) {
  const t = useTranslations("ordersPage");
  const tc = useTranslations("common");
  const [activeBranch, setActiveBranch] = useState<string>(branchId ?? branches[0]?.id ?? "");
  const [tables, setTables] = useState<TableOut[]>([]);
  const [tableId, setTableId] = useState<string>("");
  const [products, setProducts] = useState<ProductOut[]>([]);
  const [lines, setLines] = useState<CartLine[]>([]);
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!activeBranch) return;
    tablesApi.list(activeBranch).then((list) => setTables(list)).catch(() => {});
  }, [activeBranch]);

  useEffect(() => {
    menuApi.listProducts(100, 0).then((page) => setProducts(page.items)).catch(() => {});
  }, []);

  // Idempotency-Key: generated once when the form is opened (not per render),
  // so a retry of the same logical order cannot create a duplicate.
  const [idempotencyKey] = useState<string>(() => {
    if (typeof globalThis !== "undefined" && globalThis.crypto?.randomUUID) {
      return globalThis.crypto.randomUUID();
    }
    return `idem-${Date.now()}`;
  });

  const addLine = () => {
    const first = products[0];
    if (!first) return;
    setLines((prev) => [
      ...prev,
      {
        key: `${Date.now()}-${Math.random()}`,
        product: first,
        quantity: 1,
        notes: "",
        selectedByGroup: {},
      },
    ]);
  };

  const updateLine = (key: string, patch: Partial<CartLine>) => {
    setLines((prev) =>
      prev.map((line) => (line.key === key ? { ...line, ...patch } : line))
    );
  };

  const setLineProduct = (key: string, product: ProductOut) => {
    updateLine(key, { product, selectedByGroup: {} });
  };

  const toggleModifier = (key: string, groupId: string, modifierId: string, maxSelections: number) => {
    setLines((prev) =>
      prev.map((line) => {
        if (line.key !== key) return line;
        const current = line.selectedByGroup[groupId] ?? [];
        const next = current.includes(modifierId)
          ? current.filter((m) => m !== modifierId)
          : current.length >= maxSelections
            ? [...current.slice(1), modifierId]
            : [...current, modifierId];
        return { ...line, selectedByGroup: { ...line.selectedByGroup, [groupId]: next } };
      })
    );
  };

  const isValid = lines.length > 0 && lines.every((line) =>
    line.product.modifier_groups.every(
      (group) =>
        (line.selectedByGroup[group.id] ?? []).length >= group.min_selections
    )
  );

  const total = lines.reduce((sum, line) => {
    if (!line.product) return sum;
    let lineTotal = parseFloat(line.product.price) * line.quantity;
    for (const [groupId, modIds] of Object.entries(line.selectedByGroup)) {
      const group = line.product.modifier_groups.find((g) => g.id === groupId);
      if (!group) continue;
      for (const modId of modIds) {
        const mod = group.modifiers.find((m) => m.id === modId);
        if (mod) lineTotal += parseFloat(mod.price);
      }
    }
    return sum + lineTotal;
  }, 0);

  const submit = async () => {
    if (!activeBranch || !isValid || submitting) return;
    setSubmitting(true);
    try {
      await ordersApi.create(
        {
          branch_id: activeBranch,
          table_id: tableId || null,
          source: "POS",
          notes: notes.trim() || undefined,
          items: lines.map((line) => ({
            product_id: line.product.id,
            quantity: line.quantity,
            notes: line.notes.trim() || undefined,
            modifiers: Object.values(line.selectedByGroup)
              .flat()
              .map((modifierId) => ({ modifier_id: modifierId })),
          })),
        },
        idempotencyKey
      );
      onCreated();
    } catch (err) {
      alert((err as Error).message);
      setSubmitting(false);
    }
  };

  return (
    <Modal open onClose={onClose} title={t("createOrderTitle")}>
      <p className="mb-4 text-sm text-text-secondary">
        {t("createOrderDescription")}
      </p>

      <div className="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
        <label className="block text-sm font-medium text-text-primary">
          {t("selectTable")}
          <select
            value={tableId}
            onChange={(e) => setTableId(e.target.value)}
            className="mt-1 w-full rounded-lg border border-border-default bg-background px-3 py-2 text-sm text-text-primary outline-none focus:border-accent-primary"
          >
            <option value="">{t("tablePlaceholder")}</option>
            {tables
              .filter((tb) => tb.status !== "DISABLED")
              .map((tb) => (
                <option key={tb.id} value={tb.id}>
                  {tb.name} ({tb.capacity})
                </option>
              ))}
          </select>
        </label>

        {branches.length > 1 && (
          <label className="block text-sm font-medium text-text-primary">
            {t("selectBranch")}
            <select
              value={activeBranch}
              onChange={(e) => {
                setActiveBranch(e.target.value);
                setTableId("");
              }}
              className="mt-1 w-full rounded-lg border border-border-default bg-background px-3 py-2 text-sm text-text-primary outline-none focus:border-accent-primary"
            >
              {branches.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
            </select>
          </label>
        )}
      </div>

      {/* Lines */}
      <div className="max-h-64 space-y-3 overflow-y-auto pr-1">
        {lines.length === 0 && (
          <p className="rounded-lg border border-dashed border-border-default px-4 py-8 text-center text-sm text-text-secondary">
            {t("addItemLabel")}
          </p>
        )}
        {lines.map((line) => (
          <div key={line.key} className="rounded-lg border border-border-default bg-background p-3">
            <div className="flex items-center gap-2">
              <select
                value={line.product.id}
                onChange={(e) => {
                  const p = products.find((pr) => pr.id === e.target.value);
                  if (p) setLineProduct(line.key, p);
                }}
                className="min-w-0 flex-1 rounded-lg border border-border-default bg-surface px-2 py-1.5 text-sm text-text-primary outline-none focus:border-accent-primary"
              >
                {products.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} — {formatMoney(p.price, currency)}
                  </option>
                ))}
              </select>
              <div className="flex items-center gap-1">
                <button
                  onClick={() => updateLine(line.key, { quantity: Math.max(1, line.quantity - 1) })}
                  aria-label={t("remQty")}
                  className="flex h-8 w-8 items-center justify-center rounded-lg border border-border-default text-text-secondary hover:text-text-primary"
                >
                  <Minus className="h-4 w-4" />
                </button>
                <span className="w-8 text-center text-sm font-semibold text-text-primary">
                  {line.quantity}
                </span>
                <button
                  onClick={() => updateLine(line.key, { quantity: line.quantity + 1 })}
                  aria-label={t("addQty")}
                  className="flex h-8 w-8 items-center justify-center rounded-lg border border-border-default text-text-secondary hover:text-text-primary"
                >
                  <Plus className="h-4 w-4" />
                </button>
              </div>
              <button
                onClick={() => setLines((prev) => prev.filter((l) => l.key !== line.key))}
                aria-label={t("remove")}
                className="flex h-8 w-8 items-center justify-center rounded-lg text-text-secondary hover:text-error"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>

            {/* Modifiers */}
            {line.product.modifier_groups.length > 0 && (
              <div className="mt-2 space-y-2 border-t border-border-default pt-2">
                {line.product.modifier_groups.map((group) => {
                  const selected = line.selectedByGroup[group.id] ?? [];
                  const isRadio = group.max_selections === 1;
                  return (
                    <fieldset key={group.id}>
                      <legend className="text-xs font-semibold text-text-secondary">
                        {group.name}
                        {group.is_required ? " *" : ""}
                      </legend>
                      <div className="mt-1 flex flex-wrap gap-1.5">
                        {group.modifiers.map((mod) => {
                          const checked = selected.includes(mod.id);
                          return (
                            <button
                              key={mod.id}
                              type="button"
                              onClick={() =>
                                toggleModifier(line.key, group.id, mod.id, group.max_selections)
                              }
                              className={`rounded-full border px-2.5 py-1 text-xs font-medium transition-colors ${
                                checked
                                  ? "border-accent-primary bg-accent-primary/10 text-accent-primary"
                                  : "border-border-default text-text-secondary hover:text-text-primary"
                              }`}
                            >
                              {mod.name} +{formatMoney(mod.price, currency)}
                            </button>
                          );
                        })}
                      </div>
                      {isRadio && selected.length === 1 && (
                        <span className="hidden" aria-hidden />
                      )}
                    </fieldset>
                  );
                })}
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="mt-3 flex items-center justify-between">
        <Button variant="secondary" size="sm" onClick={addLine}>
          <Plus className="h-4 w-4" />
          {t("addItemLabel")}
        </Button>
        <p className="text-sm font-semibold text-text-primary">
          {t("orderTotal")}:{" "}
          <span className="font-bold text-accent-primary">
            {formatMoney(total, currency)}
          </span>
        </p>
      </div>

      <textarea
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
        placeholder={t("notes")}
        rows={2}
        className="mt-3 w-full resize-none rounded-lg border border-border-default bg-background px-3 py-2 text-sm text-text-primary outline-none focus:border-accent-primary"
      />

      <div className="mt-4 flex justify-end gap-2">
        <Button variant="secondary" size="sm" onClick={onClose}>
          {tc("actions.cancel")}
        </Button>
        <Button size="sm" onClick={submit} disabled={!isValid || submitting}>
          {t("submitOrder")}
        </Button>
      </div>
    </Modal>
  );
}

// ---------------------------------------------------------------------------
// Order detail modal
// ---------------------------------------------------------------------------
function OrderDetailModal({
  order,
  currency,
  tableName,
  canUpdate,
  onClose,
  onStatus,
  onKitchen,
}: {
  order: OrderOut;
  currency: string;
  tableName: string | undefined;
  canUpdate: boolean;
  onClose: () => void;
  onStatus: (status: string) => void;
  onKitchen: (kitchenStatus: string) => void;
}) {
  const t = useTranslations("ordersPage");
  const tc = useTranslations("common");
  const statusToText = (status: string) => tc(`orderStatus.${status}`) ?? status;
  const [showItems, setShowItems] = useState(true);

  const kitchenActions: { key: string; labelKey: string }[] = [];
  if (order.kitchen_status === "PENDING") {
    kitchenActions.push({ key: "NEW", labelKey: "markPreparing" });
  } else if (order.kitchen_status === "NEW" || order.kitchen_status === "PREPARING") {
    kitchenActions.push({ key: "READY", labelKey: "markReady" });
  }
  if (["NEW", "PREPARING", "READY"].includes(order.kitchen_status)) {
    kitchenActions.push({ key: "SERVED", labelKey: "markServed" });
  }

  const statusActions: { key: string; labelKey: string; danger?: boolean }[] = [];
  if (order.status === "DRAFT") {
    statusActions.push({ key: "OPEN", labelKey: "markPreparing" });
    statusActions.push({ key: "CANCELLED", labelKey: "markCancelled", danger: true });
  } else if (order.status === "OPEN") {
    statusActions.push({ key: "COMPLETED", labelKey: "markCompleted" });
    statusActions.push({ key: "CANCELLED", labelKey: "markCancelled", danger: true });
  } else if (order.status === "PARTIALLY_PAID") {
    statusActions.push({ key: "COMPLETED", labelKey: "markCompleted" });
  } else if (order.status === "COMPLETED") {
    statusActions.push({ key: "REFUNDED", labelKey: "markRefund" });
  }

  return (
    <Modal open onClose={onClose} title={`${t("detailTitle")} #${order.order_number}`}>
      <div className="space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <span
            className={`rounded-full px-2.5 py-1 text-xs font-semibold ${STATUS_STYLES[order.status] ?? "bg-background-secondary text-text-secondary"}`}
          >
            {statusToText(order.status)}
          </span>
          <span className="rounded-full bg-background-secondary px-2.5 py-1 text-xs font-semibold text-text-secondary">
            {t("kitchen")}: {tc(`kitchenStatus.${order.kitchen_status}`) ?? order.kitchen_status}
          </span>
        </div>

        <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
          <dt className="text-text-secondary">{t("orderNumber")}</dt>
          <dd className="text-right font-semibold text-text-primary">#{order.order_number}</dd>
          <dt className="text-text-secondary">{t("table")}</dt>
          <dd className="text-right font-semibold text-text-primary">{tableName ?? "—"}</dd>
          <dt className="text-text-secondary">{t("source")}</dt>
          <dd className="text-right font-semibold uppercase text-text-primary">{order.source}</dd>
          <dt className="text-text-secondary">{t("createdAt")}</dt>
          <dd className="text-right font-semibold text-text-primary">
            {formatDateTime(order.created_at)}
          </dd>
        </dl>

        {(order.customer_name || order.customer_phone || order.delivery_type) && (
          <div className="space-y-2 rounded-lg border border-border-default p-3 text-sm">
            <p className="text-xs font-semibold uppercase tracking-wide text-text-secondary">
              {order.delivery_type ? t(`deliveryType.${order.delivery_type}`) : t("customer")}
            </p>
            {order.customer_name && <p className="font-medium text-text-primary">{order.customer_name}</p>}
            {order.customer_phone && (
              <a href={`tel:${order.customer_phone}`} className="flex items-center gap-1.5 text-accent-primary hover:underline">
                <Phone className="h-3.5 w-3.5" />
                {order.customer_phone}
              </a>
            )}
            {order.delivery_type === "DELIVERY" && order.delivery_address && (
              <p className="flex items-start gap-1.5 text-text-primary">
                <MapPin className="mt-0.5 h-3.5 w-3.5 shrink-0 text-text-secondary" />
                <span>{order.delivery_address}</span>
              </p>
            )}
            {order.delivery_note && <p className="text-xs text-text-secondary">{order.delivery_note}</p>}
            {order.delivery_lat && order.delivery_lng && (
              <a
                href={`https://www.google.com/maps?q=${order.delivery_lat},${order.delivery_lng}`}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-xs font-medium text-accent-primary hover:underline"
              >
                <MapPin className="h-3.5 w-3.5" />
                {t("openMap")}
              </a>
            )}
          </div>
        )}

        {order.payment_method && (
          <div className="space-y-2 rounded-lg border border-border-default p-3 text-sm">
            <div className="flex items-center justify-between">
              <span className="text-text-secondary">{t("paymentMethod")}</span>
              <span className="font-semibold text-text-primary">{t(`paymentMethods.${order.payment_method}`)}</span>
            </div>
            {order.payment_proof_url && (
              <a href={order.payment_proof_url} target="_blank" rel="noopener noreferrer" className="block">
                <p className="mb-1 text-xs font-medium text-text-secondary">{t("paymentProof")}</p>
                <SafeImage src={order.payment_proof_url} alt={t("paymentProof")} className="h-40 w-full rounded-lg" />
              </a>
            )}
          </div>
        )}

        {/* Items */}
        <div className="rounded-lg border border-border-default">
          <button
            onClick={() => setShowItems((v) => !v)}
            className="flex w-full items-center justify-between px-4 py-3 text-sm font-semibold text-text-primary"
          >
            {t("items")} ({order.items.length})
            {showItems ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </button>
          {showItems && (
            <ul className="divide-y divide-border-default border-t border-border-default px-4 py-2">
              {order.items.map((item) => {
                const modifiersTotal = item.modifiers.reduce(
                  (sum, m) => sum + parseFloat(m.price) * m.quantity,
                  0
                );
                return (
                  <li key={item.id} className="py-2">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-text-primary">
                          {item.quantity} × {item.product_name_snapshot}
                        </p>
                        {item.modifiers.length > 0 && (
                          <ul className="mt-1 space-y-0.5 pl-3 text-xs text-text-secondary">
                            {item.modifiers.map((m) => (
                              <li key={m.id}>
                                {m.modifier_name_snapshot}{" "}
                                {parseFloat(m.price) > 0
                                  ? `+${formatMoney(m.price, currency)}`
                                  : ""}
                              </li>
                            ))}
                          </ul>
                        )}
                        {item.notes && (
                          <p className="mt-1 text-xs italic text-text-secondary">{item.notes}</p>
                        )}
                      </div>
                      <span className="shrink-0 text-sm font-semibold text-text-primary">
                        {formatMoney(parseFloat(item.unit_price) * item.quantity + modifiersTotal, currency)}
                      </span>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        <dl className="ml-auto w-48 space-y-1 text-sm">
          <div className="flex justify-between">
            <dt className="text-text-secondary">{t("subtotal")}</dt>
            <dd className="font-medium text-text-primary">{formatMoney(order.subtotal, currency)}</dd>
          </div>
          {parseFloat(order.discount) > 0 && (
            <div className="flex justify-between">
              <dt className="text-text-secondary">{t("discount")}</dt>
              <dd className="font-medium text-success">−{formatMoney(order.discount, currency)}</dd>
            </div>
          )}
          <div className="flex justify-between">
            <dt className="text-text-secondary">{t("tax")}</dt>
            <dd className="font-medium text-text-primary">{formatMoney(order.tax, currency)}</dd>
          </div>
          {parseFloat(order.service_charge) > 0 && (
            <div className="flex justify-between">
              <dt className="text-text-secondary">{t("serviceCharge")}</dt>
              <dd className="font-medium text-text-primary">
                {formatMoney(order.service_charge, currency)}
              </dd>
            </div>
          )}
          <div className="flex justify-between border-t border-border-default pt-1">
            <dt className="font-semibold text-text-primary">{t("total")}</dt>
            <dd className="font-bold text-accent-primary">{formatMoney(order.total, currency)}</dd>
          </div>
        </dl>

        {order.notes && (
          <p className="rounded-lg bg-background px-3 py-2 text-sm text-text-secondary">
            {order.notes}
          </p>
        )}

        {(canUpdate || order.status !== "REFUNDED") && (
          <div className="flex flex-wrap justify-end gap-2">
            <ReceiptButton
              orderId={order.id}
              className="flex items-center gap-1.5 rounded-xl border border-border-default px-4 py-2 text-sm font-medium text-text-secondary hover:border-accent-primary/60 hover:text-accent-primary"
            />
            {canUpdate &&
              kitchenActions.map((action) => (
                <Button key={action.key} variant="secondary" size="sm"
                  onClick={() => onKitchen(action.key)}>
                  {t(action.labelKey)}
                </Button>
              ))}
            {canUpdate &&
              statusActions.map((action) => (
                <Button
                  key={action.key}
                  variant="primary"
                  size="sm"
                  className={action.danger ? "bg-error hover:brightness-110" : ""}
                  onClick={() => onStatus(action.key)}
                >
                  {t(action.labelKey)}
                </Button>
              ))}
            <Button variant="ghost" size="sm" onClick={onClose}>
              {tc("actions.close")}
            </Button>
          </div>
        )}
      </div>
    </Modal>
  );
}