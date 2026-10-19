"use client";

import { useState } from "react";
import { ImageOff } from "lucide-react";

/** <img> that falls back to a neutral placeholder when missing or broken. */
export default function SafeImage({
  src,
  alt = "",
  className = "",
  iconClassName = "h-6 w-6",
}: {
  src?: string | null;
  alt?: string;
  className?: string;
  iconClassName?: string;
}) {
  const [broken, setBroken] = useState(false);
  if (!src || broken) {
    return (
      <div className={`flex items-center justify-center bg-background-secondary text-text-secondary/40 ${className}`}>
        <ImageOff className={iconClassName} aria-hidden="true" />
      </div>
    );
  }
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={src}
      alt={alt}
      loading="lazy"
      onError={() => setBroken(true)}
      className={`object-cover ${className}`}
    />
  );
}
