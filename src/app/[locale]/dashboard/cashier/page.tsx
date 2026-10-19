"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { Minus, Plus, Trash2, Printer, RotateCcw, Split } from "lucide-react";
import {
  BranchOut,
  CategoryOut,
  OrderOut,
  ProductOut,
  SplitShare,
  TableOut,
  branchesApi,
  menuApi,
  ordersApi,
  paymentsApi,
  restaurantsApi,
  tablesApi,
} from "@/lib/api";
import { formatMoney } from "@/lib/format";
import { useAuth } from "@/lib/auth-context";
import Button from "@/components/Button";
import Modal from "@/components/Modal";
import PageHeader from "@/components/dashboard/PageHeader";
import ReceiptButton from "@/components/ReceiptButton";
import SearchField from "@/components/ui/SearchField";
import Tabs from "@/components/ui/Tabs";
import ProductCard from "@/components/ui/ProductCard";

interface CartLine {
  key: string;
  product: ProductOut;
  quantity: number;
  selectedByGroup: Record<string, string[]>;
}

const PAYMENT_METHODS = ["CASH", "CARD", "TRANSFER", "QR"] as const;

export default function CashierPage() {
  const t = useTranslations("cashierPage");
  const tc = useTranslations("common");
  const { can } = useAuth();

  const [branches, setBranches] = useState<BranchOut[]>([]);
  const [branchId, setBranchId] = useState<string | null>(null);
  const [currency, setCurrency] = useState("UZS");
  const [categories, setCategories] = useState<CategoryOut[]>([]);
  const [products, setProducts] = useState<ProductOut[]>([]);
  const [activeCategory, setActiveCategory] = useState<string | null>(null);
  const [tables, setTables] = useState<TableOut[]>([]);
  const [tableId, setTableId] = useState<string>("");

  const [lines, setLines] = useState<CartLine[]>([]);
  const [modifierProduct, setModifierProduct] = useState<ProductOut | null>(null);
  const [discountType, setDiscountType] = useState<"FIXED" | "PERCENT">("PERCENT");
  const [discountValue, setDiscountValue] = useState("0");

  const [submitting, setSubmitting] = useState(false);
  const [openOrder, setOpenOrder] = useState<OrderOut | null>(null);
  const [paymentRows, setPaymentRows] = useState<{ method: string; amount: string }[]>([]);
  const [paying, setPaying] = useState(false);
  const [splitOpen, setSplitOpen] = useState(false);
  const [splitParts, setSplitParts] = useState("2");
  const [splitShares, setSplitShares] = useState<SplitShare[] | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const searchRef = useRef<HTMLInputElement>(null);

  const canOrder = can("orders.create");
  const canDiscount = can("orders.discount");

  useEffect(() => {
    branchesApi.list().then((list) => {
      setBranches(list);
      setBranchId((prev) => prev ?? list[0]?.id ?? null);
    }).catch(() => {});
    restaurantsApi.getMine().then((r) => setCurrency(r.currency)).catch(() => {});
    menuApi.listCategories(100, 0).then(setCategories).catch(() => {});
    menuApi.listProducts(100, 0).then((page) => setProducts(page.items)).catch(() => {});
  }, []);

  useEffect(() => {
    if (!branchId) return;
    tablesApi.list(branchId).then((list) => setTables(list)).catch(() => {});
  }, [branchId]);

  const flash = (message: string) => {
    setNotice(message);
    setTimeout(() => setNotice(null), 3000);
  };

  const shownProducts = products.filter(
    (p) =>
      p.is_active &&
      (!activeCategory || p.category_id === activeCategory) &&
      (!search.trim() || p.name.toLowerCase().includes(search.trim().toLowerCase()))
  );

  // "/" jumps to product search (unless already typing in a field).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement | null;
      const typing = !!el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.tagName === "SELECT");
      if (e.key === "/" && !typing) {
        e.preventDefault();
        searchRef.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const addToCart = (product: ProductOut) => {
    if (product.modifier_groups.length > 0) {
      setModifierProduct(product);
      return;
    }
    setLines((prev) => {
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
        { key: `${Date.now()}-${Math.random()}`, product, quantity: 1, selectedByGroup: {} },
      ];
    });
  };

  const addConfiguredLine = (product: ProductOut, selectedByGroup: Record<string, string[]>) => {
    setLines((prev) => [
      ...prev,
      { key: `${Date.now()}-${Math.random()}`, product, quantity: 1, selectedByGroup },
    ]);
    setModifierProduct(null);
  };

  const updateQuantity = (key: string, delta: number) => {
    setLines((prev) =>
      prev
        .map((l) => (l.key === key ? { ...l, quantity: l.quantity + delta } : l))
        .filter((l) => l.quantity > 0)
    );
  };

  const removeLine = (key: string) => {
    setLines((prev) => prev.filter((l) => l.key !== key));
  };

  const lineTotal = (line: CartLine) => {
    let total = parseFloat(line.product.price) * line.quantity;
    for (const [groupId, modIds] of Object.entries(line.selectedByGroup)) {
      const group = line.product.modifier_groups.find((g) => g.id === groupId);
      if (!group) continue;
      for (const modId of modIds) {
        const mod = group.modifiers.find((m) => m.id === modId);
        if (mod) total += parseFloat(mod.price) * line.quantity;
      }
    }
    return total;
  };

  const cartSubtotal = useMemo(
    () => lines.reduce((sum, l) => sum + lineTotal(l), 0),
    [lines]
  );

  const resetSale = () => {
    setLines([]);
    setTableId("");
    setDiscountValue("0");
    setOpenOrder(null);
    setPaymentRows([]);
    setSplitShares(null);
    setSplitOpen(false);
  };

  const submitOrder = async () => {
    if (!branchId || lines.length === 0 || submitting) return;
    setSubmitting(true);
    try {
      const created = await ordersApi.create(
        {
          branch_id: branchId,
          table_id: tableId || null,
          source: "POS",
          discount_type: discountType,
          discount: discountValue || "0",
          items: lines.map((line) => ({
            product_id: line.product.id,
            quantity: line.quantity,
            modifiers: Object.values(line.selectedByGroup)
              .flat()
              .map((modifier_id) => ({ modifier_id })),
          })),
        },
        globalThis.crypto?.randomUUID?.() ?? `idem-${Date.now()}`
      );
      const opened = await ordersApi.updateStatus(created.id, "OPEN");
      setOpenOrder(opened);
      setPaymentRows([{ method: "CASH", amount: opened.total }]);
    } catch (err) {
      alert((err as Error).message);
    } finally {
      setSubmitting(false);
    }
  };

  const paidSoFar = paymentRows.reduce((sum, r) => sum + (parseFloat(r.amount) || 0), 0);
  const remaining = openOrder ? parseFloat(openOrder.total) - paidSoFar : 0;

  const finalizePayment = async () => {
    if (!openOrder || paying) return;
    setPaying(true);
    try {
      for (const row of paymentRows) {
        const amount = parseFloat(row.amount);
        if (!amount || amount <= 0) continue;
        await paymentsApi.add({ order_id: openOrder.id, amount: amount.toFixed(2), method: row.method });
      }
      const refreshed = await ordersApi.get(openOrder.id);
      setOpenOrder(refreshed);
      flash(t("paymentComplete"));
    } catch (err) {
      alert((err as Error).message);
    } finally {
      setPaying(false);
    }
  };

  const runSplitPreview = async () => {
    if (!openOrder) return;
    try {
      const preview = await ordersApi.previewSplit(openOrder.id, {
        mode: "person",
        parts: parseInt(splitParts, 10) || 2,
      });
      setSplitShares(preview.shares);
    } catch (err) {
      alert((err as Error).message);
    }
  };

  const useShareAsRow = (share: SplitShare) => {
    setPaymentRows((prev) => [...prev, { method: "CASH", amount: share.amount }]);
    setSplitOpen(false);
  };

  if (!canOrder) {
    return (
      <div className="p-6 text-sm text-text-secondary">{t("noAccess")}</div>
    );
  }

  return (
    <div>
      <PageHeader
        title={t("title")}
        description={t("description")}
        actions={
          <select
            value={branchId ?? ""}
            onChange={(e) => setBranchId(e.target.value || null)}
            className="rounded-lg border border-border-default bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent-primary"
          >
            {branches.map((b) => (
              <option key={b.id} value={b.id}>
                {b.name}
              </option>
            ))}
          </select>
        }
      />

      {notice && (
        <div className="mb-4 rounded-lg border border-success/30 bg-success/10 px-4 py-2 text-sm text-success">
          {notice}
        </div>
      )}

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[1fr_380px]">
        {/* Left: category tabs + product grid */}
        <div className="min-w-0">
          <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center">
            <SearchField
              ref={searchRef}
              value={search}
              onChange={setSearch}
              placeholder={tc("ui.search")}
              clearLabel={tc("ui.clear")}
              className="sm:w-64"
            />
            <Tabs
              value={activeCategory ?? "all"}
              onChange={(k) => setActiveCategory(k === "all" ? null : k)}
              className="min-w-0 flex-1"
              items={[
                { key: "all", label: t("allCategories") },
                ...categories.map((c) => ({ key: c.id, label: c.name })),
              ]}
            />
          </div>

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-4">
            {shownProducts.map((p) => (
              <ProductCard
                key={p.id}
                name={p.name}
                price={formatMoney(p.price, currency)}
                imageUrl={p.image_url}
                disabled={!p.is_available}
                badge={p.modifier_groups.length > 0 ? "+" : undefined}
                onClick={() => addToCart(p)}
              />
            ))}
            {shownProducts.length === 0 && (
              <p className="col-span-full py-12 text-center text-sm text-text-secondary">{tc("states.empty")}</p>
            )}
          </div>
        </div>

        {/* Right: cart + checkout */}
        <div className="flex flex-col rounded-xl border border-border-default bg-surface p-4 shadow-card lg:sticky lg:top-0 lg:max-h-[calc(100vh-8rem)] lg:self-start lg:overflow-y-auto">
          {!openOrder ? (
            <>
              <label className="mb-3 block text-sm font-medium text-text-primary">
                {t("table")}
                <select
                  value={tableId}
                  onChange={(e) => setTableId(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-border-default bg-background px-3 py-2 text-sm text-text-primary outline-none focus:border-accent-primary"
                >
                  <option value="">{t("walkIn")}</option>
                  {tables.map((tb) => (
                    <option key={tb.id} value={tb.id} disabled={tb.status === "OCCUPIED"}>
                      {tb.name} {tb.status === "OCCUPIED" ? `(${tc("tableStatus.OCCUPIED")})` : ""}
                    </option>
                  ))}
                </select>
              </label>

              <div className="flex-1 space-y-2 overflow-y-auto">
                {lines.length === 0 ? (
                  <p className="py-8 text-center text-sm text-text-secondary">{t("emptyCart")}</p>
                ) : (
                  lines.map((line) => (
                    <div key={line.key} className="rounded-lg border border-border-default p-2.5">
                      <div className="flex items-start justify-between gap-2">
                        <span className="text-sm font-medium text-text-primary">
                          {line.product.name}
                        </span>
                        <button
                          onClick={() => removeLine(line.key)}
                          className="text-text-secondary hover:text-error"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>
                      <div className="mt-1.5 flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => updateQuantity(line.key, -1)}
                            className="flex h-6 w-6 items-center justify-center rounded-md border border-border-default text-text-secondary hover:text-accent-primary"
                          >
                            <Minus className="h-3 w-3" />
                          </button>
                          <span className="w-5 text-center text-sm">{line.quantity}</span>
                          <button
                            onClick={() => updateQuantity(line.key, 1)}
                            className="flex h-6 w-6 items-center justify-center rounded-md border border-border-default text-text-secondary hover:text-accent-primary"
                          >
                            <Plus className="h-3 w-3" />
                          </button>
                        </div>
                        <span className="text-sm font-semibold text-text-primary">
                          {formatMoney(lineTotal(line).toFixed(2), currency)}
                        </span>
                      </div>
                    </div>
                  ))
                )}
              </div>

              {canDiscount && (
                <div className="mt-3 border-t border-border-default pt-3">
                  <label className="mb-1 block text-xs font-medium text-text-secondary">
                    {t("discount")}
                  </label>
                  <div className="flex gap-2">
                    <select
                      value={discountType}
                      onChange={(e) => setDiscountType(e.target.value as "FIXED" | "PERCENT")}
                      className="rounded-lg border border-border-default bg-background px-2 py-1.5 text-sm text-text-primary outline-none focus:border-accent-primary"
                    >
                      <option value="PERCENT">%</option>
                      <option value="FIXED">{currency}</option>
                    </select>
                    <input
                      type="number"
                      min={0}
                      value={discountValue}
                      onChange={(e) => setDiscountValue(e.target.value)}
                      className="w-full rounded-lg border border-border-default bg-background px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent-primary"
                    />
                  </div>
                </div>
              )}

              <div className="mt-3 flex items-center justify-between border-t border-border-default pt-3">
                <span className="text-sm text-text-secondary">{t("subtotal")}</span>
                <span className="text-base font-semibold text-text-primary">
                  {formatMoney(cartSubtotal.toFixed(2), currency)}
                </span>
              </div>

              <Button
                className="mt-3 w-full justify-center"
                disabled={lines.length === 0 || submitting}
                onClick={submitOrder}
              >
                {submitting ? tc("states.loading") : t("checkout")}
              </Button>
            </>
          ) : (
            <>
              <p className="text-sm text-text-secondary">
                {t("orderNumber")} #{openOrder.order_number}
              </p>
              <div className="mt-2 flex items-center justify-between">
                <span className="text-sm text-text-secondary">{t("total")}</span>
                <span className="text-lg font-bold text-text-primary">
                  {formatMoney(openOrder.total, currency)}
                </span>
              </div>

              <div className="mt-3 flex items-center justify-between">
                <span className="text-sm font-medium text-text-secondary">{t("payments")}</span>
                <button
                  onClick={() => setSplitOpen(true)}
                  className="flex items-center gap-1 text-xs font-medium text-accent-primary hover:underline"
                >
                  <Split className="h-3.5 w-3.5" />
                  {t("splitBill")}
                </button>
              </div>

              <div className="mt-2 space-y-2">
                {paymentRows.map((row, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <select
                      value={row.method}
                      onChange={(e) =>
                        setPaymentRows((prev) =>
                          prev.map((r, idx) => (idx === i ? { ...r, method: e.target.value } : r))
                        )
                      }
                      className="rounded-lg border border-border-default bg-background px-2 py-1.5 text-sm text-text-primary outline-none focus:border-accent-primary"
                    >
                      {PAYMENT_METHODS.map((m) => (
                        <option key={m} value={m}>
                          {tc(`paymentMethod.${m}`)}
                        </option>
                      ))}
                    </select>
                    <input
                      type="number"
                      min={0}
                      value={row.amount}
                      onChange={(e) =>
                        setPaymentRows((prev) =>
                          prev.map((r, idx) => (idx === i ? { ...r, amount: e.target.value } : r))
                        )
                      }
                      className="w-full rounded-lg border border-border-default bg-background px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent-primary"
                    />
                    <button
                      onClick={() => setPaymentRows((prev) => prev.filter((_, idx) => idx !== i))}
                      className="text-text-secondary hover:text-error"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                ))}
                <button
                  onClick={() =>
                    setPaymentRows((prev) => [...prev, { method: "CASH", amount: remaining > 0 ? remaining.toFixed(2) : "0" }])
                  }
                  className="text-xs font-medium text-accent-primary hover:underline"
                >
                  + {t("addPaymentRow")}
                </button>
              </div>

              <div className="mt-3 flex items-center justify-between border-t border-border-default pt-3 text-sm">
                <span className="text-text-secondary">{t("remaining")}</span>
                <span className={remaining > 0.001 ? "font-semibold text-warning" : "font-semibold text-success"}>
                  {formatMoney(remaining.toFixed(2), currency)}
                </span>
              </div>

              {openOrder.status === "COMPLETED" ? (
                <div className="mt-3 space-y-2">
                  <p className="rounded-lg bg-success/10 px-3 py-2 text-center text-sm font-medium text-success">
                    {t("paymentComplete")}
                  </p>
                  <ReceiptButton orderId={openOrder.id} className="flex w-full items-center justify-center gap-1.5 rounded-lg bg-accent-primary px-3 py-2 text-sm font-medium text-white hover:brightness-110" />
                  <Button variant="secondary" className="w-full justify-center" onClick={resetSale}>
                    <RotateCcw className="h-4 w-4" />
                    {t("newSale")}
                  </Button>
                </div>
              ) : (
                <Button className="mt-3 w-full justify-center" disabled={paying} onClick={finalizePayment}>
                  {paying ? tc("states.loading") : t("finalizePayment")}
                </Button>
              )}
            </>
          )}
        </div>
      </div>

      {modifierProduct && (
        <ModifierPickerModal
          product={modifierProduct}
          currency={currency}
          onClose={() => setModifierProduct(null)}
          onConfirm={(selected) => addConfiguredLine(modifierProduct, selected)}
        />
      )}

      {splitOpen && openOrder && (
        <Modal open onClose={() => setSplitOpen(false)} title={t("splitBill")}>
          <div className="flex items-center gap-2">
            <input
              type="number"
              min={2}
              value={splitParts}
              onChange={(e) => setSplitParts(e.target.value)}
              className="w-24 rounded-lg border border-border-default bg-background px-3 py-2 text-sm text-text-primary outline-none focus:border-accent-primary"
            />
            <Button size="sm" onClick={runSplitPreview}>
              {t("calculate")}
            </Button>
          </div>
          {splitShares && (
            <ul className="mt-4 space-y-2">
              {splitShares.map((share, i) => (
                <li
                  key={i}
                  className="flex items-center justify-between rounded-lg border border-border-default px-3 py-2"
                >
                  <span className="text-sm text-text-primary">{share.label}</span>
                  <div className="flex items-center gap-3">
                    <span className="text-sm font-semibold">
                      {formatMoney(share.amount, currency)}
                    </span>
                    <Button size="sm" variant="secondary" onClick={() => useShareAsRow(share)}>
                      {t("addPaymentRow")}
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Modal>
      )}
    </div>
  );
}

function ModifierPickerModal({
  product,
  currency,
  onClose,
  onConfirm,
}: {
  product: ProductOut;
  currency: string;
  onClose: () => void;
  onConfirm: (selected: Record<string, string[]>) => void;
}) {
  const t = useTranslations("cashierPage");
  const tc = useTranslations("common");
  const [selected, setSelected] = useState<Record<string, string[]>>({});

  const toggle = (groupId: string, modifierId: string, maxSelections: number) => {
    setSelected((prev) => {
      const current = prev[groupId] ?? [];
      const next = current.includes(modifierId)
        ? current.filter((m) => m !== modifierId)
        : current.length >= maxSelections
          ? [...current.slice(1), modifierId]
          : [...current, modifierId];
      return { ...prev, [groupId]: next };
    });
  };

  const isValid = product.modifier_groups.every(
    (g) => (selected[g.id] ?? []).length >= g.min_selections
  );

  return (
    <Modal open onClose={onClose} title={product.name}>
      <div className="space-y-4">
        {product.modifier_groups.map((group) => (
          <div key={group.id}>
            <p className="mb-1.5 text-sm font-medium text-text-primary">
              {group.name}
              {group.min_selections > 0 && (
                <span className="ml-1 text-xs text-error">*</span>
              )}
            </p>
            <div className="space-y-1.5">
              {group.modifiers.map((mod) => {
                const isSelected = (selected[group.id] ?? []).includes(mod.id);
                return (
                  <button
                    key={mod.id}
                    onClick={() => toggle(group.id, mod.id, group.max_selections)}
                    className={`flex w-full items-center justify-between rounded-lg border px-3 py-2 text-sm transition-colors ${
                      isSelected
                        ? "border-accent-primary bg-accent-primary/5 text-accent-primary"
                        : "border-border-default text-text-primary hover:border-accent-primary/40"
                    }`}
                  >
                    <span>{mod.name}</span>
                    <span>{formatMoney(mod.price, currency)}</span>
                  </button>
                );
              })}
            </div>
          </div>
        ))}
        <Button
          className="w-full justify-center"
          disabled={!isValid}
          onClick={() => onConfirm(selected)}
        >
          {tc("actions.add")}
        </Button>
      </div>
    </Modal>
  );
}
