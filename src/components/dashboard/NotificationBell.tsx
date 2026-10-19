"use client";

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { Bell, CheckCheck } from "lucide-react";
import { useRouter } from "@/i18n/routing";
import { NotificationEvent, NotificationOut, notificationsApi } from "@/lib/api";
import { useTenantWebSocket } from "@/lib/use-tenant-websocket";
import { formatDateTime } from "@/lib/format";
import { useSubscription } from "@/lib/subscription-context";

const NOTIFICATION_ICON: Record<NotificationOut["type"], string> = {
  NEW_ORDER: "bg-accent-primary",
  LOW_STOCK: "bg-warning",
  PAYMENT: "bg-success",
  ORDER_CANCELLED: "bg-error",
  BILL_REQUEST: "bg-info",
  SUBSCRIPTION: "bg-accent-primary",
};

export default function NotificationBell() {
  const t = useTranslations("notifications");
  const router = useRouter();
  const { refresh: refreshSubscription } = useSubscription();
  const [items, setItems] = useState<NotificationOut[]>([]);
  const [open, setOpen] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);

  const unreadCount = items.filter((n) => !n.is_read).length;

  const load = () => {
    notificationsApi.list().then(setItems).catch(() => {});
  };

  useEffect(load, []);

  useTenantWebSocket<NotificationEvent>("/ws/notifications", null, (msg) => {
    if (msg.event !== "notification") return;
    setItems((prev) => [msg.notification, ...prev].slice(0, 30));
    // A payment was approved/rejected: unlock (or re-lock) modules right away.
    if (msg.notification.type === "SUBSCRIPTION") void refreshSubscription();
  });

  useEffect(() => {
    if (!open) return;
    const onOutside = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    const onEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onOutside);
    document.addEventListener("keydown", onEscape);
    return () => {
      document.removeEventListener("mousedown", onOutside);
      document.removeEventListener("keydown", onEscape);
    };
  }, [open]);

  const handleClick = async (n: NotificationOut) => {
    if (!n.is_read) {
      setItems((prev) => prev.map((x) => (x.id === n.id ? { ...x, is_read: true } : x)));
      notificationsApi.markRead(n.id).catch(() => {});
    }
    setOpen(false);
    if (n.link) router.push(n.link);
  };

  const markAllRead = async () => {
    setItems((prev) => prev.map((x) => ({ ...x, is_read: true })));
    notificationsApi.markAllRead().catch(() => {});
  };

  return (
    <div className="relative" ref={panelRef}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-label={t("title")}
        className="relative flex h-9 w-9 items-center justify-center rounded-lg text-text-secondary hover:bg-background-secondary hover:text-text-primary"
      >
        <Bell className="h-5 w-5" />
        {unreadCount > 0 && (
          <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-error px-1 text-[10px] font-bold text-white">
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-11 z-50 w-80 rounded-xl border border-border-default bg-surface shadow-lg">
          <div className="flex items-center justify-between border-b border-border-default px-4 py-2.5">
            <span className="text-sm font-semibold text-text-primary">{t("title")}</span>
            {unreadCount > 0 && (
              <button
                type="button"
                onClick={() => void markAllRead()}
                className="flex items-center gap-1 text-xs font-medium text-accent-primary hover:opacity-80"
              >
                <CheckCheck className="h-3.5 w-3.5" />
                {t("markAllRead")}
              </button>
            )}
          </div>
          <div className="max-h-96 overflow-y-auto">
            {items.length === 0 ? (
              <p className="px-4 py-6 text-center text-sm text-text-secondary">{t("empty")}</p>
            ) : (
              <ul>
                {items.map((n) => (
                  <li key={n.id}>
                    <button
                      type="button"
                      onClick={() => void handleClick(n)}
                      className={`flex w-full items-start gap-2.5 border-b border-border-default px-4 py-3 text-left text-sm hover:bg-background-secondary ${
                        n.is_read ? "" : "bg-accent-primary/[0.04]"
                      }`}
                    >
                      <span
                        className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${NOTIFICATION_ICON[n.type]} ${n.is_read ? "opacity-30" : ""}`}
                      />
                      <span className="min-w-0 flex-1">
                        <span className="block font-medium text-text-primary">{n.title}</span>
                        {n.body && (
                          <span className="mt-0.5 block truncate text-xs text-text-secondary">{n.body}</span>
                        )}
                        <span className="mt-0.5 block text-xs text-text-secondary">
                          {formatDateTime(n.created_at)}
                        </span>
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
