"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useLiveReload } from "@/lib/use-live-reload";
import { useLocale, useTranslations } from "next-intl";
import { Wallet, Banknote, CreditCard, Receipt, ExternalLink, Printer, MapPin } from "lucide-react";
import {
  BranchOut,
  CashShiftOut,
  OrderOut,
  PaymentOut,
  branchesApi,
  ordersApi,
  paymentsApi,
  printersApi,
  restaurantsApi,
} from "@/lib/api";
import type { LoadState } from "@/lib/load-state";
import { loadingState, errorState, dataState } from "@/lib/load-state";
import { formatMoney, formatDateTime } from "@/lib/format";
import { useAuth } from "@/lib/auth-context";
import Modal from "@/components/Modal";
import Button from "@/components/Button";
import StateView from "@/components/dashboard/StateView";
import PageHeader from "@/components/dashboard/PageHeader";
import StatusBadge from "@/components/ui/StatusBadge";
import { useToast } from "@/components/ui/Toast";
import { useTenantWebSocket } from "@/lib/use-tenant-websocket";

const PAYMENT_METHODS = ["CASH", "CARD", "TRANSFER", "QR"];

const ACTIVE_STATUSES = ["DRAFT", "OPEN", "PARTIALLY_PAID"];

interface OrderWithPayments {
  order: OrderOut;
  payments: PaymentOut[];
  paid: number;
  remaining: number;
}

export default function PaymentsPage() {
  const t = useTranslations("paymentsPage");
  const tc = useTranslations("common");
  const { can } = useAuth();
  const toast = useToast();
  const locale = useLocale();

  const [branches, setBranches] = useState<BranchOut[]>([]);
  const [branchId, setBranchId] = useState<string | null>(null);
  const [orders, setOrders] = useState<LoadState<OrderWithPayments[]>>(loadingState());
  const [shifts, setShifts] = useState<CashShiftOut[]>([]);
  const [currency, setCurrency] = useState("UZS");
  const [paymentTarget, setPaymentTarget] = useState<OrderWithPayments | null>(null);
  const [shiftModal, setShiftModal] = useState<"open" | "close" | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [caps, setCaps] = useState({ kitchen: false, receipt: false });
  const [receiptOffer, setReceiptOffer] = useState<{ id: string; number: number } | null>(null);
  const refreshTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const canFinanceRead = can("finance.read");
  const canFinanceManage = can("finance.manage");
  const canUpdateOrders = can("orders.update");

  const openShift = shifts.find((s) => s.status === "OPEN");

  const loadData = useCallback(async (silent = false) => {
    if (!branchId) return;
    if (!silent) setOrders(loadingState());
    try {
      const page = await ordersApi.list({ branch_id: branchId, limit: 100, offset: 0 });
      const active = page.items.filter((o) => ACTIVE_STATUSES.includes(o.status));
      const withPayments: OrderWithPayments[] = await Promise.all(
        active.map(async (order) => {
          const paymentList = await paymentsApi
            .listForOrder(order.id)
            .catch(() => [] as PaymentOut[]);
          const paid = paymentList.reduce(
            (sum, p) => sum + (p.status === "PAID" ? parseFloat(p.amount) : 0),
            0
          );
          const total = parseFloat(order.total);
          return {
            order,
            payments: paymentList,
            paid,
            remaining: Math.max(0, total - paid),
          };
        })
      );
      setOrders(dataState(withPayments));
    } catch (err) {
      setOrders(errorState((err as Error).message));
    }
  }, [branchId]);

  const loadShifts = useCallback(async () => {
    if (!branchId) return;
    try {
      const list = await paymentsApi.listCashShifts(branchId);
      setShifts(list);
    } catch {
      setShifts([]);
    }
  }, [branchId]);

  useEffect(() => {
    branchesApi.list().then((list) => {
      setBranches(list);
      setBranchId((prev) => prev ?? list[0]?.id ?? null);
    }).catch(() => {});
    restaurantsApi.getMine().then((r) => setCurrency(r.currency)).catch(() => {});
  }, []);

  useEffect(() => {
    if (branchId === null) return;
    void (async () => {
      try {
        const page = await ordersApi.list({ branch_id: branchId, limit: 100, offset: 0 });
        const active = page.items.filter((o) => ACTIVE_STATUSES.includes(o.status));
        const withPayments: OrderWithPayments[] = await Promise.all(
          active.map(async (order) => {
            const paymentList = await paymentsApi
              .listForOrder(order.id)
              .catch(() => [] as PaymentOut[]);
            const paid = paymentList.reduce(
              (sum, p) => sum + (p.status === "PAID" ? parseFloat(p.amount) : 0),
              0
            );
            const total = parseFloat(order.total);
            return {
              order,
              payments: paymentList,
              paid,
              remaining: Math.max(0, total - paid),
            };
          })
        );
        setOrders(dataState(withPayments));
      } catch (err) {
        setOrders(errorState((err as Error).message));
      }
    })();
    void (async () => {
      try {
        const list = await paymentsApi.listCashShifts(branchId);
        setShifts(list);
      } catch {
        setShifts([]);
      }
    })();
  }, [branchId]);

  useEffect(() => {
    if (!branchId) return;
    printersApi.capabilities(branchId).then(setCaps).catch(() => setCaps({ kitchen: false, receipt: false }));
  }, [branchId]);

  // Live: a waiter/Telegram/QR order or a "bring the bill" request arrives while
  // the cashier is on this page -> refetch quietly (debounced).
  const scheduleRefresh = useCallback(() => {
    if (refreshTimer.current) clearTimeout(refreshTimer.current);
    refreshTimer.current = setTimeout(() => void loadData(true), 400);
  }, [loadData]);
  useTenantWebSocket<unknown>("/ws/kitchen", null, scheduleRefresh);
  useTenantWebSocket<unknown>("/ws/notifications", null, scheduleRefresh);

  const printDoc = async (orderId: string, kind: "PRECHECK" | "RECEIPT") => {
    if (!caps.receipt) {
      // No network printer for this branch: fall back to the browser print page.
      window.open(
        `/${locale}/receipt?order=${orderId}${kind === "PRECHECK" ? "&kind=precheck" : ""}`,
        "_blank",
        "noopener,noreferrer"
      );
      return;
    }
    try {
      const job = await ordersApi.print(orderId, kind);
      if (job.status === "PRINTED") toast.success(t("printed"));
      else toast.error(`${t("printFailed")}: ${job.error ?? ""}`);
    } catch (err) {
      toast.error((err as Error).message);
    }
  };

  const flash = (message: string, ms = 3000) => {
    setNotice(message);
    setTimeout(() => setNotice(null), ms);
  };

  const handleRecordPayment = async (
    target: OrderWithPayments,
    amount: string,
    method: string,
    reference: string
  ) => {
    try {
      await paymentsApi.add({
        order_id: target.order.id,
        amount,
        method,
        reference: reference.trim() || null,
      });
      setPaymentTarget(null);
      flash(t("paymentRecorded"));
      if (parseFloat(amount) >= target.remaining) {
        setReceiptOffer({ id: target.order.id, number: target.order.order_number });
      }
      loadData();
    } catch (err) {
      alert((err as Error).message);
    }
  };

  const markDelivered = async (order: OrderOut) => {
    try {
      await ordersApi.updateKitchenStatus(order.id, "SERVED");
      toast.success(t("delivered"));
      void loadData(true);
    } catch (err) {
      toast.error((err as Error).message);
    }
  };

  const handlePayOnline = async (target: OrderWithPayments) => {
    try {
      const { checkout_url } = await paymentsApi.paymeCheckout(
        target.order.id,
        target.remaining.toFixed(2)
      );
      window.open(checkout_url, "_blank", "noopener,noreferrer");
      flash(t("paymeOpened"));
    } catch (err) {
      alert((err as Error).message);
    }
  };

  const handleOpenShift = async (openingBalance: string) => {
    if (!branchId) return;
    try {
      await paymentsApi.openCashShift(branchId, openingBalance);
      setShiftModal(null);
      flash(t("shiftOpened"));
      loadShifts();
    } catch (err) {
      alert((err as Error).message);
    }
  };

  const handleCloseShift = async (actualClosingBalance: string) => {
    if (!openShift) return;
    try {
      const closed = await paymentsApi.closeCashShift(
        openShift.id,
        actualClosingBalance,
        openShift.version
      );
      setShiftModal(null);
      const diff = parseFloat(closed.actual_closing_balance ?? "0") - parseFloat(closed.expected_closing_balance ?? "0");
      flash(
        t("shiftClosedResult", {
          expected: formatMoney(closed.expected_closing_balance ?? "0", currency),
          actual: formatMoney(closed.actual_closing_balance ?? "0", currency),
          diff: formatMoney(diff.toFixed(2), currency),
        }),
        12000
      );
      loadShifts();
    } catch (err) {
      alert((err as Error).message);
    }
  };

  // A waiter/Telegram order arriving, or any payment, refreshes the list by itself.
  useLiveReload(() => {
    void loadData(true);
    void loadShifts();
  });

  const methodToText = (method: string) => tc(`paymentMethod.${method}`) ?? method;
  const statusToText = (status: string) => tc(`orderStatus.${status}`) ?? status;

  const recentPayments: PaymentOut[] = (orders.type === "data" ? orders.data : [])
    .flatMap((entry) => entry.payments)
    .sort((a, b) => b.created_at.localeCompare(a.created_at))
    .slice(0, 10);

  return (
    <div>
      <PageHeader title={t("title")} description={t("description")} />

      {notice && (
        <div className="mb-4 rounded-lg border border-success/30 bg-success/10 px-4 py-2 text-sm text-success">
          {notice}
        </div>
      )}

      {receiptOffer && (
        <div className="mb-4 flex flex-wrap items-center gap-3 rounded-lg border border-accent-primary/30 bg-accent-primary/10 px-4 py-3 text-sm">
          <span className="font-medium text-text-primary">{t("paidInFull", { n: receiptOffer.number })}</span>
          <Button
            size="sm"
            className="ml-auto"
            onClick={() => {
              void printDoc(receiptOffer.id, "RECEIPT");
              setReceiptOffer(null);
            }}
          >
            <Printer className="h-4 w-4" />
            {t("printReceipt")}
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setReceiptOffer(null)}>
            {tc("actions.close")}
          </Button>
        </div>
      )}

      <select
        value={branchId ?? ""}
        onChange={(e) => setBranchId(e.target.value || null)}
        className="mb-5 rounded-lg border border-border-default bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent-primary"
      >
        {branches.length === 0 && <option value="">—</option>}
        {branches.map((b) => (
          <option key={b.id} value={b.id}>
            {b.name}
          </option>
        ))}
      </select>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {/* Orders to collect */}
        <section className="lg:col-span-2">
          <h2 className="mb-3 flex items-center gap-2 text-base font-semibold text-text-primary">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent-primary/10 text-accent-primary">
              <Wallet className="h-4.5 w-4.5" />
            </span>
            {t("openOrdersTitle")}
          </h2>

          {orders.type === "data" ? (
            orders.data.filter((entry) => entry.remaining > 0).length === 0 ? (
              <StateView kind="empty" message={t("noOpenOrders")} />
            ) : (
              <ul className="space-y-3">
                {orders.data
                  .filter((entry) => entry.remaining > 0)
                  .sort((a, b) => Number(!!b.order.bill_requested_at) - Number(!!a.order.bill_requested_at))
                  .map((entry) => (
                    <li
                      key={entry.order.id}
                      className={`rounded-xl border bg-surface p-4 shadow-sm transition-shadow hover:shadow-md ${
                        entry.order.bill_requested_at ? "border-info/50 ring-1 ring-info/30" : "border-border-default"
                      }`}
                    >
                      <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
                        <div className="min-w-24">
                          <p className="font-semibold text-text-primary">
                            #{entry.order.order_number}
                          </p>
                          <p className="text-xs text-text-secondary">
                            {statusToText(entry.order.status)}
                            {entry.order.waiter_name ? ` · ${entry.order.waiter_name}` : ""}
                          </p>
                          {entry.order.bill_requested_at && (
                            <StatusBadge tone="info" className="mt-1">
                              {t("billRequested")}
                            </StatusBadge>
                          )}
                        </div>
                        <p className="text-sm text-text-secondary">
                          {entry.order.items.length} {t("itemCount")}
                        </p>
                        {(entry.order.customer_name || entry.order.delivery_address) && (
                          <p className="flex basis-full items-start gap-1.5 text-xs text-text-secondary">
                            <MapPin className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                            <span>
                              {[entry.order.customer_name, entry.order.customer_phone, entry.order.delivery_address]
                                .filter(Boolean)
                                .join(" · ")}
                            </span>
                          </p>
                        )}
                        <div className="ml-auto space-x-4 text-right">
                          <span className="text-xs text-text-secondary">
                            {t("paid")}{" "}
                            <span className="font-semibold text-text-primary">
                              {formatMoney(entry.paid, currency)}
                            </span>
                          </span>
                          <span className="text-xs text-text-secondary">
                            {t("remaining")}{" "}
                            <span className="font-bold text-accent-primary">
                              {formatMoney(entry.remaining, currency)}
                            </span>
                          </span>
                        </div>
                        <Button size="sm" variant="secondary" onClick={() => void printDoc(entry.order.id, "PRECHECK")}>
                          <Printer className="h-4 w-4" />
                          {t("printPrecheck")}
                        </Button>
                        {canUpdateOrders && entry.order.delivery_type && entry.order.kitchen_status !== "SERVED" && (
                          <Button size="sm" variant="secondary" onClick={() => void markDelivered(entry.order)}>
                            {entry.order.delivery_type === "PICKUP" ? t("markHandedOver") : t("markDelivered")}
                          </Button>
                        )}
                        {canUpdateOrders && (
                          <Button
                            size="sm"
                            variant="secondary"
                            onClick={() => setPaymentTarget(entry)}
                          >
                            <CreditCard className="h-4 w-4" />
                            {t("recordPayment")}
                          </Button>
                        )}
                        {canFinanceManage && (
                          <Button
                            size="sm"
                            onClick={() => handlePayOnline(entry)}
                          >
                            <ExternalLink className="h-4 w-4" />
                            {t("payOnline")}
                          </Button>
                        )}
                      </div>
                    </li>
                  ))}
              </ul>
            )
          ) : (
            <StateView
              kind={orders.type}
              message={orders.type === "error" ? orders.message : undefined}
              onRetry={orders.type === "error" ? () => loadData() : undefined}
            />
          )}
        </section>

        {/* Cash shift + recent payments */}
        <aside className="space-y-4">
          <section className="rounded-xl border border-border-default bg-surface p-5">
            <h2 className="mb-3 flex items-center gap-2 text-base font-semibold text-text-primary">
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-success/10 text-success">
                <Banknote className="h-4.5 w-4.5" />
              </span>
              {t("cashShiftTitle")}
            </h2>

            {openShift ? (
              <div className="space-y-2 text-sm">
                <div className="flex items-center justify-between">
                  <span className="text-text-secondary">{t("openedAt")}</span>
                  <span className="font-medium text-text-primary">
                    {formatDateTime(openShift.opened_at)}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-text-secondary">{t("openingBalance")}</span>
                  <span className="font-medium text-text-primary">
                    {formatMoney(openShift.opening_balance, currency)}
                  </span>
                </div>
                {openShift.expected_closing_balance && (
                  <div className="flex items-center justify-between">
                    <span className="text-text-secondary">{t("expectedBalance")}</span>
                    <span className="font-medium text-text-primary">
                      {formatMoney(openShift.expected_closing_balance, currency)}
                    </span>
                  </div>
                )}
                <div className="mt-1 flex items-center justify-center gap-1.5 rounded-full bg-success/10 px-2.5 py-1 text-center text-xs font-semibold text-success">
                  <span className="h-1.5 w-1.5 rounded-full bg-success" />
                  {t("shiftOpen")}
                </div>
                {canFinanceManage && (
                  <Button
                    size="sm"
                    variant="secondary"
                    className="mt-3 w-full"
                    onClick={() => setShiftModal("close")}
                  >
                    {t("closeShift")}
                  </Button>
                )}
              </div>
            ) : (
              <div className="space-y-3">
                <p className="text-sm text-text-secondary">{t("shiftClosed")}</p>
                {canFinanceManage && (
                  <Button
                    size="sm"
                    className="w-full"
                    onClick={() => setShiftModal("open")}
                  >
                    {t("openShift")}
                  </Button>
                )}
              </div>
            )}
          </section>

          {canFinanceRead && (
            <section className="rounded-xl border border-border-default bg-surface p-5">
              <h2 className="mb-3 text-base font-semibold text-text-primary">{t("shiftHistory")}</h2>
              {shifts.filter((x) => x.status === "CLOSED").length === 0 ? (
                <p className="py-3 text-center text-sm text-text-secondary">{t("shiftHistoryEmpty")}</p>
              ) : (
                <ul className="divide-y divide-border-default">
                  {shifts
                    .filter((x) => x.status === "CLOSED")
                    .slice(0, 10)
                    .map((x) => {
                      const diff = parseFloat(x.actual_closing_balance ?? "0") - parseFloat(x.expected_closing_balance ?? "0");
                      const tone = diff === 0 ? "text-success" : diff < 0 ? "text-error" : "text-warning";
                      const label = diff === 0 ? t("diffMatch") : diff < 0 ? t("diffShortage") : t("diffSurplus");
                      return (
                        <li key={x.id} className="space-y-1 py-3 text-sm">
                          <div className="flex items-center justify-between text-xs text-text-secondary">
                            <span>{formatDateTime(x.opened_at)}</span>
                            <span>→ {x.closed_at ? formatDateTime(x.closed_at) : ""}</span>
                          </div>
                          <div className="flex items-center justify-between">
                            <span className="text-text-secondary">{t("openingBalance")}</span>
                            <span className="text-text-primary">{formatMoney(x.opening_balance, currency)}</span>
                          </div>
                          <div className="flex items-center justify-between">
                            <span className="text-text-secondary">{t("expectedBalance")}</span>
                            <span className="text-text-primary">{formatMoney(x.expected_closing_balance ?? "0", currency)}</span>
                          </div>
                          <div className="flex items-center justify-between">
                            <span className="text-text-secondary">{t("actualBalance")}</span>
                            <span className="font-medium text-text-primary">{formatMoney(x.actual_closing_balance ?? "0", currency)}</span>
                          </div>
                          <div className={`flex items-center justify-between font-semibold ${tone}`}>
                            <span>{t("difference")}: {label}</span>
                            <span>{diff > 0 ? "+" : ""}{formatMoney(diff.toFixed(2), currency)}</span>
                          </div>
                        </li>
                      );
                    })}
                </ul>
              )}
            </section>
          )}

          {canFinanceRead && (
            <section className="rounded-xl border border-border-default bg-surface p-5">
              <h2 className="mb-3 flex items-center gap-2 text-base font-semibold text-text-primary">
                <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent-ai/10 text-accent-ai">
                  <Receipt className="h-4.5 w-4.5" />
                </span>
                {t("paymentsTitle")}
              </h2>
              {recentPayments.length === 0 ? (
                <p className="py-6 text-center text-sm text-text-secondary">
                  {t("noPayments")}
                </p>
              ) : (
                <ul className="space-y-2">
                  {recentPayments.map((payment) => (
                    <li
                      key={payment.id}
                      className="flex items-center justify-between gap-2 text-sm"
                    >
                      <div className="min-w-0">
                        <p className="truncate font-medium text-text-primary">
                          {methodToText(payment.method)}
                        </p>
                        <p className="text-xs text-text-secondary">
                          {formatDateTime(payment.created_at)}
                        </p>
                      </div>
                      <span className="shrink-0 font-semibold text-success">
                        {formatMoney(payment.amount, currency)}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          )}
        </aside>
      </div>

      {/* Record payment modal */}
      {paymentTarget && (
        <PaymentFormModal
          currency={currency}
          defaultAmount={paymentTarget.remaining}
          onClose={() => setPaymentTarget(null)}
          onSubmit={(amount, method, reference) =>
            handleRecordPayment(paymentTarget, amount, method, reference)
          }
        />
      )}

      {shiftModal === "open" && (
        <ShiftFormModal
          title={t("openShift")}
          label={t("openingBalance")}
          defaultAmount="0.00"
          submitLabel={t("openShift")}
          onClose={() => setShiftModal(null)}
          onSubmit={handleOpenShift}
        />
      )}

      {shiftModal === "close" && (
        <ShiftFormModal
          title={t("closeShift")}
          label={t("closingBalance")}
          defaultAmount={openShift?.expected_closing_balance ?? "0.00"}
          submitLabel={t("closeShift")}
          onClose={() => setShiftModal(null)}
          onSubmit={handleCloseShift}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Record payment form
// ---------------------------------------------------------------------------
function PaymentFormModal({
  currency,
  defaultAmount,
  onClose,
  onSubmit,
}: {
  currency: string;
  defaultAmount: number;
  onClose: () => void;
  onSubmit: (amount: string, method: string, reference: string) => void;
}) {
  const t = useTranslations("paymentsPage");
  const tc = useTranslations("common");
  const [amount, setAmount] = useState(defaultAmount.toFixed(2));
  const [method, setMethod] = useState("CASH");
  const [reference, setReference] = useState("");

  return (
    <Modal open onClose={onClose} title={t("recordPayment")}>
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          onSubmit(amount, method, reference);
        }}
      >
        <div>
          <label className="mb-1 block text-sm font-medium text-text-primary">
            {t("amount")}
          </label>
          <input
            type="number"
            step="0.01"
            min="0.01"
            required
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            className="w-full rounded-lg border border-border-default bg-background px-3 py-2 text-sm text-text-primary outline-none focus:border-accent-primary"
          />
          <p className="mt-1 text-xs text-text-secondary">{currency}</p>
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-text-primary">
            {t("method")}
          </label>
          <select
            value={method}
            onChange={(e) => setMethod(e.target.value)}
            className="w-full rounded-lg border border-border-default bg-background px-3 py-2 text-sm text-text-primary outline-none focus:border-accent-primary"
          >
            {PAYMENT_METHODS.map((m) => (
              <option key={m} value={m}>
                {tc(`paymentMethod.${m}`)}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-text-primary">
            {t("reference")}
          </label>
          <input
            value={reference}
            onChange={(e) => setReference(e.target.value)}
            placeholder={t("referencePlaceholder")}
            className="w-full rounded-lg border border-border-default bg-background px-3 py-2 text-sm text-text-primary outline-none focus:border-accent-primary"
          />
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

// ---------------------------------------------------------------------------
// Cash shift form
// ---------------------------------------------------------------------------
function ShiftFormModal({
  title,
  label,
  defaultAmount,
  submitLabel,
  onClose,
  onSubmit,
}: {
  title: string;
  label: string;
  defaultAmount: string;
  submitLabel: string;
  onClose: () => void;
  onSubmit: (amount: string) => void;
}) {
  const tc = useTranslations("common");
  const [amount, setAmount] = useState(defaultAmount);

  return (
    <Modal open onClose={onClose} title={title}>
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          onSubmit(amount);
        }}
      >
        <div>
          <label className="mb-1 block text-sm font-medium text-text-primary">
            {label}
          </label>
          <input
            type="number"
            step="0.01"
            min="0"
            required
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            className="w-full rounded-lg border border-border-default bg-background px-3 py-2 text-sm text-text-primary outline-none focus:border-accent-primary"
          />
        </div>
        <div className="flex justify-end gap-2">
          <Button variant="secondary" size="sm" onClick={onClose}>
            {tc("actions.cancel")}
          </Button>
          <Button type="submit" size="sm">
            {submitLabel}
          </Button>
        </div>
      </form>
    </Modal>
  );
}