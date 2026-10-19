"use client";

import { useState } from "react";

export interface DonutSegment {
  label: string;
  value: number;
  color: string;
}

/**
 * Part-to-whole donut. Every segment is identified by a direct label + count
 * in the legend (never colour alone); thin ring, 2px surface gap between
 * segments, hover highlights the matching legend row.
 */
export default function DonutChart({
  segments,
  centerLabel,
  size = 148,
}: {
  segments: DonutSegment[];
  centerLabel?: string;
  size?: number;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const total = segments.reduce((s, x) => s + x.value, 0);
  const stroke = 16;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const gap = segments.filter((s) => s.value > 0).length > 1 ? 2 : 0;

  const fracs = segments.map((seg) => (total > 0 ? seg.value / total : 0));
  const arcs = segments.map((seg, i) => {
    const start = fracs.slice(0, i).reduce((a, b) => a + b, 0);
    return { seg, i, len: Math.max(0, fracs[i] * c - gap), offset: -start * c };
  });

  return (
    <div className="flex flex-wrap items-center gap-6">
      <div className="relative shrink-0" style={{ width: size, height: size }}>
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label={centerLabel}>
          <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--color-background-secondary)" strokeWidth={stroke} />
          <g transform={`rotate(-90 ${size / 2} ${size / 2})`}>
            {arcs.map(({ seg, i, len, offset }) =>
              seg.value > 0 ? (
                <circle
                  key={i}
                  cx={size / 2}
                  cy={size / 2}
                  r={r}
                  fill="none"
                  stroke={seg.color}
                  strokeWidth={hover === i ? stroke + 3 : stroke}
                  strokeDasharray={`${len} ${c - len}`}
                  strokeDashoffset={offset}
                  opacity={hover === null || hover === i ? 1 : 0.4}
                  onMouseEnter={() => setHover(i)}
                  onMouseLeave={() => setHover(null)}
                />
              ) : null
            )}
          </g>
        </svg>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <span className="tabular text-2xl font-semibold text-text-primary">{total}</span>
          {centerLabel && <span className="text-xs text-text-secondary">{centerLabel}</span>}
        </div>
      </div>

      <ul className="min-w-[10rem] flex-1 space-y-1.5">
        {segments.map((seg, i) => (
          <li
            key={i}
            onMouseEnter={() => setHover(i)}
            onMouseLeave={() => setHover(null)}
            className={`flex items-center gap-2 text-sm ${hover !== null && hover !== i ? "opacity-50" : ""}`}
          >
            <span className="h-2.5 w-2.5 shrink-0 rounded-sm" style={{ backgroundColor: seg.color }} />
            <span className="flex-1 truncate text-text-primary">{seg.label}</span>
            <span className="tabular font-medium text-text-primary">{seg.value}</span>
            <span className="tabular w-10 text-right text-xs text-text-secondary">
              {total > 0 ? Math.round((seg.value / total) * 100) : 0}%
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
