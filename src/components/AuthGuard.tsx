"use client";

import { useEffect } from "react";
import { Loader2 } from "lucide-react";
import { usePathname, useRouter } from "@/i18n/routing";
import { useAuth } from "@/lib/auth-context";

/**
 * Auth gate for standalone (non-dashboard-shell) routes — /waiter, /receipt.
 * Same redirect-to-login logic as DashboardGuard, but renders children
 * directly with no sidebar/header: these are distraction-free, single-purpose
 * screens, not corners of the admin panel.
 */
export default function AuthGuard({ children }: { children: React.ReactNode }) {
  const { status } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    if (status === "unauthenticated") {
      router.replace({ pathname: "/login", query: { next: pathname } });
    }
  }, [status, pathname, router]);

  if (status === "loading" || status === "unauthenticated") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <Loader2 className="h-8 w-8 animate-spin text-accent-primary" />
      </div>
    );
  }

  return <>{children}</>;
}
