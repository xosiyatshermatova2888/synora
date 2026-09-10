import { getRequestConfig } from "next-intl/server";
import { hasLocale } from "next-intl";
import { routing } from "./routing";

export default getRequestConfig(async ({ locale, requestLocale }) => {
  const requested = locale ?? (await requestLocale);
  const resolved = hasLocale(routing.locales, requested)
    ? requested
    : routing.defaultLocale;

  return {
    locale: resolved,
    messages: (await import(`../messages/${resolved}.json`)).default,
  };
});