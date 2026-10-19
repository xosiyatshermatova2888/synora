"use client";

import { useTranslations } from "next-intl";
import { ChevronLeft, ChevronRight } from "lucide-react";

export default function Pagination({
  total,
  limit,
  offset,
  onChange,
}: {
  total: number;
  limit: number;
  offset: number;
  onChange: (offset: number) => void;
}) {
  const t = useTranslations("common.ui");
  if (total <= 0) return null;
  const from = offset + 1;
  const to = Math.min(offset + limit, total);
  const canPrev = offset > 0;
  const canNext = offset + limit < total;

  return (
    <div className="flex items-center justify-between gap-3 border-t border-border-default px-5 py-3 text-sm text-text-secondary">
      <span className="tabular">{t("range", { from, to, total })}</span>
      <div className="flex items-center gap-1.5">
        <button
          type="button"
          disabled={!canPrev}
          onClick={() => onChange(Math.max(0, offset - limit))}
          aria-label={t("prev")}
          className="flex h-8 w-8 items-center justify-center rounded-lg border border-border-default hover:bg-background-secondary disabled:opacity-40"
        >
          <ChevronLeft className="h-4 w-4" />
        </button>
        <button
          type="button"
          disabled={!canNext}
          onClick={() => onChange(offset + limit)}
          aria-label={t("next")}
          className="flex h-8 w-8 items-center justify-center rounded-lg border border-border-default hover:bg-background-secondary disabled:opacity-40"
        >
          <ChevronRight className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
