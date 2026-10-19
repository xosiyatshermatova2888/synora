import { CheckCircle2, Clock, XCircle, Info, CircleDot } from "lucide-react";

export type Tone = "success" | "warning" | "error" | "info" | "accent" | "neutral";

const TONE_CLS: Record<Tone, string> = {
  success: "bg-success/10 text-success",
  warning: "bg-warning/10 text-warning",
  error: "bg-error/10 text-error",
  info: "bg-info/10 text-info",
  accent: "bg-accent-primary/10 text-accent-primary",
  neutral: "bg-background-secondary text-text-secondary",
};

// Icons double the colour so state never relies on colour alone, and so the
// emerald accent is never confused with the "success" green.
const TONE_ICON: Record<Tone, typeof Info> = {
  success: CheckCircle2,
  warning: Clock,
  error: XCircle,
  info: Info,
  accent: CircleDot,
  neutral: CircleDot,
};

export default function StatusBadge({
  tone = "neutral",
  children,
  className = "",
}: {
  tone?: Tone;
  children: React.ReactNode;
  className?: string;
}) {
  const Icon = TONE_ICON[tone];
  return (
    <span
      className={`inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-medium ${TONE_CLS[tone]} ${className}`}
    >
      <Icon className="h-3 w-3 shrink-0" aria-hidden="true" />
      {children}
    </span>
  );
}

// Single status -> tone map for every status family in the app.
export const orderStatusTone: Record<string, Tone> = {
  DRAFT: "neutral",
  OPEN: "info",
  PARTIALLY_PAID: "warning",
  COMPLETED: "success",
  CANCELLED: "error",
  REFUNDED: "error",
};

export const kitchenStatusTone: Record<string, Tone> = {
  PENDING: "neutral",
  NEW: "info",
  PREPARING: "warning",
  READY: "success",
  SERVED: "neutral",
};

export const paymentStatusTone: Record<string, Tone> = {
  PAID: "success",
  PENDING: "warning",
  FAILED: "error",
  VOID: "neutral",
  REFUNDED: "error",
};

export const tableStatusTone: Record<string, Tone> = {
  AVAILABLE: "success",
  OCCUPIED: "warning",
  RESERVED: "info",
  DISABLED: "neutral",
};
