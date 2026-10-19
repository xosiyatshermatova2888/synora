"use client";

import { useCallback, useEffect, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { ChefHat, AlertTriangle, Clock, Printer, Flame } from "lucide-react";
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
  printJobsApi,
  printersApi,
} from "@/lib/api";
import type { LoadState } from "@/lib/load-state";
import { loadingState, errorState, dataState } from "@/lib/load-state";
import { formatDateTime } from "@/lib/format";
import { useAuth } from "@/lib/auth-context";

const ACTIVE_STATUSES: KitchenTicketStatus[] = ["NEW", "PREPARING", "READY"];

const COLUMNS: {
  key: KitchenTicketStatus;
  labelKey: string;
  dot: string;
  border: string;
  headerBg: string;
}[] = [
  {
    key: "NEW",
    labelKey: "columnNew",
    dot: "bg-accent-primary",
    border: "border-l-accent-primary",
    headerBg: "bg-accent-primary/[0.04]",
  },
  {
    key: "PREPARING",
    labelKey: "columnPreparing",
    dot: "bg-warning",
    border: "border-l-warning",
    headerBg: "bg-warning/[0.04]",
  },
  {
    key: "READY",
    labelKey: "columnReady",
    dot: "bg-success",
    border: "border-l-success",
    headerBg: "bg-success/[0.04]",
  },
];

function minutesBetween(from: number, iso: string): number {
  return Math.max(0, Math.floor((from - new Date(iso).getTime()) / 60000));
}

export default function KitchenPage() {
  const t = useTranslations("kitchenPage");
  const tsrc = useTranslations("ordersPage");
  const locale = useLocale();
  const { can } = useAuth();

  const [branches, setBranches] = useState<BranchOut[]>([]);
  const [branchId, setBranchId] = useState<string | null>(null);
  const [board, setBoard] = useState<LoadState<KitchenTicketOut[]>>(loadingState());
  const [connected, setConnected] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [now, setNow] = useState(0);
  const [notice, setNotice] = useState<string | null>(null);

  const canUpdateOrders = can("orders.update");
  const canManage = can("users.manage");

  // Kitchen printer: when one exists the print button reprints on it, otherwise
  // it falls back to the browser print page.
  const [hasKitchenPrinter, setHasKitchenPrinter] = useState(false);
  const [printFailed, setPrintFailed] = useState(false);

  useEffect(() => {
    if (!branchId) return;
    printersApi
      .capabilities(branchId)
      .then((c) => setHasKitchenPrinter(c.kitchen))
      .catch(() => setHasKitchenPrinter(false));
  }, [branchId]);

  useEffect(() => {
    if (!canManage || !hasKitchenPrinter) return;
    const check = () =>
      printJobsApi
        .list(5)
        .then((jobs) => setPrintFailed(jobs.some((j) => j.kind === "KITCHEN_TICKET" && j.status === "FAILED")))
        .catch(() => {});
    void check();
    const id = setInterval(check, 30000);
    return () => clearInterval(id);
  }, [canManage, hasKitchenPrinter]);

  const printTicket = async (ticket: KitchenTicketOut) => {
    if (!hasKitchenPrinter) {
      window.open(`/${locale}/kitchen-ticket?order=${ticket.order_id}`, "_blank", "noopener,noreferrer");
      return;
    }
    try {
      const job = await ordersApi.reprintKitchen(ticket.order_id);
      flash(job.status === "PRINTED" ? t("printed") : `${t("printFailed")}: ${job.error ?? ""}`);
    } catch (err) {
      alert((err as Error).message);
    }
  };

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
    setNow(Date.now());
    const id = setInterval(() => setNow(Date.now()), 5000);
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
        // One tap: a new ticket goes straight to READY (the "start preparing"
        // step is skipped; the ticket printing is the kitchen's signal).
        const next: KitchenTicketStatus = "READY";
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
    if (ticket.status === "NEW" || ticket.status === "PREPARING") {
      return { label: t("markReady"), to: "READY" as const };
    }
    return { label: t("markServed"), to: "SERVED" as const };
  };

  const OVERDUE_MIN = 15;
  const WARN_MIN = 8;
  const activeCount = board.type === "data" ? board.data.length : 0;
  const overdueCount =
    board.type === "data" && now > 0
      ? board.data.filter(
          (tk) => tk.status !== "READY" && minutesBetween(now, tk.created_at) >= OVERDUE_MIN
        ).length
      : 0;

  return (
    <div className="-m-4 min-h-[calc(100vh-4rem)] bg-[#08181a] p-4 text-white lg:-m-6 lg:p-6">
      {/* KDS header */}
      <div className="mb-5 flex flex-wrap items-center gap-x-6 gap-y-3">
        <div>
          <h1 className="flex items-center gap-2.5 text-2xl font-semibold tracking-tight">
            <ChefHat className="h-7 w-7 text-accent-primary" />
            {t("title")}
          </h1>
          <p className="mt-0.5 text-sm text-slate-400">
            {t("branch")}: {branches.find((b) => b.id === branchId)?.name ?? "—"}
          </p>
        </div>

        <div className="ml-auto flex flex-wrap items-center gap-3">
          <span className="rounded-lg bg-white/5 px-3 py-1.5 text-sm text-slate-300">
            {t("activeTickets", { n: activeCount })}
          </span>
          {overdueCount > 0 && (
            <span className="inline-flex items-center gap-1.5 rounded-lg bg-red-500/15 px-3 py-1.5 text-sm font-semibold text-red-300">
              <Flame className="h-4 w-4" />
              {t("overdueCount", { n: overdueCount })}
            </span>
          )}
          {printFailed && (
            <span className="inline-flex items-center gap-1.5 rounded-lg bg-red-500/15 px-3 py-1.5 text-sm font-semibold text-red-300">
              <Printer className="h-4 w-4" />
              {t("printerError")}
            </span>
          )}
          <select
            value={branchId ?? ""}
            onChange={(e) => setBranchId(e.target.value || null)}
            aria-label={t("branch")}
            className="h-9 rounded-lg border border-white/10 bg-[#0f272b] px-3 text-sm text-white outline-none focus:border-accent-primary"
          >
            {branches.length === 0 && <option value="">—</option>}
            {branches.map((b) => (
              <option key={b.id} value={b.id}>
                {b.name}
              </option>
            ))}
          </select>
          <span
            className={`inline-flex items-center gap-2 rounded-full px-3 py-1.5 text-xs font-semibold ${
              connected ? "bg-emerald-500/15 text-emerald-300" : "bg-amber-500/15 text-amber-300"
            }`}
          >
            <span className={`h-2 w-2 rounded-full ${connected ? "bg-emerald-400" : "bg-amber-400"}`} />
            {connected ? t("live") : t("reconnecting")}
          </span>
        </div>
      </div>

      {notice && (
        <div className="mb-4 rounded-lg border border-emerald-400/30 bg-emerald-500/10 px-4 py-2 text-sm text-emerald-300">
          {notice}
        </div>
      )}

      {board.type === "error" ? (
        <div className="rounded-xl border border-white/10 bg-[#0f272b] py-16 text-center">
          <AlertTriangle className="mx-auto h-8 w-8 text-red-400" />
          <p className="mt-3 text-sm text-slate-300">{board.message}</p>
          <button
            onClick={() => void loadBoard()}
            className="mt-4 h-9 rounded-lg border border-white/15 px-4 text-sm text-white hover:bg-white/5"
          >
            {t("retry")}
          </button>
        </div>
      ) : board.type === "loading" ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-64 animate-pulse rounded-xl bg-white/5" />
          ))}
        </div>
      ) : board.type === "data" ? (
        board.data.length === 0 ? (
          <div className="flex flex-col items-center rounded-xl border border-dashed border-white/10 py-24 text-center">
            <ChefHat className="h-10 w-10 text-slate-600" />
            <p className="mt-3 max-w-sm text-base text-slate-400">{t("noTickets")}</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            {COLUMNS.map((column) => {
              const tickets = board.data.filter((tk) => tk.status === column.key);
              return (
                <section key={column.key} className="rounded-xl bg-[#0c2024] ring-1 ring-white/5">
                  <div className="flex items-center gap-2.5 border-b border-white/5 px-4 py-3">
                    <span className={`h-2.5 w-2.5 rounded-full ${column.dot}`} />
                    <h2 className="text-base font-semibold uppercase tracking-wide text-slate-200">
                      {t(column.labelKey)}
                    </h2>
                    <span className="tabular ml-auto rounded-full bg-white/10 px-2.5 py-0.5 text-sm font-semibold text-white">
                      {tickets.length}
                    </span>
                  </div>
                  <ul className="space-y-3 p-3">
                    {tickets.length === 0 && (
                      <li className="py-10 text-center text-sm text-slate-500">{t("noTickets")}</li>
                    )}
                    {tickets.map((ticket) => {
                      const mins = now > 0 ? minutesBetween(now, ticket.created_at) : 0;
                      const overdue = ticket.status !== "READY" && mins >= OVERDUE_MIN;
                      const warn = ticket.status !== "READY" && !overdue && mins >= WARN_MIN;
                      return (
                        <li
                          key={ticket.id}
                          className={`rounded-xl border-l-4 bg-[#12303a] p-4 ${
                            overdue ? "border-l-red-500 ring-1 ring-red-500/40" : warn ? "border-l-amber-400" : column.border
                          }`}
                        >
                          <div className="flex items-start gap-3">
                            <div>
                              <p className="tabular text-2xl font-bold leading-none">#{ticket.order_number}</p>
                              <p className="mt-1 text-xs uppercase tracking-wide text-slate-400">
                                {tsrc(`sources.${ticket.source}` as "sources.POS")}
                              </p>
                            </div>
                            {ticket.table_name && (
                              <span className="ml-auto rounded-lg bg-white/10 px-3 py-1.5 text-lg font-semibold">
                                {ticket.table_name}
                              </span>
                            )}
                          </div>

                          <p
                            className={`tabular mt-3 flex items-center gap-1.5 text-sm font-semibold ${
                              overdue ? "animate-pulse text-red-300" : warn ? "text-amber-300" : "text-slate-400"
                            }`}
                          >
                            <Clock className="h-4 w-4" />
                            {now > 0
                              ? mins < 1
                                ? t("justNow")
                                : t("minutes", { m: mins })
                              : formatDateTime(ticket.created_at)}
                            {overdue && <span className="ml-1 uppercase">· {t("overdue")}</span>}
                          </p>

                          <ul className="mt-3 space-y-2">
                            {ticket.items.map((item, index) => (
                              <li key={index}>
                                <div className="flex gap-2.5 text-lg leading-snug">
                                  <span className="tabular min-w-[1.75rem] font-bold text-accent-primary">
                                    {item.quantity}×
                                  </span>
                                  <span className="font-medium">{item.product_name_snapshot}</span>
                                </div>
                                {item.modifiers.length > 0 && (
                                  <p className="pl-10 text-sm text-slate-300">
                                    {item.modifiers
                                      .map(
                                        (m) =>
                                          `+ ${m.modifier_name_snapshot}${m.quantity > 1 ? ` ×${m.quantity}` : ""}`
                                      )
                                      .join(", ")}
                                  </p>
                                )}
                                {item.notes && (
                                  <p className="pl-10 text-sm italic text-amber-300">{item.notes}</p>
                                )}
                              </li>
                            ))}
                          </ul>

                          {ticket.notes && (
                            <p className="mt-3 rounded-lg bg-amber-400/15 px-3 py-2 text-sm font-medium text-amber-200">
                              {ticket.notes}
                            </p>
                          )}

                          <div className="mt-4 flex items-center gap-2">
                            {actionFor(ticket) && (
                              <button
                                type="button"
                                disabled={busyId === ticket.id}
                                onClick={() => advance(ticket)}
                                className="flex h-12 flex-1 items-center justify-center gap-2 rounded-lg bg-accent-primary text-base font-semibold text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
                              >
                                <ChefHat className="h-5 w-5" />
                                {busyId === ticket.id ? "…" : actionFor(ticket)!.label}
                              </button>
                            )}
                            <button
                              type="button"
                              title={t("printTicket")}
                              aria-label={t("printTicket")}
                              onClick={() => void printTicket(ticket)}
                              className="flex h-12 w-12 items-center justify-center rounded-lg border border-white/15 text-slate-300 hover:bg-white/5 hover:text-white"
                            >
                              <Printer className="h-5 w-5" />
                            </button>
                          </div>
                        </li>
                      );
                    })}
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
