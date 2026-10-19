"use client";

import { useState, useEffect } from "react";
import { useTranslations } from "next-intl";
import { Menu, X, ChevronDown } from "lucide-react";
import { Link } from "@/i18n/navigation";
import { AnimatePresence, motion } from "framer-motion";
import Container from "@/components/Container";
import LanguageSwitcher from "@/components/LanguageSwitcher";
import { useCTA } from "@/components/CTAProvider";

export default function Navbar({ variant = "light" }: { variant?: "light" | "dark" }) {
  const dark = variant === "dark";
  const t = useTranslations("nav");
  const { openTrial } = useCTA();
  const [scrolled, setScrolled] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [resourcesOpen, setResourcesOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 10);
    onScroll();
    window.addEventListener("scroll", onScroll);
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const scrollTo = (id: string) => {
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth" });
  };

  const resourceLinks = [
    { href: "/blog", label: t("blog") },
    { href: "/help", label: t("help") },
    { href: "/docs", label: t("docs") },
  ];

  const desktopNav = [
    {
      label: t("products"),
      action: () => scrollTo("features"),
    },
    {
      label: t("solutions"),
      action: () => scrollTo("pricing"),
    },
    {
      label: t("ai"),
      action: () => scrollTo("ai"),
    },
    {
      label: t("pricing"),
      action: () => scrollTo("pricing"),
    },
  ];

  return (
    <header
      className={`fixed inset-x-0 top-0 z-40 transition-all duration-300 ${
        dark
          ? scrolled || mobileOpen
            ? "border-b border-white/10 bg-[#071a1c]/90 text-white backdrop-blur-md"
            : "border-b border-transparent bg-transparent text-white"
          : scrolled || mobileOpen
            ? "border-b border-border-default bg-background/80 backdrop-blur-md"
            : "border-b border-transparent bg-transparent"
      }`}
    >
      <Container>
        <div className="flex h-16 items-center justify-between gap-4">
          <Link
            href="/"
            className="flex items-center gap-2 text-lg font-bold tracking-tight"
            aria-label="SYNORA home"
          >
            <span
              className="flex h-7 w-7 items-center justify-center rounded-lg bg-brand-gradient text-sm font-black text-white"
              aria-hidden="true"
            >
              S
            </span>
            SYNORA
          </Link>

          <nav className="hidden items-center gap-1 lg:flex" aria-label="Main">
            {desktopNav.map((item) => (
              <button
                key={item.label}
                onClick={item.action}
                className={`rounded-lg px-3 py-2 text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-accent-primary ${
                  dark ? "text-teal-100/75 hover:text-white" : "text-text-secondary hover:text-text-primary"
                }`}
              >
                {item.label}
              </button>
            ))}
            <div
              className="relative"
              onMouseEnter={() => setResourcesOpen(true)}
              onMouseLeave={() => setResourcesOpen(false)}
            >
              <button
                className={`flex items-center gap-1 rounded-lg px-3 py-2 text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-accent-primary ${
                  dark ? "text-teal-100/75 hover:text-white" : "text-text-secondary hover:text-text-primary"
                }`}
                aria-expanded={resourcesOpen}
              >
                {t("resources")}
                <ChevronDown className="h-3.5 w-3.5" />
              </button>
              <AnimatePresence>
                {resourcesOpen && (
                  <motion.div
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: 6 }}
                    transition={{ duration: 0.18 }}
                    className="absolute left-0 top-full mt-2 w-40 overflow-hidden rounded-xl border border-border-default bg-background-secondary p-1 shadow-xl"
                  >
                    {resourceLinks.map((r) => (
                      <Link
                        key={r.href}
                        href={r.href}
                        className="block rounded-lg px-3 py-2 text-sm text-text-secondary transition-colors hover:bg-surface hover:text-text-primary"
                      >
                        {r.label}
                      </Link>
                    ))}
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </nav>

          <div className="hidden items-center gap-3 lg:flex">
            <LanguageSwitcher />
            <Link
              href="/login"
              className={`text-sm font-medium transition-colors ${dark ? "text-teal-100/75 hover:text-white" : "text-text-secondary hover:text-text-primary"}`}
            >
              {t("login")}
            </Link>
            <button
              onClick={openTrial}
              className="h-9 rounded-lg bg-accent-primary px-4 text-sm font-medium text-white transition-all duration-200 hover:brightness-110"
            >
              {t("startTrial")}
            </button>
          </div>

          <button
            className={`rounded-lg p-2 lg:hidden ${dark ? "text-white" : "text-text-primary"}`}
            onClick={() => setMobileOpen((v) => !v)}
            aria-label="Toggle menu"
            aria-expanded={mobileOpen}
          >
            {mobileOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
          </button>
        </div>
      </Container>

      <AnimatePresence>
        {mobileOpen && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden border-t border-border-default bg-background lg:hidden"
          >
            <Container className="py-4">
              <nav className="flex flex-col gap-1" aria-label="Mobile">
                {desktopNav.map((item) => (
                  <button
                    key={item.label}
                    onClick={() => {
                      setMobileOpen(false);
                      item.action();
                    }}
                    className="rounded-lg px-3 py-2.5 text-left text-base text-text-primary hover:bg-surface"
                  >
                    {item.label}
                  </button>
                ))}
                <p className="mt-2 px-3 pt-2 text-xs font-medium uppercase tracking-wider text-text-secondary">
                  {t("resources")}
                </p>
{resourceLinks.map((r) => (
                  <Link
                    key={r.href}
                    href={r.href}
                    onClick={() => setMobileOpen(false)}
                    className="rounded-lg px-3 py-2.5 text-base text-text-primary hover:bg-surface"
                  >
                    {r.label}
                  </Link>
                ))}
                <div className="mt-2 border-t border-border-default pt-3">
                  <LanguageSwitcher variant="mobile" />
                  <Link
                    href="/login"
                    onClick={() => setMobileOpen(false)}
                    className="mt-1 block rounded-lg px-3 py-2.5 text-base text-text-primary hover:bg-surface"
                  >
                    {t("login")}
                  </Link>
                  <button
                    onClick={() => {
                      setMobileOpen(false);
                      openTrial();
                    }}
                    className="mt-2 flex h-12 items-center justify-center rounded-xl bg-accent-primary px-4 text-base font-medium text-white"
                  >
                    {t("startTrial")}
                  </button>
                </div>
              </nav>
            </Container>
          </motion.div>
        )}
      </AnimatePresence>
    </header>
  );
}


