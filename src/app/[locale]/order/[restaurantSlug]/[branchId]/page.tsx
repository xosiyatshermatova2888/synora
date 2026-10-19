"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { Minus, Plus, Trash2, ShoppingCart, ArrowLeft, CheckCircle2, Loader2 } from "lucide-react";
import {
  PublicMenuOut,
  PublicOrderItemIn,
  PublicProductOut,
  PublicTableOut,
  publicApi,
} from "@/lib/api";
import { formatMoney } from "@/lib/format";

interface CartLine {
  key: string;
  product: PublicProductOut;
  quantity: number;
  selectedByGroup: Record<string, string[]>;
}

type Step = "menu" | "cart" | "checkout" | "done";

export default function PublicOrderPage() {
  const t = useTranslations("publicOrderPage");
  const params = useParams<{ restaurantSlug: string; branchId: string }>();
  const restaurantSlug = params.restaurantSlug;
  const branchId = params.branchId;

  const [menu, setMenu] = useState<PublicMenuOut | null>(null);
  const [tables, setTables] = useState<PublicTableOut[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [activeCategory, setActiveCategory] = useState<string | null>(null);
  const [lines, setLines] = useState<CartLine[]>([]);
  const [modifierProduct, setModifierProduct] = useState<PublicProductOut | null>(null);
  const [step, setStep] = useState<Step>("menu");

  const [customerName, setCustomerName] = useState("");
  const [customerPhone, setCustomerPhone] = useState("");
  const [tableId, setTableId] = useState("");
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [orderResult, setOrderResult] = useState<{ order_number: number; total: string } | null>(null);

  const [idempotencyKey] = useState<string>(() => {
    if (typeof globalThis !== "undefined" && globalThis.crypto?.randomUUID) {
      return globalThis.crypto.randomUUID();
    }
    return `idem-${Date.now()}`;
  });

  useEffect(() => {
    if (!restaurantSlug || !branchId) return;
    Promise.all([publicApi.menu(restaurantSlug), publicApi.tables(restaurantSlug, branchId)])
      .then(([m, tbls]) => {
        setMenu(m);
        setTables(tbls);
        setActiveCategory(m.categories[0]?.id ?? null);
      })
      .catch((err) => setError((err as Error).message));
  }, [restaurantSlug, branchId]);

  const addToCart = (product: PublicProductOut) => {
    if (product.modifier_groups.length > 0) {
      setModifierProduct(product);
      return;
    }
    setLines((prev) => {
      const existing = prev.find(
        (l) => l.product.id === product.id && Object.keys(l.selectedByGroup).length === 0
      );
      if (existing) {
        return prev.map((l) => (l.key === existing.key ? { ...l, quantity: l.quantity + 1 } : l));
      }
      return [...prev, { key: `${Date.now()}-${Math.random()}`, product, quantity: 1, selectedByGroup: {} }];
    });
  };

  const addConfiguredLine = (product: PublicProductOut, selectedByGroup: Record<string, string[]>) => {
    setLines((prev) => [
      ...prev,
      { key: `${Date.now()}-${Math.random()}`, product, quantity: 1, selectedByGroup },
    ]);
    setModifierProduct(null);
  };

  const updateQuantity = (key: string, delta: number) => {
    setLines((prev) =>
      prev.map((l) => (l.key === key ? { ...l, quantity: l.quantity + delta } : l)).filter((l) => l.quantity > 0)
    );
  };

  const removeLine = (key: string) => setLines((prev) => prev.filter((l) => l.key !== key));

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

  const cartTotal = useMemo(() => lines.reduce((sum, l) => sum + lineTotal(l), 0), [lines]);
  const cartCount = useMemo(() => lines.reduce((sum, l) => sum + l.quantity, 0), [lines]);
  const currency = menu?.currency ?? "UZS";

  const submitOrder = async () => {
    if (!restaurantSlug || !branchId || !tableId || !customerName.trim() || lines.length === 0) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const items: PublicOrderItemIn[] = lines.map((line) => ({
        product_id: line.product.id,
        quantity: line.quantity,
        modifiers: Object.values(line.selectedByGroup)
          .flat()
          .map((modifier_id) => ({ modifier_id })),
      }));
      const result = await publicApi.createOrder(
        {
          restaurant_slug: restaurantSlug,
          branch_id: branchId,
          table_id: tableId,
          customer_name: customerName.trim(),
          customer_phone: customerPhone.trim() || undefined,
          notes: notes.trim() || undefined,
          items,
        },
        idempotencyKey
      );
      setOrderResult(result);
      setStep("done");
    } catch (err) {
      setSubmitError((err as Error).message);
    } finally {
      setSubmitting(false);
    }
  };

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background p-6 text-center">
        <p className="text-sm text-error">{t("notFound")}</p>
      </div>
    );
  }

  if (!menu) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <Loader2 className="h-8 w-8 animate-spin text-accent-primary" />
      </div>
    );
  }

  if (step === "done" && orderResult) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-background p-6 text-center">
        <CheckCircle2 className="h-16 w-16 text-success" />
        <h1 className="text-xl font-bold text-text-primary">{t("orderPlaced")}</h1>
        <p className="text-text-secondary">
          {t("orderNumber")} #{orderResult.order_number}
        </p>
        <p className="text-2xl font-bold text-text-primary">{formatMoney(orderResult.total, currency)}</p>
        <p className="max-w-xs text-sm text-text-secondary">{t("thankYou")}</p>
      </div>
    );
  }

  const activeCategoryData = menu.categories.find((c) => c.id === activeCategory);

  return (
    <div className="min-h-screen bg-background pb-24">
      <header className="sticky top-0 z-10 border-b border-border-default bg-surface/95 px-4 py-3 backdrop-blur-sm">
        <h1 className="text-lg font-bold text-text-primary">{menu.restaurant_name}</h1>
        <p className="text-xs text-text-secondary">{t("scanOrderSubtitle")}</p>
      </header>

      {step === "menu" && (
        <>
          <div className="flex gap-2 overflow-x-auto px-4 py-3">
            {menu.categories.map((c) => (
              <button
                key={c.id}
                onClick={() => setActiveCategory(c.id)}
                className={`shrink-0 rounded-full px-4 py-2 text-sm font-semibold transition-colors ${
                  activeCategory === c.id
                    ? "bg-accent-primary text-white"
                    : "bg-background-secondary text-text-secondary"
                }`}
              >
                {c.name}
              </button>
            ))}
          </div>

          <div className="grid grid-cols-2 gap-3 px-4 pb-4 sm:grid-cols-3">
            {(activeCategoryData?.products ?? []).map((p) => (
              <button
                key={p.id}
                onClick={() => addToCart(p)}
                className="flex flex-col items-start rounded-xl border border-border-default bg-surface p-3 text-left shadow-sm active:scale-[0.98]"
              >
                {p.image_url && (
                  <img src={p.image_url} alt={p.name} className="mb-2 h-24 w-full rounded-lg object-cover" />
                )}
                <span className="text-sm font-semibold text-text-primary">{p.name}</span>
                <span className="mt-1 text-sm font-medium text-accent-primary">
                  {formatMoney(p.price, currency)}
                </span>
              </button>
            ))}
          </div>
        </>
      )}

      {step === "cart" && (
        <div className="px-4 py-4">
          <button
            onClick={() => setStep("menu")}
            className="mb-4 flex items-center gap-1.5 text-sm text-text-secondary"
          >
            <ArrowLeft className="h-4 w-4" />
            {t("backToMenu")}
          </button>
          {lines.length === 0 ? (
            <p className="py-12 text-center text-sm text-text-secondary">{t("emptyCart")}</p>
          ) : (
            <div className="space-y-2">
              {lines.map((line) => (
                <div key={line.key} className="rounded-lg border border-border-default bg-surface p-3">
                  <div className="flex items-start justify-between gap-2">
                    <span className="text-sm font-medium text-text-primary">{line.product.name}</span>
                    <button onClick={() => removeLine(line.key)} className="text-text-secondary hover:text-error">
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                  <div className="mt-2 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => updateQuantity(line.key, -1)}
                        className="flex h-7 w-7 items-center justify-center rounded-md border border-border-default"
                      >
                        <Minus className="h-3 w-3" />
                      </button>
                      <span className="w-5 text-center text-sm">{line.quantity}</span>
                      <button
                        onClick={() => updateQuantity(line.key, 1)}
                        className="flex h-7 w-7 items-center justify-center rounded-md border border-border-default"
                      >
                        <Plus className="h-3 w-3" />
                      </button>
                    </div>
                    <span className="text-sm font-semibold text-text-primary">
                      {formatMoney(lineTotal(line).toFixed(2), currency)}
                    </span>
                  </div>
                </div>
              ))}
              <div className="flex items-center justify-between border-t border-border-default pt-3">
                <span className="text-sm text-text-secondary">{t("total")}</span>
                <span className="text-lg font-bold text-text-primary">
                  {formatMoney(cartTotal.toFixed(2), currency)}
                </span>
              </div>
              <button
                onClick={() => setStep("checkout")}
                className="mt-2 w-full rounded-xl bg-accent-primary py-3 text-sm font-semibold text-white"
              >
                {t("goToCheckout")}
              </button>
            </div>
          )}
        </div>
      )}

      {step === "checkout" && (
        <div className="px-4 py-4">
          <button
            onClick={() => setStep("cart")}
            className="mb-4 flex items-center gap-1.5 text-sm text-text-secondary"
          >
            <ArrowLeft className="h-4 w-4" />
            {t("backToCart")}
          </button>
          <div className="space-y-4">
            <div>
              <label className="mb-1 block text-sm font-medium text-text-primary">{t("yourName")}</label>
              <input
                value={customerName}
                onChange={(e) => setCustomerName(e.target.value)}
                required
                className="w-full rounded-lg border border-border-default bg-surface px-3 py-2.5 text-sm text-text-primary outline-none focus:border-accent-primary"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-text-primary">{t("phoneOptional")}</label>
              <input
                value={customerPhone}
                onChange={(e) => setCustomerPhone(e.target.value)}
                className="w-full rounded-lg border border-border-default bg-surface px-3 py-2.5 text-sm text-text-primary outline-none focus:border-accent-primary"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-text-primary">{t("tableNumber")}</label>
              <select
                value={tableId}
                onChange={(e) => setTableId(e.target.value)}
                required
                className="w-full rounded-lg border border-border-default bg-surface px-3 py-2.5 text-sm text-text-primary outline-none focus:border-accent-primary"
              >
                <option value="">{t("selectTable")}</option>
                {tables.map((tb) => (
                  <option key={tb.id} value={tb.id}>
                    {tb.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-text-primary">{t("notesOptional")}</label>
              <input
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                className="w-full rounded-lg border border-border-default bg-surface px-3 py-2.5 text-sm text-text-primary outline-none focus:border-accent-primary"
              />
            </div>

            {submitError && <p className="text-sm text-error">{submitError}</p>}

            <div className="flex items-center justify-between border-t border-border-default pt-3">
              <span className="text-sm text-text-secondary">{t("total")}</span>
              <span className="text-lg font-bold text-text-primary">
                {formatMoney(cartTotal.toFixed(2), currency)}
              </span>
            </div>
            <button
              onClick={submitOrder}
              disabled={submitting || !tableId || !customerName.trim()}
              className="w-full rounded-xl bg-accent-primary py-3 text-sm font-semibold text-white disabled:opacity-50"
            >
              {submitting ? t("placing") : t("placeOrder")}
            </button>
          </div>
        </div>
      )}

      {step === "menu" && cartCount > 0 && (
        <button
          onClick={() => setStep("cart")}
          className="fixed inset-x-4 bottom-4 z-10 flex items-center justify-between rounded-xl bg-accent-primary px-5 py-3.5 text-white shadow-lg"
        >
          <span className="flex items-center gap-2 text-sm font-semibold">
            <ShoppingCart className="h-4 w-4" />
            {t("cartCount", { count: cartCount })}
          </span>
          <span className="text-sm font-bold">{formatMoney(cartTotal.toFixed(2), currency)}</span>
        </button>
      )}

      {modifierProduct && (
        <ModifierPickerModal
          product={modifierProduct}
          currency={currency}
          onClose={() => setModifierProduct(null)}
          onConfirm={(selected) => addConfiguredLine(modifierProduct, selected)}
        />
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
  product: PublicProductOut;
  currency: string;
  onClose: () => void;
  onConfirm: (selected: Record<string, string[]>) => void;
}) {
  const t = useTranslations("publicOrderPage");
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

  const isValid = product.modifier_groups.every((g) => (selected[g.id] ?? []).length >= g.min_selections);

  return (
    <div className="fixed inset-0 z-20 flex items-end justify-center bg-black/40 sm:items-center" onClick={onClose}>
      <div
        className="max-h-[85vh] w-full max-w-md overflow-y-auto rounded-t-2xl bg-surface p-5 sm:rounded-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="mb-4 text-base font-bold text-text-primary">{product.name}</h2>
        <div className="space-y-4">
          {product.modifier_groups.map((group) => (
            <div key={group.id}>
              <p className="mb-1.5 text-sm font-medium text-text-primary">
                {group.name}
                {group.min_selections > 0 && <span className="ml-1 text-xs text-error">*</span>}
              </p>
              <div className="space-y-1.5">
                {group.modifiers.map((mod) => {
                  const isSelected = (selected[group.id] ?? []).includes(mod.id);
                  return (
                    <button
                      key={mod.id}
                      onClick={() => toggle(group.id, mod.id, group.max_selections)}
                      className={`flex w-full items-center justify-between rounded-lg border px-3 py-2.5 text-sm ${
                        isSelected
                          ? "border-accent-primary bg-accent-primary/5 text-accent-primary"
                          : "border-border-default text-text-primary"
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
          <button
            disabled={!isValid}
            onClick={() => onConfirm(selected)}
            className="w-full rounded-xl bg-accent-primary py-3 text-sm font-semibold text-white disabled:opacity-50"
          >
            {t("addToCart")}
          </button>
        </div>
      </div>
    </div>
  );
}
