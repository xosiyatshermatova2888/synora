"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { Loader2, Printer, X } from "lucide-react";
import { OrderOut, RestaurantOut, TableOut, ordersApi, restaurantsApi, tablesApi } from "@/lib/api";
import { formatDateTime } from "@/lib/format";

/**
 * Print-only kitchen ticket — a bare page (no dashboard shell), same
 * mechanism as `receipt/page.tsx` (window.print(), @page sizing, 58/80mm
 * toggle). Opened in a new tab from the Kitchen board via `?order=<id>`.
 */
export default function KitchenTicketPage() {
  return (
    <Suspense fallback={null}>
      <KitchenTicketContent />
    </Suspense>
  );
}

function KitchenTicketContent() {
  const t = useTranslations("kitchenTicketPage");
  const searchParams = useSearchParams();
  const orderId = searchParams.get("order");
  const printWidth = searchParams.get("width") === "58" ? 58 : 80;

  const [order, setOrder] = useState<OrderOut | null>(null);
  const [restaurant, setRestaurant] = useState<RestaurantOut | null>(null);
  const [table, setTable] = useState<TableOut | null>(null);
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

  const containerWidth = printWidth === 58 ? 240 : 320;

  return (
    <div className="min-h-screen bg-background-secondary py-8">
      <style>{`
        @media print {
          @page { size: ${printWidth}mm auto; margin: 3mm; }
          .no-print { display: none !important; }
          body { background: #fff !important; }
        }
      `}</style>

      <div
        className="no-print mx-auto mb-4 flex items-center justify-between px-1"
        style={{ maxWidth: containerWidth }}
      >
        <button
          onClick={() => window.close()}
          className="flex items-center gap-1.5 text-sm text-text-secondary hover:text-text-primary"
        >
          <X className="h-4 w-4" />
          {t("close")}
        </button>
        <div className="flex items-center gap-2">
          <a
            href={`?order=${orderId}&width=${printWidth === 58 ? "80" : "58"}`}
            className="rounded-lg border border-border-default px-2.5 py-1.5 text-xs font-medium text-text-secondary hover:border-accent-primary/60 hover:text-accent-primary"
          >
            {printWidth === 58 ? "80mm" : "58mm"}
          </a>
          <button
            onClick={() => window.print()}
            className="flex items-center gap-1.5 rounded-lg bg-accent-primary px-3 py-1.5 text-sm font-medium text-white hover:brightness-110"
          >
            <Printer className="h-4 w-4" />
            {t("print")}
          </button>
        </div>
      </div>

      <div
        className="mx-auto w-full bg-white p-4 font-mono leading-relaxed text-black shadow-lg"
        style={{ maxWidth: containerWidth, fontSize: printWidth === 58 ? 12 : 13 }}
      >
        <div className="text-center">
          <p className="text-base font-bold">{restaurant.name}</p>
          <p className="text-sm font-bold">{t("heading")}</p>
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
        {order.waiter_name && (
          <p>
            {t("waiter")}: {order.waiter_name}
          </p>
        )}

        {(order.delivery_type || order.customer_phone) && (
          <>
            <div className="my-2 border-t border-dashed border-black" />
            <p className="font-bold">
              {order.delivery_type === "PICKUP" ? t("pickup") : order.delivery_type === "DELIVERY" ? t("delivery") : t("customer")}
            </p>
            {order.customer_name && <p>{order.customer_name}</p>}
            {order.customer_phone && (
              <p>
                {t("phone")}: {order.customer_phone}
              </p>
            )}
            {order.delivery_type === "DELIVERY" && order.delivery_address && (
              <p>
                {t("address")}: {order.delivery_address}
              </p>
            )}
            {order.delivery_note && <p>{order.delivery_note}</p>}
          </>
        )}

        <div className="my-2 border-t border-dashed border-black" />

        {order.items.map((item) => (
          <div key={item.id} className="mb-1.5">
            <div className="flex gap-2 text-sm font-bold">
              <span>{item.quantity}×</span>
              <span>{item.product_name_snapshot}</span>
            </div>
            {item.modifiers.map((mod) => (
              <p key={mod.id} className="pl-5 text-xs">
                + {mod.modifier_name_snapshot}
                {mod.quantity > 1 ? ` ×${mod.quantity}` : ""}
              </p>
            ))}
            {item.notes && <p className="pl-5 text-xs italic">{item.notes}</p>}
          </div>
        ))}

        {order.notes && (
          <>
            <div className="my-2 border-t border-dashed border-black" />
            <p className="text-sm">
              {t("note")}: {order.notes}
            </p>
          </>
        )}

        <div className="my-3 border-t border-dashed border-black" />
      </div>
    </div>
  );
}
