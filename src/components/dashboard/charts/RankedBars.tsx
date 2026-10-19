export interface RankedBarRow {
  label: string;
  value: number;
  color?: string;
}

/**
 * Horizontal ranked-bar list (best-sellers, waiters, payment methods). Each
 * row carries its own direct label (name + formatted value) — identity is
 * never color-alone, satisfying the CVD floor-band requirement for the
 * fixed 4-color payment-method palette.
 */
export default function RankedBars({
  rows,
  formatValue,
  defaultColor = "var(--color-accent-primary)",
}: {
  rows: RankedBarRow[];
  formatValue: (value: number) => string;
  defaultColor?: string;
}) {
  const max = Math.max(1, ...rows.map((r) => r.value));

  if (rows.length === 0) {
    return null;
  }

  return (
    <div className="space-y-2.5">
      {rows.map((row, i) => (
        <div key={i}>
          <div className="mb-1 flex items-center justify-between text-sm">
            <span className="truncate text-text-primary">{row.label}</span>
            <span className="shrink-0 font-semibold text-text-primary">{formatValue(row.value)}</span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-background-secondary">
            <div
              className="h-full rounded-full"
              style={{
                width: `${Math.max(2, (row.value / max) * 100)}%`,
                backgroundColor: row.color ?? defaultColor,
              }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}
