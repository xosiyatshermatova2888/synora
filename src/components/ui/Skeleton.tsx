export default function Skeleton({ className = "" }: { className?: string }) {
  return (
    <div
      aria-hidden="true"
      className={`animate-pulse rounded-md bg-background-secondary ${className}`}
    />
  );
}

export function SkeletonRows({ rows = 6, cols = 4 }: { rows?: number; cols?: number }) {
  return (
    <div className="divide-y divide-border-default" aria-busy="true">
      {Array.from({ length: rows }).map((_, r) => (
        <div key={r} className="flex items-center gap-4 px-5 py-4">
          {Array.from({ length: cols }).map((__, c) => (
            <Skeleton key={c} className={`h-4 ${c === 0 ? "w-24" : "flex-1"}`} />
          ))}
        </div>
      ))}
    </div>
  );
}
