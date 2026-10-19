"use client";

import { useTranslations } from "next-intl";
import { Loader2, AlertTriangle, Inbox } from "lucide-react";

interface StateViewProps {
  kind: "loading" | "error" | "empty";
  message?: string;
  onRetry?: () => void;
}

export default function StateView({ kind, message, onRetry }: StateViewProps) {
  const t = useTranslations("common");

  if (kind === "loading") {
    return (
      <div className="flex flex-col items-center justify-center gap-3 py-20 text-text-secondary">
        <Loader2 className="h-7 w-7 animate-spin text-accent-primary" />
        <p className="text-sm">{message ?? t("states.loading")}</p>
      </div>
    );
  }

  if (kind === "error") {
    return (
      <div role="alert" className="flex flex-col items-center justify-center gap-3 py-20 text-center">
        <span className="flex h-12 w-12 items-center justify-center rounded-full bg-error/10">
          <AlertTriangle className="h-6 w-6 text-error" />
        </span>
        <p className="max-w-sm text-sm font-medium text-text-primary">
          {message ?? t("states.error")}
        </p>
        {onRetry && (
          <button
            onClick={onRetry}
            className="mt-1 inline-flex h-9 items-center gap-2 rounded-lg border border-border-default px-4 text-sm font-medium text-text-secondary hover:bg-background-secondary hover:text-text-primary"
          >
            {t("actions.retry")}
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center gap-3 py-20 text-center">
      <span className="flex h-12 w-12 items-center justify-center rounded-full bg-background-secondary">
        <Inbox className="h-6 w-6 text-text-secondary" />
      </span>
      <p className="max-w-sm text-sm font-medium text-text-primary">
        {message ?? t("states.empty")}
      </p>
    </div>
  );
}
