"use client";

import { useTranslations } from "next-intl";
import { Lock } from "lucide-react";
import { Link } from "@/i18n/routing";
import { useAuth } from "@/lib/auth-context";
import { useSubscription } from "@/lib/subscription-context";
import StateView from "@/components/dashboard/StateView";

const MIN_PLAN: Record<string, "PRO" | "AI_PREMIUM"> = {
  inventory: "PRO",
  crm: "PRO",
  advanced_reports: "PRO",
  multi_branch: "PRO",
  ai_assistant: "AI_PREMIUM",
};

/** Paywall: renders `children` only when the plan includes `feature`. The
 * server enforces the same rule (402); this just avoids a page of errors. */
export default function PlanGate({
  feature,
  children,
}: {
  feature: string;
  children: React.ReactNode;
}) {
  const t = useTranslations("subscription");
  const { can } = useAuth();
  const { has, loaded } = useSubscription();

  // Don't mount the page (and its requests) until we know the plan.
  if (!loaded) return <StateView kind="loading" />;
  if (has(feature)) return <>{children}</>;

  const plan = t(`plans.name.${MIN_PLAN[feature] ?? "PRO"}`);
  return (
    <div className="mx-auto flex max-w-md flex-col items-center gap-4 py-20 text-center">
      <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-accent-primary/10 text-accent-primary">
        <Lock className="h-7 w-7" aria-hidden="true" />
      </span>
      <h2 className="text-lg font-semibold text-text-primary">{t("gate.title", { plan })}</h2>
      <p className="text-sm text-text-secondary">
        {t("gate.description", { feature: t(`plans.feature.${feature}`), plan })}
      </p>
      {can("users.manage") ? (
        <Link
          href="/dashboard/subscription"
          className="inline-flex h-10 items-center rounded-lg bg-accent-primary px-5 text-sm font-medium text-white hover:bg-accent-hover"
        >
          {t("gate.upgrade")}
        </Link>
      ) : (
        <p className="text-xs text-text-secondary">{t("gate.askOwner")}</p>
      )}
    </div>
  );
}

/** Compact in-page lock for one panel of an otherwise open page (e.g. the
 * advanced charts on Reports). */
export function LockedPanel({ feature, className = "" }: { feature: string; className?: string }) {
  const t = useTranslations("subscription");
  const { can } = useAuth();
  const plan = t(`plans.name.${MIN_PLAN[feature] ?? "PRO"}`);
  return (
    <div
      className={`flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-border-default bg-surface/60 p-6 text-center ${className}`}
    >
      <Lock className="h-5 w-5 text-accent-primary" aria-hidden="true" />
      <p className="text-sm font-medium text-text-primary">{t("gate.title", { plan })}</p>
      {can("users.manage") && (
        <Link href="/dashboard/subscription" className="text-xs font-semibold text-accent-primary hover:underline">
          {t("gate.upgrade")}
        </Link>
      )}
    </div>
  );
}
