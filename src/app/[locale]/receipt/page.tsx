"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { Loader2, Printer, X } from "lucide-react";
import {
  OrderOut,
  PaymentOut,
  RestaurantOut,
  TableOut,
  ordersApi,
  paymentsApi,
  restaurantsApi,
  tablesApi,
} from "@/lib/api";
import { formatMoney, formatDateTime } from "@/lib/format";

/**
 * Print-only receipt view — deliberately a bare page (no dashboard shell)
 * so `window.print()` only ever prints the receipt itself. Opened in a new
 * tab from Payments/Orders via `?order=<id>`; sized for an 80mm thermal
 * printer through @page in the print stylesheet below.
 */
export default function ReceiptPage() {
  const t = useTranslations("receiptPage");
  const tc = useTranslations("common");
  const orderId = useSearchParams().get("order");

  const [order, setOrder] = useState<OrderOut | null>(null);
  const [restaurant, setRestaurant] = useState<RestaurantOut | null>(null);
  const [table, setTable] = useState<TableOut | null>(null);
  const [payments, setPayments] = useState<PaymentOut[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!orderId) return;
    void (async () => {
      try {
        const [o, r] = await Promise.all([
          ordersApi.get(orderId),
          restaurantsApi.getMine(),
        ]);
        setOrder(o);
        setRestaurant(r);
        if (o.table_id) {
          tablesApi.get(o.table_id).then(setTable).catch(() => {});
        }
        paymentsApi.listForOrder(orderId).then(setPayments).catch(() => {});
      } catch (err) {
        setError((err as Error).message);
      }
    })();
  }, [orderId]);

  if (!orderId) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background p-6 text-center">
        <p className="text-sm text-error">{t("missingOrder")}</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background p-6 text-center">
        <p className="text-sm text-error">{error}</p>
      </div>
    );
  }

  if (!order || !restaurant) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <Loader2 className="h-8 w-8 animate-spin text-accent-primary" />
      </div>
    );
  }

  const paidTotal = payments
    .filter((p) => p.status === "PAID")
    .reduce((sum, p) => sum + parseFloat(p.amount), 0);
  const lastMethod = payments.length > 0 ? payments[payments.length - 1].method : null;

  return (
    <div className="min-h-screen bg-background-secondary py-8">
      <style>{`
        @media print {
          @page { size: 80mm auto; margin: 3mm; }
          .no-print { display: none !important; }
          body { background: #fff !important; }
        }
      `}</style>

      <div className="no-print mx-auto mb-4 flex max-w-[320px] items-center justify-between px-1">
        <button
          onClick={() => window.close()}
          className="flex items-center gap-1.5 text-sm text-text-secondary hover:text-text-primary"
        >
          <X className="h-4 w-4" />
          {t("close")}
        </button>
        <button
          onClick={() => window.print()}
          className="flex items-center gap-1.5 rounded-lg bg-accent-primary px-3 py-1.5 text-sm font-medium text-white hover:brightness-110"
        >
          <Printer className="h-4 w-4" />
          {t("print")}
        </button>
      </div>

      <div className="mx-auto w-full max-w-[320px] bg-white p-4 font-mono text-[13px] leading-relaxed text-black shadow-lg">
        <div className="text-center">
          <p className="text-base font-bold">{restaurant.name}</p>
          {restaurant.address && <p>{restaurant.address}</p>}
          {restaurant.phone && <p>{t("phone")}: {restaurant.phone}</p>}
        </div>

        <div className="my-2 border-t border-dashed border-black" />

        <p>
          {t("orderNumber")}: #{order.order_number}
        </p>
        <p>{formatDateTime(order.created_at)}</p>
        {table && (
          <p>
            {t("table")}: {table.name}
          </p>
        )}

        <div className="my-2 border-t border-dashed border-black" />

        {order.items.map((item) => (
          <div key={item.id} className="mb-1.5">
            <p>{item.product_name_snapshot}</p>
            <div className="flex justify-between">
              <span>
                {item.quantity} × {formatMoney(item.unit_price, order.currency)}
              </span>
              <span>
                {formatMoney(
                  (parseFloat(item.unit_price) * item.quantity).toFixed(2),
                  order.currency
                )}
              </span>
            </div>
            {item.modifiers.map((mod) => (
              <div key={mod.id} className="flex justify-between pl-3 text-xs">
                <span>
                  + {mod.modifier_name_snapshot} ×{mod.quantity}
                </span>
                <span>
                  {formatMoney(
                    (parseFloat(mod.price) * mod.quantity).toFixed(2),
                    order.currency
                  )}
                </span>
              </div>
            ))}
          </div>
        ))}

        <div className="my-2 border-t border-dashed border-black" />

        <div className="flex justify-between">
          <span>{t("subtotal")}</span>
          <span>{formatMoney(order.subtotal, order.currency)}</span>
        </div>
        {parseFloat(order.discount) > 0 && (
          <div className="flex justify-between">
            <span>{t("discount")}</span>
            <span>-{formatMoney(order.discount, order.currency)}</span>
          </div>
        )}
        {parseFloat(order.tax) > 0 && (
          <div className="flex justify-between">
            <span>{t("tax")}</span>
            <span>{formatMoney(order.tax, order.currency)}</span>
          </div>
        )}
        <div className="my-2 border-t border-dashed border-black" />
        <div className="flex justify-between text-base font-bold">
          <span>{t("total")}</span>
          <span>{formatMoney(order.total, order.currency)}</span>
        </div>

        {payments.length > 0 && (
          <>
            <div className="my-2 border-t border-dashed border-black" />
            {lastMethod && (
              <div className="flex justify-between">
                <span>{t("paymentMethod")}</span>
                <span>{tc(`paymentMethod.${lastMethod}`)}</span>
              </div>
            )}
            <div className="flex justify-between">
              <span>{t("paid")}</span>
              <span>{formatMoney(paidTotal.toFixed(2), order.currency)}</span>
            </div>
          </>
        )}

        <div className="my-3 border-t border-dashed border-black" />
        <p className="text-center">{t("thankYou")}</p>
        <p className="text-center text-xs">{restaurant.name}</p>
      </div>
    </div>
  );
}
