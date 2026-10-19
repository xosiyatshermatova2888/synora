"use client";

export interface TabItem {
  key: string;
  label: string;
  count?: number;
}

/** Pill-style filter tabs (status filters, category filters). */
export default function Tabs({
  items,
  value,
  onChange,
  className = "",
}: {
  items: TabItem[];
  value: string | null;
  onChange: (key: string) => void;
  className?: string;
}) {
  return (
    <div role="tablist" className={`flex items-center gap-1.5 overflow-x-auto pb-0.5 ${className}`}>
      {items.map((item) => {
        const active = item.key === value;
        return (
          <button
            key={item.key}
            role="tab"
            aria-selected={active}
            type="button"
            onClick={() => onChange(item.key)}
            className={`inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
              active
                ? "bg-accent-primary text-white shadow-sm"
                : "bg-surface text-text-secondary ring-1 ring-inset ring-border-default hover:text-text-primary"
            }`}
          >
            {item.label}
            {item.count !== undefined && (
              <span
                className={`tabular rounded-full px-1.5 text-xs ${
                  active ? "bg-white/20 text-white" : "bg-background-secondary text-text-secondary"
                }`}
              >
                {item.count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
