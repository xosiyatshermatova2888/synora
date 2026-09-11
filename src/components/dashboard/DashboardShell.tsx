"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { motion, AnimatePresence } from "framer-motion";
import {
  Menu,
  X,
  LayoutDashboard,
  UtensilsCrossed,
  Table2,
  ShoppingCart,
  ChefHat,
  CreditCard,
  LogOut,
  ChevronRight,
} from "lucide-react";
import { Link, usePathname } from "@/i18n/routing";
import { useAuth } from "@/lib/auth-context";

interface SidebarItem {
  href:
    | "/dashboard"
    | "/dashboard/menu"
    | "/dashboard/tables"
    | "/dashboard/orders"
    | "/dashboard/kitchen"
    | "/dashboard/payments";
  icon: React.ComponentType<{ className?: string }>;
  labelKey: "overview" | "menu" | "tables" | "orders" | "kitchen" | "payments";
  permission?: string;
}

const SIDEBAR_ITEMS: SidebarItem[] = [
  { href: "/dashboard", icon: LayoutDashboard, labelKey: "overview" },
  {
    href: "/dashboard/menu",
    icon: UtensilsCrossed,
    labelKey: "menu",
    permission: "menu.read",
  },
  {
    href: "/dashboard/tables",
    icon: Table2,
    labelKey: "tables",
    permission: "orders.read",
  },
  {
    href: "/dashboard/orders",
    icon: ShoppingCart,
    labelKey: "orders",
    permission: "orders.read",
  },
  {
    href: "/dashboard/kitchen",
    icon: ChefHat,
    labelKey: "kitchen",
    permission: "orders.read",
  },
  {
    href: "/dashboard/payments",
    icon: CreditCard,
    labelKey: "payments",
    permission: "finance.read",
  },
];

function SidebarContent({
  items,
  currentPath,
  onNavigate,
}: {
  items: SidebarItem[];
  currentPath: string;
  onNavigate: () => void;
}) {
  const t = useTranslations("shell");
  return (
    <nav className="flex flex-col gap-1 p-4">
      {items.map((item) => {
        const Icon = item.icon;
        const active =
          item.href === "/dashboard"
            ? currentPath === "/dashboard"
            : currentPath.startsWith(item.href);
        return (
          <Link
            key={item.href}
            href={item.href}
            onClick={onNavigate}
            className={`relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
              active
                ? "bg-accent-primary/10 text-accent-primary"
                : "text-text-secondary hover:bg-background-secondary hover:text-text-primary"
            }`}
          >
            {active && (
              <span className="absolute -left-4 top-1/2 h-5 w-1 -translate-y-1/2 rounded-r-full bg-brand-gradient" />
            )}
            <Icon className="h-5 w-5 shrink-0" />
            <span>{t(`nav.${item.labelKey}`)}</span>
          </Link>
        );
      })}
    </nav>
  );
}

export default function DashboardShell({
  children,
}: {
  children: React.ReactNode;
}) {
  const t = useTranslations("shell");
  const pathname = usePathname();
  const { user, logout, can } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);

  const filtered = SIDEBAR_ITEMS.filter(
    (item) => !item.permission || can(item.permission)
  );

  const isActive = (href: string) => {
    if (href === "/dashboard") return pathname === "/dashboard";
    return pathname.startsWith(href);
  };

  const activeItem = filtered.find((item) => isActive(item.href));

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      {/* Desktop sidebar */}
      <aside className="hidden h-screen lg:flex lg:w-64 lg:shrink-0 lg:flex-col lg:border-r lg:border-border-default">
        <Link href="/dashboard" className="flex h-16 items-center gap-2 px-6">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-gradient text-sm font-bold text-white shadow-sm">
            S
          </div>
          <span className="text-lg font-bold text-text-primary">SYNORA</span>
        </Link>
        <SidebarContent
          items={filtered}
          currentPath={pathname}
          onNavigate={() => setMobileOpen(false)}
        />
        <div className="mt-auto p-4">
          <button
            onClick={() => logout()}
            className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-text-secondary hover:bg-background-secondary hover:text-text-primary"
          >
            <LogOut className="h-5 w-5" />
            <span>{t("nav.logout")}</span>
          </button>
        </div>
      </aside>

      {/* Mobile drawer */}
      <AnimatePresence>
        {mobileOpen && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 z-40 bg-black/40 lg:hidden"
              onClick={() => setMobileOpen(false)}
            />
            <motion.aside
              initial={{ x: -280 }}
              animate={{ x: 0 }}
              exit={{ x: -280 }}
              transition={{ type: "spring", damping: 25, stiffness: 300 }}
              className="fixed inset-y-0 left-0 z-50 w-64 border-r border-border-default bg-background lg:hidden"
            >
              <div className="flex h-16 items-center justify-between px-6">
                <Link href="/dashboard" onClick={() => setMobileOpen(false)}>
                  <div className="flex items-center gap-2">
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-gradient text-sm font-bold text-white shadow-sm">
                      S
                    </div>
                    <span className="text-lg font-bold text-text-primary">
                      SYNORA
                    </span>
                  </div>
                </Link>
                <button
                  onClick={() => setMobileOpen(false)}
                  aria-label={t("nav.close")}
                  className="text-text-secondary"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>
              <SidebarContent
                items={filtered}
                currentPath={pathname}
                onNavigate={() => setMobileOpen(false)}
              />
              <div className="absolute bottom-0 left-0 right-0 p-4">
                <button
                  onClick={() => {
                    logout();
                    setMobileOpen(false);
                  }}
                  className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-text-secondary hover:bg-background-secondary hover:text-text-primary"
                >
                  <LogOut className="h-5 w-5" />
                  <span>{t("nav.logout")}</span>
                </button>
              </div>
            </motion.aside>
          </>
        )}
      </AnimatePresence>

      {/* Main area */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-16 shrink-0 items-center gap-4 border-b border-border-default bg-surface/80 px-4 backdrop-blur-sm lg:px-6">
          <button
            onClick={() => setMobileOpen(true)}
            aria-label={t("nav.open")}
            className="text-text-secondary lg:hidden"
          >
            <Menu className="h-5 w-5" />
          </button>
          <div className="flex min-w-0 flex-1 items-center gap-2 text-sm text-text-secondary">
            <Link
              href="/dashboard"
              className="hover:text-text-primary"
            >
              {t("breadcrumb.home")}
            </Link>
            {activeItem && activeItem.href !== "/dashboard" && (
              <>
                <ChevronRight className="h-3.5 w-3.5 shrink-0" />
                <span className="truncate text-text-primary">
                  {t(`nav.${activeItem.labelKey}`)}
                </span>
              </>
            )}
          </div>
          <div className="flex flex-shrink-0 items-center gap-3">
            <span className="hidden text-sm font-medium text-text-primary sm:block">
              {user?.full_name}
            </span>
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-brand-gradient text-xs font-bold text-white shadow-sm">
              {user?.full_name?.charAt(0)?.toUpperCase()}
            </div>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto p-4 lg:p-6">{children}</main>
      </div>
    </div>
  );
}