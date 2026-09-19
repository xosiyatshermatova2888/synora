"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { WifiOff, Loader2 } from "lucide-react";
import {
  isOnline,
  startConnectivityMonitor,
  subscribeConnectivity,
} from "@/lib/offline/connectivity";
import { subscribeQueue, drainQueue } from "@/lib/offline/queue";

/**
 * Fixed top banner for the waiter app: shows "no connection" while offline,
 * and a "N kutilmoqda" badge while orders taken offline are still queued
 * (even briefly after reconnecting, until drainQueue finishes). Renders
 * nothing when online with an empty queue — the common case.
 */
export default function OfflineBanner() {
  const t = useTranslations("waiterPage");
  const [online, setOnline] = useState(true);
  const [pendingCount, setPendingCount] = useState(0);

  useEffect(() => {
    startConnectivityMonitor();
    setOnline(isOnline());

    const unsubConnectivity = subscribeConnectivity((next) => {
      setOnline(next);
      if (next) void drainQueue();
    });
    const unsubQueue = subscribeQueue((pending) => setPendingCount(pending.length));

    return () => {
      unsubConnectivity();
      unsubQueue();
    };
  }, []);

  if (online && pendingCount === 0) return null;

  return (
    <div
      role="status"
      className={`flex items-center justify-center gap-2 px-4 py-2 text-center text-sm font-medium text-white ${
        online ? "bg-warning" : "bg-error"
      }`}
    >
      {online ? (
        <>
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
          {t("syncingPending", { count: pendingCount })}
        </>
      ) : (
        <>
          <WifiOff className="h-4 w-4" aria-hidden="true" />
          {t("offline")}
          {pendingCount > 0 && ` · ${t("pendingCount", { count: pendingCount })}`}
        </>
      )}
    </div>
  );
}
