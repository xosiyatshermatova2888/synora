import Skeleton from "@/components/ui/Skeleton";

type Accent = "accent" | "success" | "warning" | "info" | "neutral";

const ACCENT_CLS: Record<Accent, string> = {
  accent: "bg-accent-primary/10 text-accent-primary",
  success: "bg-success/10 text-success",
  warning: "bg-warning/10 text-warning",
  info: "bg-info/10 text-info",
  neutral: "bg-background-secondary text-text-secondary",
};

export default function MetricCard({
  label,
  value,
  hint,
  icon: Icon,
  accent = "accent",
  loading = false,
}: {
  label: string;
  value: string;
  hint?: string;
  icon?: React.ComponentType<{ className?: string }>;
  accent?: Accent;
  loading?: boolean;
}) {
  return (
    <div className="rounded-xl border border-border-default bg-surface p-5 shadow-card">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm font-medium text-text-secondary">{label}</p>
        {Icon && (
          <span className={`flex h-9 w-9 items-center justify-center rounded-lg ${ACCENT_CLS[accent]}`}>
            <Icon className="h-[18px] w-[18px]" />
          </span>
        )}
      </div>
      {loading ? (
        <Skeleton className="mt-3 h-8 w-32" />
      ) : (
        <p className="tabular mt-2 truncate text-2xl font-semibold text-text-primary">{value}</p>
      )}
      {hint && !loading && <p className="mt-1 text-xs text-text-secondary">{hint}</p>}
    </div>
  );
}
