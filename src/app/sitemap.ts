import type { MetadataRoute } from "next";

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const base = "https://synora.app";
  const locales = ["uz", "ru", "en"] as const;
  const paths = ["", "/features", "/pricing", "/ai", "/demo", "/about", "/contact", "/blog", "/help", "/docs", "/privacy", "/terms"];

  return locales.flatMap((locale) =>
    paths.map((path) => ({
      url: `${base}/${locale}${path}`,
      lastModified: new Date(),
      changeFrequency: "monthly" as const,
      priority: path === "" ? 1 : 0.7,
    }))
  );
}
