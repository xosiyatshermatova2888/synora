"use client";

import { forwardRef } from "react";
import { Search, X } from "lucide-react";

const SearchField = forwardRef<
  HTMLInputElement,
  {
    value: string;
    onChange: (value: string) => void;
    placeholder?: string;
    clearLabel?: string;
    className?: string;
  }
>(function SearchField({ value, onChange, placeholder, clearLabel, className = "" }, ref) {
  return (
    <div className={`relative ${className}`}>
      <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-secondary" />
      <input
        ref={ref}
        type="search"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="h-10 w-full rounded-lg border border-border-default bg-surface pl-9 pr-9 text-sm text-text-primary outline-none transition-colors placeholder:text-text-secondary/70 focus:border-accent-primary [&::-webkit-search-cancel-button]:hidden"
      />
      {value && (
        <button
          type="button"
          onClick={() => onChange("")}
          aria-label={clearLabel}
          className="absolute right-2.5 top-1/2 -translate-y-1/2 text-text-secondary hover:text-text-primary"
        >
          <X className="h-4 w-4" />
        </button>
      )}
    </div>
  );
});

export default SearchField;
