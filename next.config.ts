import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false, // do not advertise the framework in every response
  images: {
    formats: ["image/avif", "image/webp"],
  },
  async headers() {
    // Baseline hardening for every response (also when the app is reached
    // directly on the LAN, without the Caddy proxy that adds the same).
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "SAMEORIGIN" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
        ],
      },
    ];
  },
  async rewrites() {
    const apiUrl = process.env.API_URL ?? "http://localhost:8000";
    const minioUrl = process.env.MINIO_URL ?? "http://localhost:9000";
    return [
      // Same-origin proxy to MinIO so image URLs (`/uploads/<bucket>/<key>`)
      // work from any device that can reach the app, not just the PC.
      { source: "/uploads/:path*", destination: `${minioUrl}/:path*` },
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