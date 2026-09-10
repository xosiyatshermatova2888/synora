"use client";

import { usePathname, useRouter } from "@/i18n/navigation";
import { useLocale } from "next-intl";
import { useTransition } from "react";
import { Languages, Check } from "lucide-react";
import { locales } from "@/i18n/routing";

const labels: Record<string, string> = {
  uz: "O‘zbek",
  ru: "Русский",
  en: "English",
};

export default function LanguageSwitcher({
  variant = "desktop",
}: {
  variant?: "desktop" | "mobile";
}) {
  const locale = useLocale();
  const router = useRouter();
  const pathname = usePathname();
  const [isPending, startTransition] = useTransition();

  const handleChange = (next: string) => {
    startTransition(() => {
      router.replace(pathname, { locale: next });
    });
  };

  if (variant === "mobile") {
    return (
      <div className="flex flex-col gap-1">
        {locales.map((loc) => (
          <button
            key={loc}
            onClick={() => handleChange(loc)}
            className="flex items-center justify-between rounded-lg px-3 py-2 text-left text-sm text-text-primary transition-colors hover:bg-surface"
          >
            {labels[loc]}
            {loc === locale && <Check className="h-4 w-4 text-accent-primary" />}
          </button>
        ))}
      </div>
    );
  }

  return (
    <div className="relative">
      <div className="flex items-center gap-0.5 rounded-lg border border-border-default bg-surface/60 p-1">
        <Languages className="mr-1 ml-1 h-4 w-4 text-text-secondary" />
        {locales.map((loc) => (
          <button
            key={loc}
            onClick={() => handleChange(loc)}
            disabled={isPending}
            aria-label={labels[loc]}
            className={`rounded-md px-2 py-1 text-xs font-medium transition-colors focus-visible:outline-2 focus-visible:outline-accent-primary ${
              loc === locale
                ? "bg-accent-primary/20 text-accent-ai"
                : "text-text-secondary hover:text-text-primary"
            }`}
          >
            {loc.toUpperCase()}
          </button>
        ))}
      </div>
    </div>
  );
}
