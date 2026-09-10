import type { MetadataRoute } from "next";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: "/",
    },
    sitemap: [
      "https://synora.app/uz/sitemap.xml",
      "https://synora.app/ru/sitemap.xml",
      "https://synora.app/en/sitemap.xml",
    ],
  };
}
