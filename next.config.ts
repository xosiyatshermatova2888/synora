import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const nextConfig: NextConfig = {
  output: "standalone",
  images: {
    formats: ["image/avif", "image/webp"],
  },
  async rewrites() {
    const apiUrl = process.env.API_URL ?? "http://localhost:8000";
    return [
      // Same-origin proxy to the FastAPI backend so the httpOnly refresh
      // cookie (path /api/v1/auth) works without CORS in the browser.
      { source: "/api/:path*", destination: `${apiUrl}/api/:path*` },
      // Proxy uploaded image files served by the backend (/files/...).
      { source: "/files/:path*", destination: `${apiUrl}/files/:path*` },
    ];
  },
};

const withNextIntl = createNextIntlPlugin();

export default withNextIntl(nextConfig);