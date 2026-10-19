"use client";

import { useEffect, useRef, useState } from "react";
import { authApi, getAccessToken } from "@/lib/api";

/**
 * Connect/exponential-backoff-reconnect/silent-token-refresh-before-retry —
 * the WebSocket pattern proven in `dashboard/kitchen/page.tsx`'s own
 * `useEffect`, extracted so other tenant-scoped sockets (e.g. the
 * notification bell) don't duplicate it. The kitchen page itself is left
 * untouched and keeps its inline version.
 *
 * `branchId: null` subscribes to every branch for the tenant (the manager's
 * "all branches" bucket — see `app/websocket/manager.py::_targets`).
 */
export function useTenantWebSocket<T>(
  path: string,
  branchId: string | null,
  onEvent: (msg: T) => void,
  onOpen?: () => void
): { connected: boolean } {
  const [connected, setConnected] = useState(false);
  const onEventRef = useRef(onEvent);
  const onOpenRef = useRef(onOpen);
  useEffect(() => {
    onEventRef.current = onEvent;
    onOpenRef.current = onOpen;
  });

  useEffect(() => {
    let mounted = true;
    let attempt = 0;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;
    let ws: WebSocket | null = null;

    const scheduleRetry = () => {
      if (!mounted) return;
      setConnected(false);
      const delay = Math.min(30000, 1000 * 2 ** attempt);
      attempt += 1;
      retryTimer = setTimeout(() => {
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
      const branchQs = branchId ? `&branch_id=${encodeURIComponent(branchId)}` : "";
      const url = `${proto}//${window.location.host}/api/v1${path}?token=${encodeURIComponent(token)}${branchQs}`;
      ws = new WebSocket(url);
      ws.onopen = () => {
        attempt = 0;
        setConnected(true);
        onOpenRef.current?.();
      };
      ws.onmessage = (event) => {
        try {
          onEventRef.current(JSON.parse(String(event.data)) as T);
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
  }, [path, branchId]);

  return { connected };
}
