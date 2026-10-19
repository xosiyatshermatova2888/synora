"use client";

import { useEffect } from "react";
import { useTranslations } from "next-intl";
import { AlertTriangle, Clock, Lock } from "lucide-react";
import { PAYMENT_REQUIRED_EVENT } from "@/lib/api";
import { Link } from "@/i18n/routing";
import { useAuth } from "@/lib/auth-context";
import { useSubscription } from "@/lib/subscription-context";
import { useToast } from "@/components/ui/Toast";

/** Explains every 402 the server returns, from whichever page caused it. */
export function PaymentRequiredToast() {
  const t = useTranslations("subscription.toast");
  const toast = useToast();

  useEffect(() => {
    const onEvent = (e: Event) => {
      const code = (e as CustomEvent<{ code?: string }>).detail?.code;
      toast.error(code === "subscription_expired" ? t("expired") : t("planRequired"));
    };
    window.addEventListener(PAYMENT_REQUIRED_EVENT, onEvent);
    return () => window.removeEventListener(PAYMENT_REQUIRED_EVENT, onEvent);
  }, [toast, t]);

  return null;
}

/** Trial / grace / read-only strip across the top of every dashboard page. */
export default function SubscriptionBanner() {
  const t = useTranslations("subscription.banner");
  const { can } = useAuth();
  const { subscription } = useSubscription();
  if (!subscription) return null;

  const { status, access, days_left, grace_days_left } = subscription;
  const showTrial = status === "TRIAL" && access === "FULL" && days_left !== null && days_left <= 7;
  if (access === "FULL" && !showTrial) return null;

  let tone = "border-warning/40 bg-warning/10 text-text-primary";
  let Icon = Clock;
  let text: string;
  if (access === "READ_ONLY") {
    tone = "border-error/40 bg-error/10 text-text-primary";
    Icon = Lock;
    text = t("readOnly");
  } else if (access === "GRACE") {
    Icon = AlertTriangle;
    text = t("grace", { days: grace_days_left ?? 0 });
  } else {
    tone = "border-accent-primary/30 bg-accent-primary/10 text-text-primary";
    text = days_left !== null && days_left <= 1 ? t("trialLast") : t("trial", { days: days_left ?? 0 });
  }

  return (
    <div role="status" className={`flex flex-wrap items-center gap-x-3 gap-y-1 border-b px-4 py-2 text-sm lg:px-6 ${tone}`}>
      <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
      <span className="min-w-0 flex-1">{text}</span>
      {can("users.manage") ? (
        <Link
          href="/dashboard/subscription"
          className="shrink-0 rounded-md bg-accent-primary px-3 py-1 text-xs font-semibold text-white hover:bg-accent-hover"
        >
          {t("pay")}
        </Link>
      ) : (
        <span className="shrink-0 text-xs text-text-secondary">{t("askOwner")}</span>
      )}
    </div>
  );
}
