"use client";

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { Search } from "lucide-react";
import { useRouter } from "@/i18n/routing";
import { SearchResultsOut, searchApi } from "@/lib/api";
import { formatMoney } from "@/lib/format";

type Group = { key: keyof SearchResultsOut; labelKey: string; to: string };

const GROUPS: Group[] = [
  { key: "orders", labelKey: "orders", to: "/dashboard/orders" },
  { key: "products", labelKey: "products", to: "/dashboard/menu" },
  { key: "customers", labelKey: "customers", to: "/dashboard/customers" },
  { key: "staff", labelKey: "staff", to: "/dashboard/staff" },
  { key: "tables", labelKey: "tables", to: "/dashboard/tables" },
];

function label(key: keyof SearchResultsOut, hit: SearchResultsOut[typeof key][number]): string {
  switch (key) {
    case "orders":
      return `#${(hit as SearchResultsOut["orders"][number]).order_number}`;
    case "products":
      return (hit as SearchResultsOut["products"][number]).name;
    case "customers": {
      const c = hit as SearchResultsOut["customers"][number];
      return c.full_name ?? c.phone ?? "—";
    }
    case "staff":
      return (hit as SearchResultsOut["staff"][number]).full_name;
    case "tables":
      return (hit as SearchResultsOut["tables"][number]).name;
  }
}

function sublabel(key: keyof SearchResultsOut, hit: SearchResultsOut[typeof key][number]): string | null {
  switch (key) {
    case "orders": {
      const o = hit as SearchResultsOut["orders"][number];
      return `${o.status} · ${formatMoney(o.total)}`;
    }
    case "products":
      return formatMoney((hit as SearchResultsOut["products"][number]).price);
    case "customers":
      return (hit as SearchResultsOut["customers"][number]).phone;
    case "staff":
      return (hit as SearchResultsOut["staff"][number]).username;
    case "tables":
      return (hit as SearchResultsOut["tables"][number]).zone;
  }
}

export default function GlobalSearch() {
  const t = useTranslations("globalSearch");
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResultsOut | null>(null);
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const q = query.trim();
    if (q.length < 2) {
      setResults(null);
      return;
    }
    const id = window.setTimeout(() => {
      searchApi
        .search(q)
        .then((r) => {
          setResults(r);
          setOpen(true);
        })
        .catch(() => {});
    }, 300);
    return () => window.clearTimeout(id);
  }, [query]);

  useEffect(() => {
    if (!open) return;
    const onOutside = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false);
    };
    const onEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onOutside);
    document.addEventListener("keydown", onEscape);
    return () => {
      document.removeEventListener("mousedown", onOutside);
      document.removeEventListener("keydown", onEscape);
    };
  }, [open]);

  const totalHits = results
    ? GROUPS.reduce((sum, g) => sum + results[g.key].length, 0)
    : 0;

  const goTo = (to: string) => {
    setOpen(false);
    setQuery("");
    setResults(null);
    router.push(to);
  };

  return (
    <div className="relative hidden sm:block" ref={wrapRef}>
      <div className="relative">
        <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-text-secondary" />
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => results && setOpen(true)}
          placeholder={t("placeholder")}
          className="w-40 rounded-lg border border-border-default bg-background py-1.5 pl-8 pr-2.5 text-sm text-text-primary outline-none focus:w-56 focus:border-accent-primary transition-all"
        />
      </div>

      {open && results && (
        <div className="absolute left-0 top-11 z-50 w-80 rounded-xl border border-border-default bg-surface shadow-lg">
          <div className="max-h-96 overflow-y-auto py-2">
            {totalHits === 0 ? (
              <p className="px-4 py-6 text-center text-sm text-text-secondary">{t("noResults")}</p>
            ) : (
              GROUPS.filter((g) => results[g.key].length > 0).map((g) => (
                <div key={g.key} className="mb-1">
                  <p className="px-4 py-1 text-xs font-semibold uppercase tracking-wide text-text-secondary">
                    {t(g.labelKey)}
                  </p>
                  {(results[g.key] as Array<SearchResultsOut[typeof g.key][number]>).map((hit) => (
                    <button
                      key={hit.id}
                      type="button"
                      onClick={() => goTo(g.to)}
                      className="flex w-full flex-col items-start gap-0.5 px-4 py-2 text-left text-sm hover:bg-background-secondary"
                    >
                      <span className="font-medium text-text-primary">{label(g.key, hit)}</span>
                      {sublabel(g.key, hit) && (
                        <span className="text-xs text-text-secondary">{sublabel(g.key, hit)}</span>
                      )}
                    </button>
                  ))}
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
