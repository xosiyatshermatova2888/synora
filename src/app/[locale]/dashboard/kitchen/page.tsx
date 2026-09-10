"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { ChefHat, AlertTriangle, Clock } from "lucide-react";
import {
  BranchOut,
  KitchenEvent,
  KitchenTicketOut,
  KitchenTicketStatus,
  authApi,
  branchesApi,
  getAccessToken,
  kitchenApi,
  ordersApi,
} from "@/lib/api";
import type { LoadState } from "@/lib/load-state";
import { loadingState, errorState, dataState } from "@/lib/load-state";
import { formatDateTime } from "@/lib/format";
import { useAuth } from "@/lib/auth-context";
import StateView from "@/components/dashboard/StateView";
import PageHeader from "@/components/dashboard/PageHeader";

const ACTIVE_STATUSES: KitchenTicketStatus[] = ["NEW", "PREPARING", "READY"];

const COLUMNS: { key: KitchenTicketStatus; labelKey: string; dot: string }[] = [
  { key: "NEW", labelKey: "columnNew", dot: "bg-accent-primary" },
  { key: "PREPARING", labelKey: "columnPreparing", dot: "bg-warning" },
  { key: "READY", labelKey: "columnReady", dot: "bg-success" },
];

function minutesBetween(from: number, iso: string): number {
  return Math.max(0, Math.floor((from - new Date(iso).getTime()) / 60000));
}

export default function KitchenPage() {
  const t = useTranslations("kitchenPage");
  const { can } = useAuth();

  const [branches, setBranches] = useState<BranchOut[]>([]);
  const [branchId, setBranchId] = useState<string | null>(null);
  const [board, setBoard] = useState<LoadState<KitchenTicketOut[]>>(loadingState());
  const [connected, setConnected] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [now, setNow] = useState(0);
  const [notice, setNotice] = useState<string | null>(null);

  const canUpdateOrders = can("orders.update");

  // -------------------------------------------------------------------------
  // Initial load: branches + first board fetch
  // -------------------------------------------------------------------------
  const loadBoard = useCallback(async () => {
    if (!branchId) return;
    setBoard(loadingState());
    try {
      const items = await kitchenApi.listTickets(branchId);
      setBoard(dataState(items));
    } catch (err) {
      setBoard(errorState((err as Error).message));
    }
  }, [branchId]);

  useEffect(() => {
    branchesApi
      .list()
      .then((list) => {
        setBranches(list);
        setBranchId((prev) => prev ?? list[0]?.id ?? null);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!branchId) return;
    let cancelled = false;
    void (async () => {
      try {
        const items = await kitchenApi.listTickets(branchId);
        if (!cancelled) setBoard(dataState(items));
      } catch (err) {
        if (!cancelled) setBoard(errorState((err as Error).message));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [branchId]);

  // Elapsed-time ticker (only relevant while the board is open).
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 15000);
    return () => clearInterval(id);
  }, []);

  const flash = (message: string) => {
    setNotice(message);
    window.setTimeout(() => setNotice(null), 3000);
  };

  // -------------------------------------------------------------------------
  // WebSocket: branch-scoped, authenticated, self-healing
  // -------------------------------------------------------------------------
  useEffect(() => {
    if (!branchId) return;
    let mounted = true;
    let attempt = 0;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;
    let ws: WebSocket | null = null;

    const applyEvent = (msg: KitchenEvent) => {
      if (!branchId) return;
      if (msg.event === "ticket_removed") {
        if (msg.branch_id && msg.branch_id !== branchId) return;
        setBoard((prev) => {
          if (prev.type !== "data") return prev;
          return dataState(
            prev.data.filter((t) => t.order_id !== msg.order_id)
          );
        });
        return;
      }
      const ticket = msg.ticket;
      if (!ticket) return;
      setBoard((prev) => {
        if (prev.type !== "data") return prev;
        const rest = prev.data.filter((t) => t.id !== ticket.id);
        if (!ACTIVE_STATUSES.includes(ticket.status)) return dataState(rest);
        const next = [...rest, ticket];
        next.sort(
          (a, b) =>
            new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
        );
        return dataState(next);
      });
    };

    const refetch = () => {
      kitchenApi.listTickets(branchId).then((items) => {
        if (mounted) setBoard(dataState(items));
      }).catch(() => {});
    };

    const scheduleRetry = () => {
      if (!mounted) return;
      setConnected(false);
      const delay = Math.min(30000, 1000 * 2 ** attempt);
      attempt += 1;
      retryTimer = setTimeout(() => {
        // Refresh the access token silently before reconnecting (it may have
        // expired); then retry. No second refresh mechanism — reuse authApi.
        authApi
          .refresh()
          .then((ok) => {
            if (mounted && ok) connect();
            else if (mounted) scheduleRetry();
          })
          .catch(() => {
            if (mounted) scheduleRetry();
          });
      }, delay);
    };

    const connect = () => {
      const token = getAccessToken();
      if (!token) {
        scheduleRetry();
        return;
      }
      const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
      const url = `${proto}//${window.location.host}/api/v1/ws/kitchen?token=${encodeURIComponent(token)}&branch_id=${encodeURIComponent(branchId)}`;
      ws = new WebSocket(url);
      ws.onopen = () => {
        attempt = 0;
        setConnected(true);
        refetch();
      };
      ws.onmessage = (event) => {
        try {
          applyEvent(JSON.parse(String(event.data)) as KitchenEvent);
        } catch {
          // Ignore malformed frames; the reconnect logic below handles failures.
        }
      };
      ws.onclose = () => scheduleRetry();
      ws.onerror = () => {
        try {
          ws?.close();
        } catch {
          // no-op
        }
      };
    };

    connect();

    return () => {
      mounted = false;
      if (retryTimer) clearTimeout(retryTimer);
      try {
        ws?.close();
      } catch {
        // no-op
      }
    };
  }, [branchId]);

  // -------------------------------------------------------------------------
  // Actions
  // -------------------------------------------------------------------------
  const advance = async (ticket: KitchenTicketOut) => {
    setBusyId(ticket.id);
    try {
      if (ticket.status === "READY") {
        // SERVED is a terminal kitchen status; it flows through the order
        // engine (the ticket endpoint only accepts board moves).
        await ordersApi.updateKitchenStatus(ticket.order_id, "SERVED");
        setBoard((prev) =>
          prev.type === "data"
            ? dataState(prev.data.filter((x) => x.id !== ticket.id))
            : prev
        );
      } else {
        const next: KitchenTicketStatus =
          ticket.status === "NEW" ? "PREPARING" : "READY";
        const updated = await kitchenApi.updateTicketStatus(ticket.id, next);
        setBoard((prev) => {
          if (prev.type !== "data") return prev;
          const rest = prev.data.filter((x) => x.id !== updated.id);
          const list = [...rest, updated];
          list.sort(
            (a, b) =>
              new Date(a.created_at).getTime() -
              new Date(b.created_at).getTime()
          );
          return dataState(list);
        });
      }
      flash(t("ticketMoved"));
    } catch (err) {
      alert((err as Error).message);
    } finally {
      setBusyId(null);
    }
  };

  const actionFor = (ticket: KitchenTicketOut) => {
    if (!canUpdateOrders) return null;
    if (ticket.status === "NEW") {
      return { label: t("markPreparing"), to: "PREPARING" as const };
    }
    if (ticket.status === "PREPARING") {
      return { label: t("markReady"), to: "READY" as const };
    }
    return { label: t("markServed"), to: "SERVED" as const };
  };

  return (
    <div>
      <PageHeader
        title={t("title")}
        description={`${t("branch")}: ${branches.find((b) => b.id === branchId)?.name ?? "—"}`}
      />

      {notice && (
        <div className="mb-4 rounded-lg border border-success/30 bg-success/10 px-4 py-2 text-sm text-success">
          {notice}
        </div>
      )}

      <div className="mb-5 flex flex-wrap items-center gap-3">
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
        <span
          className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-semibold ${
            connected
              ? "bg-success/10 text-success"
              : "bg-warning/10 text-warning"
          }`}
        >
          <span
            className={`h-1.5 w-1.5 rounded-full ${connected ? "bg-success" : "bg-warning"}`}
          />
          {connected ? t("live") : t("reconnecting")}
        </span>
        {!connected && (
          <span className="flex items-center gap-1 text-xs text-text-secondary">
            <AlertTriangle className="h-3.5 w-3.5" />
            {t("reconnecting")}
          </span>
        )}
      </div>

      {board.type === "error" ? (
        <div className="rounded-xl border border-border-default bg-surface">
          <StateView
            kind="error"
            message={board.message}
            onRetry={() => void loadBoard()}
          />
        </div>
      ) : board.type === "loading" ? (
        <div className="rounded-xl border border-border-default bg-surface">
          <StateView kind="loading" />
        </div>
      ) : board.type === "data" ? (
        board.data.length === 0 ? (
          <div className="rounded-xl border border-border-default bg-surface">
            <StateView kind="empty" message={t("noTickets")} />
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          {COLUMNS.map((column) => {
            const tickets = board.data.filter(
              (tk) => tk.status === column.key
            );
            return (
              <section
                key={column.key}
                className="rounded-xl border border-border-default bg-surface"
              >
                <div className="flex items-center gap-2 border-b border-border-default px-4 py-3">
                  <span className={`h-2 w-2 rounded-full ${column.dot}`} />
                  <h2 className="text-sm font-semibold text-text-primary">
                    {t(column.labelKey)}
                  </h2>
                  <span className="ml-auto rounded-full bg-background-secondary px-2 py-0.5 text-xs font-medium text-text-secondary">
                    {tickets.length}
                  </span>
                </div>
                <ul className="space-y-3 p-3">
                  {tickets.length === 0 && (
                    <li className="py-8 text-center text-sm text-text-secondary">
                      {t("noTickets")}
                    </li>
                  )}
                  {tickets.map((ticket) => (
                    <li
                      key={ticket.id}
                      className="rounded-lg border border-border-default bg-background p-3"
                    >
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-text-primary">
                          #{ticket.order_number}
                        </span>
                        {ticket.table_name && (
                          <span className="ml-auto rounded-md bg-accent-primary/10 px-2 py-0.5 text-xs font-medium text-accent-primary">
                            {t("table")} {ticket.table_name}
                          </span>
                        )}
                      </div>

                      {ticket.status === "NEW" && (
                        <p className="mt-1.5 flex items-center gap-1 text-xs text-text-secondary">
                          <Clock className="h-3.5 w-3.5" />
                          {now > 0 ? (
                            minutesBetween(now, ticket.created_at) < 1 ? (
                              t("justNow")
                            ) : (
                              t("minutes", {
                                m: minutesBetween(now, ticket.created_at),
                              })
                            )
                          ) : (
                            formatDateTime(ticket.created_at)
                          )}
                        </p>
                      )}

                      <ul className="mt-2 space-y-1.5">
                        {ticket.items.map((item, index) => (
                          <li key={index} className="text-sm">
                            <div className="flex gap-2">
                              <span className="text-text-secondary">
                                {item.quantity}×
                              </span>
                              <span className="font-medium text-text-primary">
                                {item.product_name_snapshot}
                              </span>
                            </div>
                            {item.modifiers.length > 0 && (
                              <div className="mt-0.5 pl-6 text-xs text-text-secondary">
                                {item.modifiers
                                  .map(
                                    (m) =>
                                      `${m.modifier_name_snapshot}${m.quantity > 1 ? ` ×${m.quantity}` : ""}`
                                  )
                                  .join(", ")}
                              </div>
                            )}
                            {item.notes && (
                              <div className="mt-0.5 pl-6 text-xs italic text-text-secondary">
                                {item.notes}
                              </div>
                            )}
                          </li>
                        ))}
                      </ul>

                      {ticket.notes && (
                        <p className="mt-2 rounded-md bg-warning/10 px-2 py-1.5 text-xs text-warning">
                          {ticket.notes}
                        </p>
                      )}

                      {actionFor(ticket) && (
                        <button
                          type="button"
                          disabled={busyId === ticket.id}
                          onClick={() => advance(ticket)}
                          className="mt-3 flex w-full items-center justify-center gap-2 rounded-lg bg-accent-primary px-3 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
                        >
                          <ChefHat className="h-4 w-4" />
                          {busyId === ticket.id ? "…" : actionFor(ticket)!.label}
                        </button>
                      )}
                    </li>
                  ))}
                </ul>
              </section>
            );
          })}
        </div>
        )
      ) : null}
    </div>
  );
}