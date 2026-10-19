/**
 * Money / currency formatting helpers.
 *
 * We keep a small runtime map of well-known currencies; for anything not
 * listed we fall back to plain number formatting with the ISO code appended.
 */

const CURRENCY_LOCALES: Record<string, string> = {
  UZS: "uz-UZ",
  USD: "en-US",
  EUR: "de-DE",
  RUB: "ru-RU",
  KZT: "kk-KZ",
  TRY: "tr-TR",
  GBP: "en-GB",
  JPY: "ja-JP",
};

/**
 * Format a decimal string (money) into a locale-aware display string.
 * @param value  Decimal string from the API, e.g. "120000.00"
 * @param currency  ISO 4217 currency code, e.g. "UZS"
 */
export function formatMoney(value: string | number, currency?: string): string {
  const num = typeof value === "number" ? value : parseFloat(value);
  if (isNaN(num)) return value?.toString() ?? "—";

  const cur = currency?.toUpperCase() ?? "UZS";

  // Fraction digits: UZS has 0, most others 2, JPY has 0.
  const fractionDigits = cur === "UZS" || cur === "JPY" ? 0 : 2;

  const locale = CURRENCY_LOCALES[cur] ?? "en-US";

  return new Intl.NumberFormat(locale, {
    style: "currency",
    currency: cur,
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  }).format(num);
}

/** Only same-site paths and http(s) URLs may become a link/image source; a
 * `javascript:` or `data:` value stored by someone else must never run. */
export function safeUrl(url: string | null | undefined): string | null {
  if (!url) return null;
  return /^(\/(?!\/)|https?:\/\/)/i.test(url) ? url : null;
}

/**
 * Format an ISO date string to a short human-readable date + time.
 */
export function formatDateTime(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/**
 * Format an ISO date string to a short date only.
 */
export function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}
