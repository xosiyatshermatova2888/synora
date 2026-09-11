"use client";

import { useEffect } from "react";
import { Loader2 } from "lucide-react";
import { usePathname, useRouter } from "@/i18n/routing";
import { useAuth } from "@/lib/auth-context";

/**
 * Auth gate for /waiter — same redirect logic as DashboardGuard, but
 * deliberately does NOT render DashboardShell: the waiter flow is a
 * distraction-free, full-screen screen with its own minimal header, not
 * the full dashboard with its sidebar and other modules.
 */
export default function WaiterGuard({
  children,
}: {
  children: React.ReactNode;
}) {
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
