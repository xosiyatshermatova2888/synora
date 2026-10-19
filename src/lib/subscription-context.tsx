"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { PAYMENT_REQUIRED_EVENT, SubscriptionOut, subscriptionApi } from "./api";
import { useAuth } from "./auth-context";

interface SubscriptionContextValue {
  /** null until the first load finishes (or if it failed). */
  subscription: SubscriptionOut | null;
  /** True once the first load has settled (even if it failed). Gated pages wait
   * for this so a Business restaurant never fires a doomed request first. */
  loaded: boolean;
  /** Does the current plan include `feature`? Optimistic (true) while loading
   * so pages don't flash a paywall — the server enforces it either way. */
  has: (feature: string) => boolean;
  /** False once the subscription is read-only (past the grace period). */
  canWrite: boolean;
  refresh: () => Promise<void>;
}

const SubscriptionContext = createContext<SubscriptionContextValue | undefined>(undefined);

export function SubscriptionProvider({ children }: { children: React.ReactNode }) {
  const { status } = useAuth();
  const [subscription, setSubscription] = useState<SubscriptionOut | null>(null);
  const [loaded, setLoaded] = useState(false);

  const refresh = useCallback(async () => {
    try {
      setSubscription(await subscriptionApi.get());
    } catch {
      // Leave the previous state: a failed refresh must not lock the UI.
    } finally {
      setLoaded(true);
    }
  }, []);

  useEffect(() => {
    if (status === "authenticated") void refresh();
  }, [status, refresh]);

  // Any 402 means the server's idea of the plan differs from ours — resync.
  useEffect(() => {
    const onPaymentRequired = () => void refresh();
    window.addEventListener(PAYMENT_REQUIRED_EVENT, onPaymentRequired);
    return () => window.removeEventListener(PAYMENT_REQUIRED_EVENT, onPaymentRequired);
  }, [refresh]);

  const value = useMemo<SubscriptionContextValue>(
    () => ({
      subscription,
      loaded,
      has: (feature) => (subscription ? subscription.features.includes(feature) : true),
      canWrite: subscription ? subscription.can_write : true,
      refresh,
    }),
    [subscription, loaded, refresh]
  );

  return <SubscriptionContext.Provider value={value}>{children}</SubscriptionContext.Provider>;
}

export function useSubscription(): SubscriptionContextValue {
  const ctx = useContext(SubscriptionContext);
  if (!ctx) throw new Error("useSubscription must be used within SubscriptionProvider");
  return ctx;
}
