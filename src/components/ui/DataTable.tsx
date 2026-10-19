"use client";

import { useMemo, useState } from "react";
import { ArrowDown, ArrowUp, ChevronsUpDown } from "lucide-react";
import { SkeletonRows } from "@/components/ui/Skeleton";
import StateView from "@/components/dashboard/StateView";

export interface Column<T> {
  key: string;
  header: string;
  render: (row: T) => React.ReactNode;
  /** Provide to make the column sortable (client-side, on the loaded rows). */
  sortValue?: (row: T) => string | number;
  align?: "left" | "right";
  className?: string;
  /** Hide below the md breakpoint (keeps tablet layouts readable). */
  hideOnMobile?: boolean;
}

export default function DataTable<T>({
  columns,
  rows,
  rowKey,
  loading = false,
  error,
  onRetry,
  emptyMessage,
  onRowClick,
  footer,
}: {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
  emptyMessage?: string;
  onRowClick?: (row: T) => void;
  /** Rendered inside the card under the table — e.g. <Pagination/>. */
  footer?: React.ReactNode;
}) {
  const [sort, setSort] = useState<{ key: string; dir: "asc" | "desc" } | null>(null);

  const sorted = useMemo(() => {
    if (!sort) return rows;
    const col = columns.find((c) => c.key === sort.key);
    if (!col?.sortValue) return rows;
    const get = col.sortValue;
    return [...rows].sort((a, b) => {
      const av = get(a);
      const bv = get(b);
      const cmp = av < bv ? -1 : av > bv ? 1 : 0;
      return sort.dir === "asc" ? cmp : -cmp;
    });
  }, [rows, sort, columns]);

  const toggleSort = (key: string) =>
    setSort((prev) =>
      prev?.key !== key ? { key, dir: "asc" } : prev.dir === "asc" ? { key, dir: "desc" } : null
    );

  return (
    <div className="overflow-hidden rounded-xl border border-border-default bg-surface shadow-card">
      {error ? (
        <StateView kind="error" message={error} onRetry={onRetry} />
      ) : loading ? (
        <SkeletonRows cols={Math.min(columns.length, 5)} />
      ) : sorted.length === 0 ? (
        <StateView kind="empty" message={emptyMessage} />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="sticky top-0 bg-background-secondary/60 text-xs uppercase tracking-wide text-text-secondary">
              <tr>
                {columns.map((col) => {
                  const active = sort?.key === col.key;
                  const SortIcon = !active ? ChevronsUpDown : sort.dir === "asc" ? ArrowUp : ArrowDown;
                  return (
                    <th
                      key={col.key}
                      scope="col"
                      aria-sort={active ? (sort.dir === "asc" ? "ascending" : "descending") : undefined}
                      className={`px-5 py-3 font-semibold ${col.align === "right" ? "text-right" : ""} ${col.hideOnMobile ? "hidden md:table-cell" : ""}`}
                    >
                      {col.sortValue ? (
                        <button
                          type="button"
                          onClick={() => toggleSort(col.key)}
                          className="inline-flex items-center gap-1 uppercase tracking-wide hover:text-text-primary"
                        >
                          {col.header}
                          <SortIcon className={`h-3 w-3 ${active ? "text-accent-primary" : "opacity-50"}`} />
                        </button>
                      ) : (
                        col.header
                      )}
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody className="divide-y divide-border-default">
              {sorted.map((row) => (
                <tr
                  key={rowKey(row)}
                  onClick={onRowClick ? () => onRowClick(row) : undefined}
                  className={onRowClick ? "cursor-pointer hover:bg-background-secondary/50" : ""}
                >
                  {columns.map((col) => (
                    <td
                      key={col.key}
                      className={`px-5 py-3.5 align-middle text-text-primary ${col.align === "right" ? "tabular text-right" : ""} ${col.hideOnMobile ? "hidden md:table-cell" : ""} ${col.className ?? ""}`}
                    >
                      {col.render(row)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {!loading && !error && footer}
    </div>
  );
}
