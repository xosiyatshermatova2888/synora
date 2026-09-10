import { getTranslations } from "next-intl/server";
import Container from "@/components/Container";
import { Link } from "@/i18n/navigation";
import { BookOpen, LifeBuoy, Newspaper, Sparkles } from "lucide-react";

const RESOURCE_ICONS = { docs: BookOpen, help: LifeBuoy, about: Sparkles };

export default async function BlogContent({ locale }: { locale: string }) {
  const t = await getTranslations({ locale, namespace: "landing.blog" });
  const links = t.raw("links") as {
    href: string;
    title: string;
    text: string;
  }[];

  return (
    <section className="pb-20">
      <Container className="max-w-3xl">
        <div className="rounded-2xl border border-border-default bg-surface p-8 text-center">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-accent-primary/10 text-accent-primary">
            <Newspaper className="h-6 w-6" aria-hidden="true" />
          </div>
          <h2 className="mt-5 text-xl font-semibold text-text-primary">
            {t("soonTitle")}
          </h2>
          <p className="mx-auto mt-3 max-w-lg leading-relaxed text-text-secondary">
            {t("soonText")}
          </p>
        </div>

        <h3 className="mt-12 text-center text-lg font-semibold text-text-primary">
          {t("linksTitle")}
        </h3>
        <div className="mt-5 grid gap-4 sm:grid-cols-3">
          {links.map((l) => {
            const Icon = RESOURCE_ICONS[l.href.slice(1) as keyof typeof RESOURCE_ICONS] ?? BookOpen;
            return (
              <Link
                key={l.href}
                href={l.href}
                className="rounded-2xl border border-border-default bg-surface p-5 transition-colors hover:border-accent-primary/60"
              >
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent-primary/10 text-accent-primary">
                  <Icon className="h-5 w-5" aria-hidden="true" />
                </div>
                <h4 className="mt-3 text-sm font-semibold text-text-primary">
                  {l.title}
                </h4>
                <p className="mt-1 text-sm leading-relaxed text-text-secondary">
                  {l.text}
                </p>
              </Link>
            );
          })}
        </div>
      </Container>
    </section>
  );
}