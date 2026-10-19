"use client";

import { useEffect } from "react";
import { Loader2 } from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import WaiterPinLogin from "@/components/WaiterPinLogin";

/**
 * Auth gate for /waiter only — unlike AuthGuard (which redirects to the
 * admin email/password /login page), an unauthenticated waiter kiosk shows
 * the name+PIN login screen in place, since it has no email/password of its
 * own to type.
 */
export default function WaiterAuthGate({ children }: { children: React.ReactNode }) {
  const { status } = useAuth();

  useEffect(() => {
    if ("serviceWorker" in navigator) {
      // Without an explicit scope, a worker served from the site root
      // defaults to controlling the ENTIRE origin — including /dashboard —
      // not just /waiter. Pin it down so it only ever intercepts the
      // waiter kiosk's own pages.
      navigator.serviceWorker.register("/waiter-sw.js", { scope: "/waiter/" }).catch(() => {});
    }
  }, []);

  if (status === "loading") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <Loader2 className="h-8 w-8 animate-spin text-accent-primary" />
      </div>
    );
  }

  if (status === "unauthenticated") {
    return <WaiterPinLogin />;
  }

  return <>{children}</>;
}
