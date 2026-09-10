import { defineRouting } from "next-intl/routing";
import { createNavigation } from "next-intl/navigation";

export const locales = ["uz", "ru", "en"] as const;
export type Locale = (typeof locales)[number];
export const defaultLocale: Locale = "uz";

export const routing = defineRouting({
  locales,
  defaultLocale,
});

export const { Link, redirect, usePathname, useRouter, getPathname } =
  createNavigation(routing);
