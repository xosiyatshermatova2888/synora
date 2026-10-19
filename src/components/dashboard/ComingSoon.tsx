"use client";

import { useTranslations } from "next-intl";
import { Hourglass } from "lucide-react";
import { Link } from "@/i18n/routing";
import PageHeader from "@/components/dashboard/PageHeader";

/**
 * Honest placeholder for modules whose backend does not exist yet — says what
 * is missing instead of faking data or fake integrations.
 */
export default function ComingSoon({
  kind,
  ctaHref,
  icon: Icon,
}: {
  kind: "delivery" | "ai";
  ctaHref: "/dashboard/orders" | "/dashboard/reports";
  icon: React.ComponentType<{ className?: string }>;
}) {
  const t = useTranslations("soonPage");
  return (
    <div>
      <PageHeader title={t(`${kind}.title`)} description={t(`${kind}.description`)} />
      <div className="mx-auto max-w-xl rounded-xl border border-dashed border-border-default bg-surface p-8 text-center shadow-card">
        <span className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-accent-primary/10 text-accent-primary">
          <Icon className="h-7 w-7" />
        </span>
        <span className="mt-4 inline-flex items-center gap-1.5 rounded-full bg-warning/10 px-3 py-1 text-xs font-semibold text-warning">
          <Hourglass className="h-3.5 w-3.5" />
          {t("badge")}
        </span>
        <h2 className="mt-3 text-lg font-semibold text-text-primary">{t("needsBackend")}</h2>
        <p className="mt-2 text-sm leading-relaxed text-text-secondary">{t(`${kind}.needs`)}</p>
        <Link
          href={ctaHref}
          className="mt-6 inline-flex h-10 items-center rounded-lg bg-accent-primary px-5 text-sm font-medium text-white hover:bg-accent-hover"
        >
          {t(`${kind}.cta`)}
        </Link>
      </div>
    </div>
  );
}
