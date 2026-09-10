import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "SYNORA — AI-Powered Restaurant Management",
    short_name: "SYNORA",
    description:
      "SYNORA is an intelligent restaurant operating system for POS, kitchen, inventory, CRM, analytics and AI-powered business management.",
    start_url: "/",
    display: "standalone",
    background_color: "#080A0F",
    theme_color: "#080A0F",
    icons: [
      { src: "/icon.svg", sizes: "any", type: "image/svg+xml" },
    ],
  };
}
