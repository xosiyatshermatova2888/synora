import type { Metadata } from "next";
import { hasLocale } from "next-intl";
import { getTranslations } from "next-intl/server";
import { routing } from "@/i18n/routing";
import { notFound } from "next/navigation";

export async function pageMetadata(
  locale: string,
  key: string,
): Promise<Metadata> {
  if (!hasLocale(routing.locales, locale)) {
    notFound();
  }
  const t = await getTranslations({ locale, namespace: "pages" });
  return {
    title: t(key),
  };
}