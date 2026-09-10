"use client";

import { Loader2, AlertTriangle, Inbox } from "lucide-react";

interface StateViewProps {
  kind: "loading" | "error" | "empty";
  message?: string;
  onRetry?: () => void;
}

export default function StateView({
  kind,
  message,
  onRetry,
}: StateViewProps) {
  if (kind === "loading") {
    return (
      <div className="flex flex-col items-center justify-center gap-3 py-24 text-text-secondary">
        <Loader2 className="h-8 w-8 animate-spin text-accent-primary" />
        <p className="text-sm">{message ?? "Loading…"}</p>
      </div>
    );
  }

  if (kind === "error") {
    return (
      <div className="flex flex-col items-center justify-center gap-3 py-24 text-center">
        <AlertTriangle className="h-8 w-8 text-error" />
        <p className="text-sm font-medium text-text-primary">
          {message ?? "Something went wrong."}
        </p>
        {onRetry && (
          <button
            onClick={onRetry}
            className="mt-1 inline-flex items-center gap-2 rounded-lg border border-border-default px-3 py-1.5 text-sm font-medium text-text-secondary hover:bg-background-secondary hover:text-text-primary"
          >
            Retry
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center gap-3 py-24 text-center">
      <Inbox className="h-8 w-8 text-text-secondary" />
      <p className="text-sm font-medium text-text-primary">
        {message ?? "Nothing here yet."}
      </p>
    </div>
  );
}