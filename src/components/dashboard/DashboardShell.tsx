"use client";

import { useEffect, useState } from "react";
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
  ChevronsLeft,
  ChevronsRight,
  Users,
  Calculator,
  Building2,
  Boxes,
  Receipt,
  BarChart3,
  Contact,
  Settings,
  ClipboardList,
  Truck,
  Sparkles,
  Sun,
  Moon,
  Gem,
  Lock,
  ShieldCheck,
} from "lucide-react";
import { Link, usePathname } from "@/i18n/routing";
import { useAuth } from "@/lib/auth-context";
import { useBranch } from "@/lib/branch-context";
import { useSubscription } from "@/lib/subscription-context";
import SubscriptionBanner, { PaymentRequiredToast } from "@/components/dashboard/SubscriptionBanner";
import NotificationBell from "@/components/dashboard/NotificationBell";
import GlobalSearch from "@/components/dashboard/GlobalSearch";
import { ToastProvider } from "@/components/ui/Toast";
import { DashboardTheme, readDashboardTheme, saveDashboardTheme } from "@/lib/dashboard-theme";

type NavKey =
  | "overview"
  | "cashier"
  | "orders"
  | "tables"
  | "kitchen"
  | "menu"
  | "inventory"
  | "customers"
  | "staff"
  | "payments"
  | "expenses"
  | "reports"
  | "branches"
  | "auditLog"
  | "settings"
  | "delivery"
  | "ai"
  | "subscription"
  | "platform";

interface NavItem {
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  labelKey: NavKey;
  permission?: string;
  /** Plan feature this module needs; shows a lock when the plan lacks it. */
  feature?: string;
  /** Only for SYNORA platform admins. */
  platformAdmin?: boolean;
  /** Not built yet: rendered disabled with a "coming soon" tag, no route. */
  soon?: boolean;
}

interface NavGroup {
  groupKey: "operations" | "catalog" | "management" | "soon";
  items: NavItem[];
}

const NAV_GROUPS: NavGroup[] = [
  {
    groupKey: "operations",
    items: [
      { href: "/dashboard", icon: LayoutDashboard, labelKey: "overview" },
      { href: "/dashboard/cashier", icon: Calculator, labelKey: "cashier", permission: "orders.create" },
      { href: "/dashboard/orders", icon: ShoppingCart, labelKey: "orders", permission: "orders.read" },
      { href: "/dashboard/tables", icon: Table2, labelKey: "tables", permission: "orders.read" },
      { href: "/dashboard/kitchen", icon: ChefHat, labelKey: "kitchen", permission: "orders.read" },
    ],
  },
  {
    groupKey: "catalog",
    items: [
      { href: "/dashboard/menu", icon: UtensilsCrossed, labelKey: "menu", permission: "menu.read" },
      { href: "/dashboard/inventory", icon: Boxes, labelKey: "inventory", permission: "inventory.read", feature: "inventory" },
      { href: "/dashboard/customers", icon: Contact, labelKey: "customers", permission: "users.read", feature: "crm" },
    ],
  },
  {
    groupKey: "management",
    items: [
      { href: "/dashboard/staff", icon: Users, labelKey: "staff", permission: "users.read" },
      { href: "/dashboard/payments", icon: CreditCard, labelKey: "payments", permission: "finance.read" },
      { href: "/dashboard/expenses", icon: Receipt, labelKey: "expenses", permission: "finance.read" },
      { href: "/dashboard/reports", icon: BarChart3, labelKey: "reports", permission: "analytics.read" },
      { href: "/dashboard/branches", icon: Building2, labelKey: "branches", permission: "users.manage" },
      { href: "/dashboard/audit-log", icon: ClipboardList, labelKey: "auditLog", permission: "users.manage" },
      { href: "/dashboard/settings", icon: Settings, labelKey: "settings", permission: "users.manage" },
      { href: "/dashboard/subscription", icon: Gem, labelKey: "subscription", permission: "users.manage" },
      { href: "/dashboard/platform", icon: ShieldCheck, labelKey: "platform", platformAdmin: true },
    ],
  },
  {
    groupKey: "soon",
    items: [
      { href: "/dashboard/delivery", icon: Truck, labelKey: "delivery", permission: "orders.read", soon: true },
      { href: "/dashboard/ai", icon: Sparkles, labelKey: "ai", permission: "analytics.read", soon: true },
    ],
  },
];

const COLLAPSE_KEY = "synora.sidebarCollapsed";

function SidebarContent({
  groups,
  currentPath,
  collapsed,
  onNavigate,
}: {
  groups: NavGroup[];
  currentPath: string;
  collapsed: boolean;
  onNavigate: () => void;
}) {
  const t = useTranslations("shell");
  const tc = useTranslations("common.ui");
  const { has } = useSubscription();
  return (
    <nav className="flex flex-col gap-5 overflow-y-auto px-3 py-4" aria-label={t("nav.label")}>
      {groups.map((group) => (
        <div key={group.groupKey}>
          {!collapsed && (
            <p className="mb-1.5 px-3 text-[11px] font-semibold uppercase tracking-wider text-nav-text/60">
              {t(`navGroups.${group.groupKey}`)}
            </p>
          )}
          {collapsed && <div className="mx-3 mb-2 h-px bg-nav-border" />}
          <div className="flex flex-col gap-0.5">
            {group.items.map((item) => {
              const Icon = item.icon;
              const label = t(`nav.${item.labelKey}`);
              if (item.soon) {
                return (
                  <div
                    key={item.href}
                    title={collapsed ? `${label} — ${tc("comingSoon")}` : undefined}
                    aria-disabled="true"
                    className={`flex cursor-not-allowed items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-nav-text/45 ${collapsed ? "justify-center" : ""}`}
                  >
                    <Icon className="h-[18px] w-[18px] shrink-0" />
                    {!collapsed && (
                      <>
                        <span className="flex-1 truncate">{label}</span>
                        <span className="rounded bg-nav-surface px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-nav-text/70">
                          {tc("comingSoon")}
                        </span>
                      </>
                    )}
                  </div>
                );
              }
              const locked = !!item.feature && !has(item.feature);
              const active =
                item.href === "/dashboard"
                  ? currentPath === "/dashboard"
                  : currentPath.startsWith(item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href as "/dashboard"}
                  onClick={onNavigate}
                  title={collapsed ? label : undefined}
                  aria-current={active ? "page" : undefined}
                  className={`group relative flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${collapsed ? "justify-center" : ""} ${
                    active
                      ? "bg-nav-surface text-nav-text-active"
                      : "text-nav-text hover:bg-nav-surface/60 hover:text-nav-text-active"
                  }`}
                >
                  {active && (
                    <span className="absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-r-full bg-accent-primary" />
                  )}
                  <Icon className={`h-[18px] w-[18px] shrink-0 ${active ? "text-accent-primary" : ""}`} />
                  {!collapsed && <span className="flex-1 truncate">{label}</span>}
                  {locked && !collapsed && <Lock className="h-3.5 w-3.5 shrink-0 text-nav-text/60" aria-hidden="true" />}
                </Link>
              );
            })}
          </div>
        </div>
      ))}
    </nav>
  );
}

function Brand({ collapsed }: { collapsed: boolean }) {
  return (
    <Link
      href="/dashboard"
      className={`flex h-16 shrink-0 items-center gap-2.5 border-b border-nav-border ${collapsed ? "justify-center" : "px-5"}`}
    >
      <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-gradient text-sm font-bold text-[#06201f]">
        S
      </span>
      {!collapsed && (
        <span className="text-lg font-semibold tracking-tight text-nav-text-active">SYNORA</span>
      )}
    </Link>
  );
}

export default function DashboardShell({ children }: { children: React.ReactNode }) {
  const t = useTranslations("shell");
  const tc = useTranslations("common");
  const pathname = usePathname();
  const { user, logout, can } = useAuth();
  const { branches, selectedBranchId, setSelectedBranchId } = useBranch();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [theme, setTheme] = useState<DashboardTheme>("dark");

  useEffect(() => {
    try {
      setCollapsed(localStorage.getItem(COLLAPSE_KEY) === "1");
    } catch {
      // storage blocked: stay expanded
    }
  }, []);

  useEffect(() => {
    setTheme(readDashboardTheme());
  }, []);

  const toggleTheme = () => {
    const next: DashboardTheme = theme === "dark" ? "light" : "dark";
    setTheme(next);
    saveDashboardTheme(next);
  };

  const toggleCollapsed = () => {
    setCollapsed((prev) => {
      try {
        localStorage.setItem(COLLAPSE_KEY, prev ? "0" : "1");
      } catch {
        // ignore
      }
      return !prev;
    });
  };

  const groups = NAV_GROUPS.map((g) => ({
    ...g,
    items: g.items.filter(
      (item) =>
        (!item.permission || can(item.permission)) && (!item.platformAdmin || !!user?.is_platform_admin)
    ),
  })).filter((g) => g.items.length > 0);

  const activeItem = groups
    .flatMap((g) => g.items)
    .filter((item) => !item.soon)
    .find((item) =>
      item.href === "/dashboard" ? pathname === "/dashboard" : pathname.startsWith(item.href)
    );

  const roleName = user?.roles?.[0]?.name;
  const roleLabel = roleName
    ? (() => {
        try {
          return tc(`roles.${roleName}` as "roles.OWNER");
        } catch {
          return roleName;
        }
      })()
    : "";

  return (
    <ToastProvider>
      <PaymentRequiredToast />
      <div className="flex h-screen overflow-hidden bg-background">
        {/* Desktop sidebar */}
        <aside
          className={`hidden h-screen shrink-0 flex-col bg-nav-bg transition-[width] duration-200 lg:flex ${collapsed ? "w-[68px]" : "w-64"}`}
        >
          <Brand collapsed={collapsed} />
          <div className="flex-1 overflow-y-auto">
            <SidebarContent
              groups={groups}
              currentPath={pathname}
              collapsed={collapsed}
              onNavigate={() => setMobileOpen(false)}
            />
          </div>
          <div className="flex flex-col gap-1 border-t border-nav-border p-3">
            <button
              onClick={toggleCollapsed}
              aria-label={collapsed ? tc("ui.expand") : tc("ui.collapse")}
              title={collapsed ? tc("ui.expand") : tc("ui.collapse")}
              className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-nav-text hover:bg-nav-surface/60 hover:text-nav-text-active ${collapsed ? "justify-center" : ""}`}
            >
              {collapsed ? (
                <ChevronsRight className="h-[18px] w-[18px]" />
              ) : (
                <>
                  <ChevronsLeft className="h-[18px] w-[18px]" />
                  <span>{tc("ui.collapse")}</span>
                </>
              )}
            </button>
            <button
              onClick={() => logout()}
              title={collapsed ? t("nav.logout") : undefined}
              className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-nav-text hover:bg-nav-surface/60 hover:text-nav-text-active ${collapsed ? "justify-center" : ""}`}
            >
              <LogOut className="h-[18px] w-[18px]" />
              {!collapsed && <span>{t("nav.logout")}</span>}
            </button>
          </div>
        </aside>

        {/* Mobile / tablet drawer */}
        <AnimatePresence>
          {mobileOpen && (
            <>
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="fixed inset-0 z-40 bg-black/50 lg:hidden"
                onClick={() => setMobileOpen(false)}
              />
              <motion.aside
                initial={{ x: -288 }}
                animate={{ x: 0 }}
                exit={{ x: -288 }}
                transition={{ type: "spring", damping: 28, stiffness: 320 }}
                className="fixed inset-y-0 left-0 z-50 flex w-72 flex-col bg-nav-bg lg:hidden"
              >
                <div className="flex items-center justify-between border-b border-nav-border pr-3">
                  <Brand collapsed={false} />
                  <button
                    onClick={() => setMobileOpen(false)}
                    aria-label={t("nav.close")}
                    className="text-nav-text hover:text-nav-text-active"
                  >
                    <X className="h-5 w-5" />
                  </button>
                </div>
                <div className="flex-1 overflow-y-auto">
                  <SidebarContent
                    groups={groups}
                    currentPath={pathname}
                    collapsed={false}
                    onNavigate={() => setMobileOpen(false)}
                  />
                </div>
                <div className="border-t border-nav-border p-3">
                  <button
                    onClick={() => {
                      logout();
                      setMobileOpen(false);
                    }}
                    className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-nav-text hover:bg-nav-surface/60 hover:text-nav-text-active"
                  >
                    <LogOut className="h-[18px] w-[18px]" />
                    <span>{t("nav.logout")}</span>
                  </button>
                </div>
              </motion.aside>
            </>
          )}
        </AnimatePresence>

        {/* Main area */}
        <div className="flex min-w-0 flex-1 flex-col">
          <header className="flex h-16 shrink-0 items-center gap-3 border-b border-border-default bg-surface px-4 lg:px-6">
            <button
              onClick={() => setMobileOpen(true)}
              aria-label={t("nav.open")}
              className="text-text-secondary hover:text-text-primary lg:hidden"
            >
              <Menu className="h-5 w-5" />
            </button>

            <nav aria-label="breadcrumb" className="flex min-w-0 flex-1 items-center gap-2 text-sm text-text-secondary">
              <Link href="/dashboard" className="hover:text-text-primary">
                {t("breadcrumb.home")}
              </Link>
              {activeItem && activeItem.href !== "/dashboard" && (
                <>
                  <ChevronRight className="h-3.5 w-3.5 shrink-0" />
                  <span className="truncate font-medium text-text-primary">
                    {t(`nav.${activeItem.labelKey}`)}
                  </span>
                </>
              )}
            </nav>

            <div className="flex shrink-0 items-center gap-2 sm:gap-3">
              <button
                type="button"
                onClick={toggleTheme}
                aria-label={theme === "dark" ? tc("ui.themeLight") : tc("ui.themeDark")}
                title={theme === "dark" ? tc("ui.themeLight") : tc("ui.themeDark")}
                className="flex h-9 w-9 items-center justify-center rounded-lg text-text-secondary hover:bg-background-secondary hover:text-text-primary"
              >
                {theme === "dark" ? <Sun className="h-[18px] w-[18px]" /> : <Moon className="h-[18px] w-[18px]" />}
              </button>
              {can("orders.read") && <GlobalSearch />}
              {can("orders.read") && <NotificationBell />}
              {branches.length > 1 && (
                <select
                  value={selectedBranchId ?? ""}
                  onChange={(e) => setSelectedBranchId(e.target.value)}
                  aria-label={t("nav.branches")}
                  className="hidden h-9 rounded-lg border border-border-default bg-surface px-2.5 text-sm text-text-primary outline-none focus:border-accent-primary sm:block"
                >
                  {branches.map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.name}
                    </option>
                  ))}
                </select>
              )}
              <div className="flex items-center gap-2.5 border-l border-border-default pl-3">
                <div className="hidden text-right leading-tight sm:block">
                  <p className="max-w-[10rem] truncate text-sm font-medium text-text-primary">
                    {user?.full_name}
                  </p>
                  {roleLabel && <p className="text-xs text-text-secondary">{roleLabel}</p>}
                </div>
                <div className="flex h-9 w-9 items-center justify-center rounded-full bg-accent-primary/10 text-sm font-semibold text-accent-primary">
                  {user?.full_name?.charAt(0)?.toUpperCase()}
                </div>
              </div>
            </div>
          </header>

          <SubscriptionBanner />
          <main className="flex-1 overflow-y-auto p-4 lg:p-6">{children}</main>
        </div>
      </div>
    </ToastProvider>
  );
}
