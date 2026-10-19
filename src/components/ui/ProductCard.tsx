"use client";

import { useState } from "react";
import { UtensilsCrossed } from "lucide-react";

/** Tappable product tile with image (graceful fallback when missing/broken). */
export default function ProductCard({
  name,
  price,
  imageUrl,
  disabled = false,
  badge,
  onClick,
}: {
  name: string;
  price: string;
  imageUrl?: string | null;
  disabled?: boolean;
  badge?: string;
  onClick: () => void;
}) {
  const [broken, setBroken] = useState(false);
  const showImage = !!imageUrl && !broken;

  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className="group flex flex-col overflow-hidden rounded-xl border border-border-default bg-surface text-left shadow-card transition-all hover:border-accent-primary/50 hover:shadow-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-primary active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-45"
    >
      <div className="relative aspect-[4/3] w-full bg-background-secondary">
        {showImage ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={imageUrl!}
            alt=""
            loading="lazy"
            onError={() => setBroken(true)}
            className="absolute inset-0 h-full w-full object-cover"
          />
        ) : (
          <div className="absolute inset-0 flex items-center justify-center text-text-secondary/40">
            <UtensilsCrossed className="h-8 w-8" />
          </div>
        )}
        {badge && (
          <span className="absolute left-2 top-2 rounded-md bg-black/60 px-2 py-0.5 text-[11px] font-medium text-white">
            {badge}
          </span>
        )}
      </div>
      <div className="p-3">
        <p className="line-clamp-2 min-h-[2.5rem] text-sm font-semibold leading-snug text-text-primary">{name}</p>
        <p className="tabular mt-1 text-sm font-semibold text-accent-primary">{price}</p>
      </div>
    </button>
  );
}
