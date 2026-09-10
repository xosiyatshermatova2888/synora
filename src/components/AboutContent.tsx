import { getTranslations } from "next-intl/server";
import Container from "@/components/Container";
import {
  Brain,
  Layers,
  ShieldCheck,
  Target,
} from "lucide-react";

const ICONS: Record<string, typeof Target> = {
  oneSystem: Layers,
  aiNative: Brain,
  private: ShieldCheck,
  mission: Target,
};

export default async function AboutContent({ locale }: { locale: string }) {
  const t = await getTranslations({ locale, namespace: "landing.about" });
  const cards = t.raw("cards") as {
    icon: keyof typeof ICONS;
    title: string;
    text: string;
  }[];
  const values = t.raw("values") as string[];

  return (
    <section className="pb-20">
      <Container className="max-w-4xl">
        <div className="prose prose-lg max-w-none text-text-secondary">
          <p className="text-lg leading-relaxed">{t("intro")}</p>
        </div>

        <div className="mt-12 grid gap-6 sm:grid-cols-2">
          {cards.map((c) => {
            const Icon = ICONS[c.icon] ?? Target;
            return (
              <div
                key={c.title}
                className="rounded-2xl border border-border-default bg-surface p-6"
              >
                <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-accent-primary/10 text-accent-primary">
                  <Icon className="h-5 w-5" aria-hidden="true" />
                </div>
                <h3 className="mt-4 text-lg font-semibold text-text-primary">
                  {c.title}
                </h3>
                <p className="mt-2 text-sm leading-relaxed text-text-secondary">
                  {c.text}
                </p>
              </div>
            );
          })}
        </div>

        <div className="mt-12">
          <h3 className="text-xl font-semibold text-text-primary">
            {t("valuesTitle")}
          </h3>
          <ul className="mt-4 space-y-3">
            {values.map((v) => (
              <li
                key={v}
                className="flex items-start gap-3 text-text-secondary"
              >
                <span
                  className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-accent-primary"
                  aria-hidden="true"
                />
                {v}
              </li>
            ))}
          </ul>
        </div>
      </Container>
    </section>
  );
}