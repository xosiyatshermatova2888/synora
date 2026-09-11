"use client";

import { useEffect, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import {
  Armchair,
  ArrowLeft,
  CheckCircle2,
  ImageOff,
  LogOut,
  Minus,
  Plus,
  ShoppingCart,
  Table2,
  Trash2,
} from "lucide-react";
import { Link } from "@/i18n/routing";
import {
  BranchOut,
  CategoryOut,
  OrderOut,
  ProductOut,
  TableOut,
  branchesApi,
  menuApi,
  ordersApi,
  tablesApi,
} from "@/lib/api";
import type { LoadState } from "@/lib/load-state";
import { loadingState, errorState, dataState } from "@/lib/load-state";
import { formatMoney } from "@/lib/format";
import { useAuth } from "@/lib/auth-context";
import Modal from "@/components/Modal";
import Button from "@/components/Button";
import StateView from "@/components/dashboard/StateView";

const TABLE_STATUS_STYLES: Record<string, string> = {
  AVAILABLE: "border-success/25 bg-success/[0.04]",
  OCCUPIED: "border-warning/25 bg-warning/[0.04]",
  RESERVED: "border-accent-primary/25 bg-accent-primary/[0.04]",
  DISABLED: "border-border-default bg-background-secondary/50",
};
const TABLE_BADGE_STYLES: Record<string, string> = {
  AVAILABLE: "bg-success/10 text-success",
  OCCUPIED: "bg-warning/10 text-warning",
  RESERVED: "bg-accent-primary/10 text-accent-primary",
  DISABLED: "bg-background-secondary text-text-secondary",
};
const MAX_SEAT_ICONS = 6;

interface CartLine {
  key: string;
  product: ProductOut;
  quantity: number;
  selectedByGroup: Record<string, string[]>;
}

function newIdempotencyKey(): string {
  if (typeof globalThis !== "undefined" && globalThis.crypto?.randomUUID) {
    return globalThis.crypto.randomUUID();
  }
  return `waiter-${Date.now()}-${Math.random()}`;
}

function lineUnitPrice(line: CartLine): number {
  let price = parseFloat(line.product.price);
  for (const [groupId, modIds] of Object.entries(line.selectedByGroup)) {
    const group = line.product.modifier_groups.find((g) => g.id === groupId);
    if (!group) continue;
    for (const modId of modIds) {
      const mod = group.modifiers.find((m) => m.id === modId);
      if (mod) price += parseFloat(mod.price);
    }
  }
  return price;
}

export default function WaiterPage() {
  const t = useTranslations("waiterPage");
  const tc = useTranslations("common");
  const { user, can, logout } = useAuth();
  const canOrder = can("orders.create");

  const [branches, setBranches] = useState<BranchOut[]>([]);
  const [branchId, setBranchId] = useState<string | null>(null);
  const [tables, setTables] = useState<LoadState<TableOut[]>>(loadingState());
  const [selectedTable, setSelectedTable] = useState<TableOut | null>(null);

  const [categories, setCategories] = useState<CategoryOut[]>([]);
  const [activeCategory, setActiveCategory] = useState<string | null>(null);
  const [products, setProducts] = useState<LoadState<ProductOut[]>>(loadingState());

  const [cart, setCart] = useState<CartLine[]>([]);
  const [cartOpen, setCartOpen] = useState(false);
  const [notes, setNotes] = useState("");
  const [modifierProduct, setModifierProduct] = useState<ProductOut | null>(null);
  const [idempotencyKey, setIdempotencyKey] = useState(() => newIdempotencyKey());
  const [submitting, setSubmitting] = useState(false);
  const [sentOrder, setSentOrder] = useState<OrderOut | null>(null);

  useEffect(() => {
    branchesApi
      .list()
      .then((list) => {
        setBranches(list);
        setBranchId((prev) => prev ?? list[0]?.id ?? null);
      })
      .catch(() => {});
    menuApi.listCategories().then(setCategories).catch(() => {});
  }, []);

  useEffect(() => {
    if (!branchId) return;
    void (async () => {
      setTables(loadingState());
      try {
        const list = await tablesApi.list(branchId);
        setTables(dataState(list));
      } catch (err) {
        setTables(errorState((err as Error).message));
      }
    })();
  }, [branchId]);

  useEffect(() => {
    void (async () => {
      setProducts(loadingState());
      try {
        const page = await menuApi.listProducts(100, 0, activeCategory ?? undefined);
        setProducts(dataState(page.items));
      } catch (err) {
        setProducts(errorState((err as Error).message));
      }
    })();
  }, [activeCategory]);

  const selectTable = (table: TableOut) => {
    setSelectedTable(table);
    setCart([]);
    setNotes("");
    setSentOrder(null);
    setIdempotencyKey(newIdempotencyKey());
  };

  const backToTables = () => {
    setSelectedTable(null);
    setCart([]);
    setSentOrder(null);
    if (branchId) {
      tablesApi.list(branchId).then((list) => setTables(dataState(list))).catch(() => {});
    }
  };

  const addSimple = (product: ProductOut) => {
    setCart((prev) => {
      const existing = prev.find(
        (l) => l.product.id === product.id && Object.keys(l.selectedByGroup).length === 0
      );
      if (existing) {
        return prev.map((l) =>
          l.key === existing.key ? { ...l, quantity: l.quantity + 1 } : l
        );
      }
      return [
        ...prev,
        { key: `${product.id}-${Date.now()}`, product, quantity: 1, selectedByGroup: {} },
      ];
    });
  };

  const tapProduct = (product: ProductOut) => {
    if (product.modifier_groups.length > 0) {
      setModifierProduct(product);
    } else {
      addSimple(product);
    }
  };

  const addWithModifiers = (
    product: ProductOut,
    selectedByGroup: Record<string, string[]>,
    quantity: number
  ) => {
    setCart((prev) => [
      ...prev,
      {
        key: `${product.id}-${Date.now()}-${Math.random()}`,
        product,
        quantity,
        selectedByGroup,
      },
    ]);
    setModifierProduct(null);
  };

  const updateQty = (key: string, delta: number) => {
    setCart((prev) =>
      prev.flatMap((l) => {
        if (l.key !== key) return [l];
        const q = l.quantity + delta;
        return q <= 0 ? [] : [{ ...l, quantity: q }];
      })
    );
  };

  const removeLine = (key: string) => {
    setCart((prev) => prev.filter((l) => l.key !== key));
  };

  const cartCount = useMemo(() => cart.reduce((s, l) => s + l.quantity, 0), [cart]);
  const cartTotal = useMemo(
    () => cart.reduce((s, l) => s + lineUnitPrice(l) * l.quantity, 0),
    [cart]
  );

  const submitOrder = async () => {
    if (!branchId || !selectedTable || cart.length === 0 || submitting) return;
    setSubmitting(true);
    try {
      const order = await ordersApi.create(
        {
          branch_id: branchId,
          table_id: selectedTable.id,
          source: "WAITER",
          notes: notes.trim() || undefined,
          items: cart.map((line) => ({
            product_id: line.product.id,
            quantity: line.quantity,
            modifiers: Object.values(line.selectedByGroup)
              .flat()
              .map((modifierId) => ({ modifier_id: modifierId })),
          })),
        },
        idempotencyKey
      );
      // Fire straight to the kitchen board — that is the whole point of a
      // waiter app; nobody should have to re-key this at a cashier screen.
      await ordersApi.updateKitchenStatus(order.id, "NEW").catch(() => {});
      setSentOrder(order);
      setCartOpen(false);
    } catch (err) {
      alert((err as Error).message);
    } finally {
      setSubmitting(false);
    }
  };

  const startAnotherRound = () => {
    setCart([]);
    setNotes("");
    setSentOrder(null);
    setIdempotencyKey(newIdempotencyKey());
  };

  if (!canOrder) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-3 bg-background p-6 text-center">
        <p className="text-lg font-semibold text-text-primary">{t("noPermission")}</p>
        <Link
          href="/dashboard"
          className="text-sm font-medium text-accent-primary hover:underline"
        >
          {t("backToDashboard")}
        </Link>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col bg-background">
      {/* Minimal header — no sidebar, no other modules */}
      <header className="flex h-14 shrink-0 items-center gap-3 border-b border-border-default bg-surface px-4">
        {selectedTable ? (
          <button
            onClick={backToTables}
            className="flex items-center gap-1.5 text-sm font-medium text-text-secondary hover:text-text-primary"
          >
            <ArrowLeft className="h-4 w-4" />
            {selectedTable.name}
          </button>
        ) : (
          <span className="flex items-center gap-2 text-sm font-semibold text-text-primary">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-brand-gradient text-xs font-bold text-white">
              S
            </div>
            {t("title")}
          </span>
        )}
        <div className="ml-auto flex items-center gap-3">
          <span className="hidden text-sm text-text-secondary sm:inline">
            {user?.full_name}
          </span>
          <Link
            href="/dashboard"
            className="hidden text-xs font-medium text-text-secondary hover:text-accent-primary sm:inline"
          >
            {t("backToDashboard")}
          </Link>
          <button
            onClick={() => logout()}
            aria-label={t("logout")}
            className="text-text-secondary hover:text-error"
          >
            <LogOut className="h-4.5 w-4.5" />
          </button>
        </div>
      </header>

      <main className="flex-1 overflow-y-auto pb-24">
        {!selectedTable ? (
          <div className="p-4">
            <h1 className="text-lg font-bold text-text-primary">{t("chooseTable")}</h1>
            {branches.length > 1 && (
              <select
                value={branchId ?? ""}
                onChange={(e) => setBranchId(e.target.value || null)}
                className="mt-3 rounded-lg border border-border-default bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent-primary"
              >
                {branches.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.name}
                  </option>
                ))}
              </select>
            )}

            {tables.type === "data" ? (
              <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
                {tables.data.map((table) => {
                  const disabled = table.status === "DISABLED";
                  return (
                    <button
                      key={table.id}
                      disabled={disabled}
                      onClick={() => selectTable(table)}
                      className={`flex flex-col items-start rounded-xl border p-4 text-left shadow-sm transition-all disabled:cursor-not-allowed disabled:opacity-50 ${
                        disabled
                          ? "border-border-default bg-background-secondary/50"
                          : `hover:-translate-y-0.5 hover:shadow-md active:scale-[0.98] ${TABLE_STATUS_STYLES[table.status] ?? ""}`
                      }`}
                    >
                      <div className="flex w-full items-start justify-between">
                        <div
                          className={`flex h-10 w-10 items-center justify-center rounded-lg ${TABLE_BADGE_STYLES[table.status] ?? "bg-background-secondary text-text-secondary"}`}
                        >
                          <Table2 className="h-5 w-5" />
                        </div>
                        <span
                          className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${TABLE_BADGE_STYLES[table.status] ?? ""}`}
                        >
                          {tc(`tableStatus.${table.status}`)}
                        </span>
                      </div>
                      <p className="mt-2 font-semibold text-text-primary">{table.name}</p>
                      <div className="mt-1 flex items-center gap-0.5 text-text-secondary">
                        {Array.from({
                          length: Math.min(table.capacity, MAX_SEAT_ICONS),
                        }).map((_, i) => (
                          <Armchair key={i} className="h-3 w-3" aria-hidden="true" />
                        ))}
                        {table.capacity > MAX_SEAT_ICONS && (
                          <span className="text-[11px]">+{table.capacity - MAX_SEAT_ICONS}</span>
                        )}
                      </div>
                    </button>
                  );
                })}
              </div>
            ) : (
              <div className="mt-4">
                <StateView
                  kind={tables.type}
                  message={tables.type === "error" ? tables.message : undefined}
                />
              </div>
            )}
          </div>
        ) : sentOrder ? (
          <div className="flex flex-col items-center gap-3 px-6 py-16 text-center">
            <CheckCircle2 className="h-14 w-14 text-success" />
            <h2 className="text-xl font-bold text-text-primary">{t("orderSentTitle")}</h2>
            <p className="text-sm text-text-secondary">
              {t("orderSentText", { number: sentOrder.order_number })}
            </p>
            <p className="text-lg font-bold text-text-primary">
              {formatMoney(sentOrder.total, sentOrder.currency)}
            </p>
            <div className="mt-4 flex flex-col gap-2 sm:flex-row">
              <Button onClick={startAnotherRound}>{t("addMore")}</Button>
              <Button variant="secondary" onClick={backToTables}>
                {t("otherTable")}
              </Button>
            </div>
          </div>
        ) : (
          <div>
            {/* Category chips */}
            <div className="flex gap-2 overflow-x-auto border-b border-border-default bg-surface px-4 py-3">
              <button
                onClick={() => setActiveCategory(null)}
                className={`shrink-0 rounded-full px-3.5 py-1.5 text-sm font-medium transition-colors ${
                  activeCategory === null
                    ? "bg-accent-primary text-white"
                    : "bg-background-secondary text-text-secondary hover:text-text-primary"
                }`}
              >
                {t("allCategories")}
              </button>
              {categories.map((c) => (
                <button
                  key={c.id}
                  onClick={() => setActiveCategory(c.id)}
                  className={`shrink-0 rounded-full px-3.5 py-1.5 text-sm font-medium transition-colors ${
                    activeCategory === c.id
                      ? "bg-accent-primary text-white"
                      : "bg-background-secondary text-text-secondary hover:text-text-primary"
                  }`}
                >
                  {c.name}
                </button>
              ))}
            </div>

            {/* Product grid */}
            <div className="p-4">
              {products.type === "data" ? (
                products.data.length === 0 ? (
                  <StateView kind="empty" message={t("menuEmpty")} />
                ) : (
                  <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
                    {products.data.map((product) => (
                      <button
                        key={product.id}
                        onClick={() => tapProduct(product)}
                        disabled={!product.is_available}
                        className="flex flex-col overflow-hidden rounded-xl border border-border-default bg-surface text-left shadow-sm transition-all hover:-translate-y-0.5 hover:shadow-md active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-40"
                      >
                        <div className="h-24 w-full bg-background-secondary">
                          {product.image_url ? (
                            // eslint-disable-next-line @next/next/no-img-element -- see ImageUploadField
                            <img
                              src={product.image_url}
                              alt={product.name}
                              className="h-full w-full object-cover"
                            />
                          ) : (
                            <div className="flex h-full w-full items-center justify-center text-text-secondary/40">
                              <ImageOff className="h-6 w-6" aria-hidden="true" />
                            </div>
                          )}
                        </div>
                        <div className="p-2.5">
                          <p className="line-clamp-1 text-sm font-medium text-text-primary">
                            {product.name}
                          </p>
                          <p className="mt-0.5 text-xs font-bold text-accent-primary">
                            {formatMoney(product.price, "UZS")}
                          </p>
                        </div>
                      </button>
                    ))}
                  </div>
                )
              ) : (
                <StateView
                  kind={products.type}
                  message={products.type === "error" ? products.message : undefined}
                />
              )}
            </div>
          </div>
        )}
      </main>

      {/* Floating cart bar */}
      {selectedTable && !sentOrder && cartCount > 0 && (
        <button
          onClick={() => setCartOpen(true)}
          className="fixed inset-x-4 bottom-4 z-30 flex items-center justify-between rounded-2xl bg-brand-gradient px-5 py-4 text-white shadow-lg shadow-accent-primary/30 transition-transform active:scale-[0.99]"
        >
          <span className="flex items-center gap-2 font-semibold">
            <ShoppingCart className="h-5 w-5" />
            {t("itemsCount", { count: cartCount })}
          </span>
          <span className="font-bold">{formatMoney(cartTotal, "UZS")}</span>
        </button>
      )}

      {/* Cart drawer */}
      {cartOpen && (
        <Modal open onClose={() => setCartOpen(false)} title={t("cartTitle")}>
          {cart.length === 0 ? (
            <p className="py-6 text-center text-sm text-text-secondary">{t("cartEmpty")}</p>
          ) : (
            <div className="space-y-3">
              <div className="max-h-72 space-y-3 overflow-y-auto pr-1">
                {cart.map((line) => (
                  <div
                    key={line.key}
                    className="flex items-start justify-between gap-2 rounded-lg border border-border-default p-3"
                  >
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-text-primary">
                        {line.product.name}
                      </p>
                      {Object.entries(line.selectedByGroup).map(([groupId, modIds]) => {
                        const group = line.product.modifier_groups.find((g) => g.id === groupId);
                        if (!group || modIds.length === 0) return null;
                        const names = modIds
                          .map((id) => group.modifiers.find((m) => m.id === id)?.name)
                          .filter(Boolean)
                          .join(", ");
                        return (
                          <p key={groupId} className="text-xs text-text-secondary">
                            {names}
                          </p>
                        );
                      })}
                      <p className="mt-1 text-xs font-semibold text-accent-primary">
                        {formatMoney(lineUnitPrice(line) * line.quantity, "UZS")}
                      </p>
                    </div>
                    <div className="flex shrink-0 items-center gap-1.5">
                      <button
                        onClick={() => updateQty(line.key, -1)}
                        aria-label={tc("actions.cancel")}
                        className="flex h-7 w-7 items-center justify-center rounded-lg border border-border-default text-text-secondary hover:bg-background-secondary"
                      >
                        <Minus className="h-3.5 w-3.5" />
                      </button>
                      <span className="w-5 text-center text-sm font-semibold text-text-primary">
                        {line.quantity}
                      </span>
                      <button
                        onClick={() => updateQty(line.key, 1)}
                        aria-label={t("addMore")}
                        className="flex h-7 w-7 items-center justify-center rounded-lg border border-border-default text-text-secondary hover:bg-background-secondary"
                      >
                        <Plus className="h-3.5 w-3.5" />
                      </button>
                      <button
                        onClick={() => removeLine(line.key)}
                        aria-label={tc("actions.delete")}
                        className="flex h-7 w-7 items-center justify-center rounded-lg text-text-secondary hover:bg-error/10 hover:text-error"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>

              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder={t("notesPlaceholder")}
                rows={2}
                className="w-full resize-none rounded-lg border border-border-default bg-background px-3 py-2 text-sm text-text-primary outline-none focus:border-accent-primary"
              />

              <div className="flex items-center justify-between border-t border-border-default pt-3">
                <span className="text-sm font-medium text-text-secondary">{t("total")}</span>
                <span className="text-lg font-bold text-text-primary">
                  {formatMoney(cartTotal, "UZS")}
                </span>
              </div>

              <Button
                className="w-full"
                size="lg"
                disabled={submitting}
                aria-busy={submitting}
                onClick={submitOrder}
              >
                {submitting ? t("sending") : t("sendOrder")}
              </Button>
            </div>
          )}
        </Modal>
      )}

      {/* Modifier picker */}
      {modifierProduct && (
        <ModifierPickerModal
          product={modifierProduct}
          onClose={() => setModifierProduct(null)}
          onConfirm={(selected, qty) => addWithModifiers(modifierProduct, selected, qty)}
        />
      )}
    </div>
  );
}

function ModifierPickerModal({
  product,
  onClose,
  onConfirm,
}: {
  product: ProductOut;
  onClose: () => void;
  onConfirm: (selectedByGroup: Record<string, string[]>, quantity: number) => void;
}) {
  const t = useTranslations("waiterPage");
  const [selected, setSelected] = useState<Record<string, string[]>>({});
  const [quantity, setQuantity] = useState(1);

  const toggle = (groupId: string, modifierId: string, maxSelections: number) => {
    setSelected((prev) => {
      const current = prev[groupId] ?? [];
      const isMulti = maxSelections > 1;
      if (current.includes(modifierId)) {
        return { ...prev, [groupId]: current.filter((m) => m !== modifierId) };
      }
      if (!isMulti) return { ...prev, [groupId]: [modifierId] };
      if (current.length >= maxSelections) {
        return { ...prev, [groupId]: [...current.slice(1), modifierId] };
      }
      return { ...prev, [groupId]: [...current, modifierId] };
    });
  };

  const isValid = product.modifier_groups.every(
    (group) => (selected[group.id] ?? []).length >= group.min_selections
  );

  const unitPrice =
    parseFloat(product.price) +
    Object.entries(selected).reduce((sum, [groupId, modIds]) => {
      const group = product.modifier_groups.find((g) => g.id === groupId);
      if (!group) return sum;
      return (
        sum +
        modIds.reduce((s, id) => {
          const mod = group.modifiers.find((m) => m.id === id);
          return s + (mod ? parseFloat(mod.price) : 0);
        }, 0)
      );
    }, 0);

  return (
    <Modal open onClose={onClose} title={product.name}>
      <div className="space-y-4">
        {product.modifier_groups.map((group) => (
          <div key={group.id}>
            <p className="mb-2 flex items-center gap-2 text-sm font-semibold text-text-primary">
              {group.name}
              {group.is_required && (
                <span className="rounded-full bg-error/10 px-2 py-0.5 text-[11px] font-medium text-error">
                  {t("required")}
                </span>
              )}
            </p>
            <div className="space-y-1.5">
              {group.modifiers.map((mod) => {
                const checked = (selected[group.id] ?? []).includes(mod.id);
                return (
                  <button
                    key={mod.id}
                    type="button"
                    onClick={() => toggle(group.id, mod.id, group.max_selections)}
                    className={`flex w-full items-center justify-between rounded-lg border px-3 py-2 text-left text-sm transition-colors ${
                      checked
                        ? "border-accent-primary bg-accent-primary/10 text-accent-primary"
                        : "border-border-default text-text-primary hover:bg-background-secondary"
                    }`}
                  >
                    <span>{mod.name}</span>
                    {parseFloat(mod.price) > 0 && (
                      <span className="font-medium">+{formatMoney(mod.price, "UZS")}</span>
                    )}
                  </button>
                );
              })}
            </div>
          </div>
        ))}

        <div className="flex items-center justify-between">
          <span className="text-sm font-medium text-text-secondary">{t("total")}</span>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setQuantity((q) => Math.max(1, q - 1))}
              className="flex h-8 w-8 items-center justify-center rounded-lg border border-border-default text-text-secondary hover:bg-background-secondary"
            >
              <Minus className="h-3.5 w-3.5" />
            </button>
            <span className="w-5 text-center font-semibold text-text-primary">{quantity}</span>
            <button
              onClick={() => setQuantity((q) => q + 1)}
              className="flex h-8 w-8 items-center justify-center rounded-lg border border-border-default text-text-secondary hover:bg-background-secondary"
            >
              <Plus className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>

        <Button
          className="w-full"
          disabled={!isValid}
          onClick={() => onConfirm(selected, quantity)}
        >
          {t("addToCart")} · {formatMoney(unitPrice * quantity, "UZS")}
        </Button>
      </div>
    </Modal>
  );
}
