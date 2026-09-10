"use client";

import { useEffect } from "react";
import { Loader2 } from "lucide-react";
import { usePathname, useRouter } from "@/i18n/routing";
import { useAuth } from "@/lib/auth-context";
import DashboardShell from "@/components/dashboard/DashboardShell";

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

  if (status === "loading" || status === "unauthenticated") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <Loader2 className="h-8 w-8 animate-spin text-accent-primary" />
      </div>
    );
  }

  return <DashboardShell>{children}</DashboardShell>;
}