import { Inter } from "next/font/google";
import type { Metadata, Viewport } from "next";
import { MotionConfig } from "framer-motion";
import "@/app/globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  display: "swap",
});

export const metadata: Metadata = {
  metadataBase: new URL("https://synora.app"),
  title: {
    default: "SYNORA — AI-Powered Restaurant Management",
    template: "%s — SYNORA",
  },
  description:
    "SYNORA is an intelligent restaurant operating system for POS, kitchen, inventory, CRM, analytics and AI-powered business management.",
  applicationName: "SYNORA",
  openGraph: {
    siteName: "SYNORA",
    type: "website",
    locale: "uz_UZ",
  },
  twitter: {
    card: "summary_large_image",
  },
};

export const viewport: Viewport = {
  themeColor: "#f6f7fa",
  colorScheme: "light",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="uz" className={inter.variable}>
      <body className="min-h-screen bg-background font-sans text-text-primary antialiased">
        <MotionConfig reducedMotion="user">{children}</MotionConfig>
      </body>
    </html>
  );
}
