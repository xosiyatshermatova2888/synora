"use client";

import { useEffect } from "react";
import { Loader2 } from "lucide-react";
import { usePathname, useRouter } from "@/i18n/routing";
import { useAuth } from "@/lib/auth-context";
import { BranchProvider } from "@/lib/branch-context";
import { SubscriptionProvider } from "@/lib/subscription-context";
import DashboardShell from "@/components/dashboard/DashboardShell";
import { applyDashboardTheme, clearDashboardTheme, readDashboardTheme } from "@/lib/dashboard-theme";

export default function DashboardGuard({
  children,
}: {
  children: React.ReactNode;
}) {
  const { status } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    if (status === "unauthenticated") {
      router.replace(
        pathname !== "/dashboard"
          ? { pathname: "/login", query: { next: pathname } }
          : "/login"
      );
    }
  }, [status, pathname, router]);

  useEffect(() => {
    applyDashboardTheme(readDashboardTheme());
    return () => clearDashboardTheme();
  }, []);

  // One-time self-heal: a root-scoped waiter-sw.js registration (a past bug —
  // it registered without a `scope`, so it defaulted to controlling the
  // whole origin) would intercept dashboard navigations too. No dashboard
  // service worker is meant to exist, so any root-scoped registration found
  // here is that stray one; remove it.
  useEffect(() => {
    if (!("serviceWorker" in navigator)) return;
    navigator.serviceWorker.getRegistrations().then((regs) => {
      for (const reg of regs) {
        if (reg.scope === `${window.location.origin}/`) {
          reg.unregister().catch(() => {});
        }
      }
    });
  }, []);

  if (status === "loading" || status === "unauthenticated") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <Loader2 className="h-8 w-8 animate-spin text-accent-primary" />
      </div>
    );
  }

  return (
    <BranchProvider>
      <SubscriptionProvider>
        <DashboardShell>{children}</DashboardShell>
      </SubscriptionProvider>
    </BranchProvider>
  );
}