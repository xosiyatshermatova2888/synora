"use client";

import { useEffect, useRef } from "react";
import { useTenantWebSocket } from "@/lib/use-tenant-websocket";

/**
 * Re-run `reload` whenever the server says orders changed (a waiter, Telegram or
 * QR order arrived, an order was paid/cancelled, the kitchen moved it...), so
 * lists update by themselves without pressing refresh.
 *
 * The server sends `order_changed` (every order change) and `notification`
 * (payments, bill requests) over the same tenant WebSocket the bell uses.
 * Bursts are coalesced into one reload, and a reload also runs after the socket
 * (re)connects, to catch whatever happened while it was down.
 */
export function useLiveReload(reload: () => void): void {
  const reloadRef = useRef(reload);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    reloadRef.current = reload;
  });

  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current);
    },
    []
  );

  const schedule = () => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => reloadRef.current(), 300);
  };

  useTenantWebSocket<{ event?: string }>(
    "/ws/notifications",
    null,
    (msg) => {
      if (msg.event === "order_changed" || msg.event === "notification") schedule();
    },
    schedule
  );
}
