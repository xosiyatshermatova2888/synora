"use client";

import { useTranslations } from "next-intl";
import { Link } from "@/i18n/navigation";
import Container from "@/components/Container";

function TelegramIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={className} aria-hidden="true">
      <path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zm4.8 6.9-1.7 8c-.13.6-.49.74-.99.46l-2.7-2-1.3 1.26c-.15.14-.27.27-.55.27l.2-2.8 5.1-4.6c.22-.2-.05-.3-.34-.11L8.6 13.1l-2.7-.9c-.6-.18-.6-.6.13-.9l10.5-4c.5-.2.95.12.77.6z" />
    </svg>
  );
}

function InstagramIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className={className} aria-hidden="true">
      <rect x="2" y="2" width="20" height="20" rx="5" />
      <circle cx="12" cy="12" r="4" />
      <circle cx="17.5" cy="6.5" r="1" fill="currentColor" stroke="none" />
    </svg>
  );
}

function LinkedinIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={className} aria-hidden="true">
      <path d="M20.45 20.45h-3.55v-5.57c0-1.33-.03-3.04-1.85-3.04-1.85 0-2.13 1.44-2.13 2.94v5.67H9.35V9h3.41v1.56h.05c.47-.9 1.63-1.85 3.36-1.85 3.6 0 4.27 2.37 4.27 5.45v6.29zM5.34 7.43a2.06 2.06 0 1 1 0-4.13 2.06 2.06 0 0 1 0 4.13zM7.12 20.45H3.56V9h3.56v11.45z" />
    </svg>
  );
}

export default function Footer() {
  const t = useTranslations("footer");
  const fl = useTranslations("footer.links");

  const productLinks = [
    { href: "/features", key: "features" },
    { href: "/pricing", key: "pricing" },
    { href: "/ai", key: "ai" },
    { href: "/demo", key: "demo" },
  ];

  const companyLinks = [
    { href: "/about", key: "about" },
    { href: "/contact", key: "contact" },
  ];

  const resourceLinks = [
    { href: "/blog", key: "blog" },
    { href: "/help", key: "help" },
    { href: "/docs", key: "docs" },
  ];

  const legalLinks = [
    { href: "/privacy", key: "privacy" },
    { href: "/terms", key: "terms" },
  ];

  const columns = [
    { title: t("product"), links: productLinks },
    { title: t("company"), links: companyLinks },
    { title: t("resources"), links: resourceLinks },
    { title: t("legal"), links: legalLinks },
  ];

  return (
    <footer className="border-t border-border-default bg-background-secondary/60">
      <Container className="py-14">
        <div className="grid gap-10 lg:grid-cols-5">
          <div className="lg:col-span-2">
            <Link href="/" className="flex items-center gap-2 text-lg font-bold tracking-tight">
              <span
                className="flex h-7 w-7 items-center justify-center rounded-lg bg-brand-gradient text-sm font-black text-white"
                aria-hidden="true"
              >
                S
              </span>
              SYNORA
            </Link>
            <p className="mt-4 max-w-xs text-sm text-text-secondary">
              {t("tagline")}
            </p>
            <div className="mt-6 flex gap-3">
              <a
                href="https://t.me/"
                target="_blank"
                rel="noopener noreferrer"
                aria-label="Telegram"
                className="flex h-10 w-10 items-center justify-center rounded-lg border border-border-default bg-surface text-text-secondary transition-colors hover:border-accent-primary/50 hover:text-text-primary"
              >
                <TelegramIcon className="h-4 w-4" />
              </a>
              <a
                href="https://instagram.com/"
                target="_blank"
                rel="noopener noreferrer"
                aria-label="Instagram"
                className="flex h-10 w-10 items-center justify-center rounded-lg border border-border-default bg-surface text-text-secondary transition-colors hover:border-accent-primary/50 hover:text-text-primary"
              >
                <InstagramIcon className="h-4 w-4" />
              </a>
              <a
                href="https://linkedin.com/"
                target="_blank"
                rel="noopener noreferrer"
                aria-label="LinkedIn"
                className="flex h-10 w-10 items-center justify-center rounded-lg border border-border-default bg-surface text-text-secondary transition-colors hover:border-accent-primary/50 hover:text-text-primary"
              >
                <LinkedinIcon className="h-4 w-4" />
              </a>
            </div>
          </div>

          {columns.map((col) => (
            <div key={col.title}>
              <h3 className="mb-4 text-sm font-semibold text-text-primary">
                {col.title}
              </h3>
              <ul className="space-y-2.5">
                {col.links.map((l) => (
                  <li key={l.href}>
                    <Link
                      href={l.href}
                      className="text-sm text-text-secondary transition-colors hover:text-text-primary"
                    >
                      {fl(l.key)}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="mt-12 border-t border-border-default pt-6 text-center text-sm text-text-secondary">
          © 2026 SYNORA. {t("rights")}
        </div>
      </Container>
    </footer>
  );
}

