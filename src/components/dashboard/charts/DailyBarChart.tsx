"use client";

import { useState } from "react";

export interface DailyBarPoint {
  label: string;
  value: number;
}

/**
 * Single-hue magnitude chart (dataviz skill: sequential = one hue). Thin
 * bars, 4px rounded data-ends anchored to the baseline, a 2px surface gap
 * between adjacent bars, recessive baseline (no heavy gridlines), and a
 * per-bar hover tooltip.
 */
export default function DailyBarChart({
  points,
  formatValue,
  color = "var(--color-accent-primary)",
  height = 180,
}: {
  points: DailyBarPoint[];
  formatValue: (value: number) => string;
  color?: string;
  height?: number;
}) {
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);
  const max = Math.max(1, ...points.map((p) => p.value));
  // Thin out x-axis labels when there are many bars, to avoid collisions.
  const labelEvery = points.length > 14 ? Math.ceil(points.length / 10) : 1;

  if (points.length === 0) {
    return null;
  }

  return (
    <div className="relative">
      <div className="flex items-end gap-1" style={{ height }}>
        {points.map((p, i) => {
          const barHeight = Math.max(2, (p.value / max) * (height - 4));
          return (
            <div
              key={i}
              className="group relative flex-1"
              style={{ height }}
              onMouseEnter={() => setHoverIndex(i)}
              onMouseLeave={() => setHoverIndex((v) => (v === i ? null : v))}
            >
              <div className="absolute bottom-0 left-0 right-0 flex justify-center px-px">
                <div
                  className="w-full rounded-t"
                  style={{
                    height: barHeight,
                    backgroundColor: color,
                    opacity: hoverIndex === null || hoverIndex === i ? 1 : 0.45,
                  }}
                />
              </div>
              {hoverIndex === i && (
                <div className="pointer-events-none absolute bottom-full left-1/2 z-10 mb-1.5 -translate-x-1/2 whitespace-nowrap rounded-lg border border-border-default bg-surface px-2 py-1 text-xs shadow-md">
                  <span className="font-semibold text-text-primary">{formatValue(p.value)}</span>
                  <span className="ml-1 text-text-secondary">{p.label}</span>
                </div>
              )}
            </div>
          );
        })}
      </div>
      <div className="mt-1.5 flex gap-1 border-t border-border-default pt-1.5">
        {points.map((p, i) => (
          <div key={i} className="flex-1 text-center text-[10px] text-text-secondary">
            {i % labelEvery === 0 ? p.label : ""}
          </div>
        ))}
      </div>
    </div>
  );
}
