import { getTranslations } from "next-intl/server";
import Container from "@/components/Container";
import { CircleCheck, ListChecks, MessageCircleQuestion } from "lucide-react";

export default async function HelpContent({ locale }: { locale: string }) {
  const t = await getTranslations({ locale, namespace: "landing.help" });
  const getting = t.raw("getting") as { title: string; text: string }[];
  const tasks = t.raw("tasks") as { title: string; text: string }[];

  return (
    <section className="pb-20">
      <Container className="max-w-4xl">
        <div className="rounded-2xl border border-border-default bg-surface p-6">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-accent-primary/10 text-accent-primary">
              <ListChecks className="h-5 w-5" aria-hidden="true" />
            </div>
            <h2 className="text-lg font-semibold text-text-primary">
              {t("gettingTitle")}
            </h2>
          </div>
          <ul className="mt-5 space-y-4">
            {getting.map((g) => (
              <li key={g.title} className="flex gap-3 text-sm">
                <CircleCheck
                  className="mt-0.5 h-5 w-5 shrink-0 text-accent-primary"
                  aria-hidden="true"
                />
                <span className="text-text-secondary">
                  <strong className="font-medium text-text-primary">
                    {g.title}.
                  </strong>{" "}
                  {g.text}
                </span>
              </li>
            ))}
          </ul>
        </div>

        <div className="mt-8">
          <h2 className="flex items-center gap-3 text-lg font-semibold text-text-primary">
            <MessageCircleQuestion
              className="h-5 w-5 text-accent-primary"
              aria-hidden="true"
            />
            {t("tasksTitle")}
          </h2>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            {tasks.map((task) => (
              <div
                key={task.title}
                className="rounded-2xl border border-border-default bg-surface p-5"
              >
                <h3 className="text-sm font-semibold text-text-primary">
                  {task.title}
                </h3>
                <p className="mt-2 text-sm leading-relaxed text-text-secondary">
                  {task.text}
                </p>
              </div>
            ))}
          </div>
        </div>

        <div className="mt-8 rounded-2xl border border-border-default bg-accent-primary/5 p-6">
          <h2 className="text-lg font-semibold text-text-primary">
            {t("supportTitle")}
          </h2>
          <p className="mt-2 text-sm leading-relaxed text-text-secondary">
            {t("supportText")}
          </p>
        </div>
      </Container>
    </section>
  );
}