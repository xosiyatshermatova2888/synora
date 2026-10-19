"use client";

import { createContext, useCallback, useContext, useMemo, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { CheckCircle2, AlertCircle, Info, X } from "lucide-react";

type ToastKind = "success" | "error" | "info";
interface ToastItem {
  id: number;
  kind: ToastKind;
  message: string;
}
interface ToastApi {
  success: (message: string) => void;
  error: (message: string) => void;
  info: (message: string) => void;
}

const ToastContext = createContext<ToastApi | undefined>(undefined);

const KIND_STYLE: Record<ToastKind, { icon: typeof Info; cls: string }> = {
  success: { icon: CheckCircle2, cls: "text-success" },
  error: { icon: AlertCircle, cls: "text-error" },
  info: { icon: Info, cls: "text-info" },
};

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const t = useTranslations("common.ui");
  const [items, setItems] = useState<ToastItem[]>([]);
  const nextId = useRef(1);

  const dismiss = useCallback((id: number) => {
    setItems((prev) => prev.filter((x) => x.id !== id));
  }, []);

  const push = useCallback(
    (kind: ToastKind, message: string) => {
      const id = nextId.current++;
      setItems((prev) => [...prev.slice(-3), { id, kind, message }]);
      window.setTimeout(() => dismiss(id), kind === "error" ? 6000 : 3500);
    },
    [dismiss]
  );

  const api = useMemo<ToastApi>(
    () => ({
      success: (m) => push("success", m),
      error: (m) => push("error", m),
      info: (m) => push("info", m),
    }),
    [push]
  );

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div
        aria-live="polite"
        className="pointer-events-none fixed bottom-4 right-4 z-[60] flex w-[min(92vw,22rem)] flex-col gap-2"
      >
        {items.map((item) => {
          const { icon: Icon, cls } = KIND_STYLE[item.kind];
          return (
            <div
              key={item.id}
              role={item.kind === "error" ? "alert" : "status"}
              className="pointer-events-auto flex items-start gap-3 rounded-lg border border-border-default bg-surface p-3.5 shadow-pop"
            >
              <Icon className={`mt-0.5 h-4 w-4 shrink-0 ${cls}`} />
              <p className="min-w-0 flex-1 text-sm text-text-primary">{item.message}</p>
              <button
                type="button"
                onClick={() => dismiss(item.id)}
                aria-label={t("dismiss")}
                className="text-text-secondary hover:text-text-primary"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastApi {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within <ToastProvider>");
  return ctx;
}
