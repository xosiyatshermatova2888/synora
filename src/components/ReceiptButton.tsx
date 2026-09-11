"use client";

import { useLocale, useTranslations } from "next-intl";
import { Printer } from "lucide-react";

/**
 * Opens /[locale]/receipt?order=<id> in a new tab — a bare, print-only page
 * (see src/app/[locale]/receipt/page.tsx) so the thermal-printer CSS never
 * has to fight the dashboard's own chrome.
 */
export default function ReceiptButton({
  orderId,
  className,
}: {
  orderId: string;
  className?: string;
}) {
  const locale = useLocale();
  const t = useTranslations("common");

  return (
    <button
      type="button"
      onClick={() =>
        window.open(`/${locale}/receipt?order=${orderId}`, "_blank", "noopener,noreferrer")
      }
      className={
        className ??
        "flex items-center gap-1.5 rounded-lg border border-border-default px-3 py-1.5 text-xs font-medium text-text-secondary hover:border-accent-primary/60 hover:text-accent-primary"
      }
    >
      <Printer className="h-3.5 w-3.5" />
      {t("printReceipt")}
    </button>
  );
}
