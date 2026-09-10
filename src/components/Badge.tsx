export default function Badge({
  children,
  variant = "default",
  className = "",
}: {
  children: React.ReactNode;
  variant?: "default" | "ai";
  className?: string;
}) {
  const base =
    "inline-flex items-center gap-1.5 rounded-full border px-3.5 py-1.5 text-xs font-medium tracking-wide";
  const styles =
    variant === "ai"
      ? "border-accent-ai/30 bg-accent-ai/10 text-accent-ai"
      : "border-border-default bg-surface/60 text-text-secondary";

  return <span className={`${base} ${styles} ${className}`}>{children}</span>;
}
