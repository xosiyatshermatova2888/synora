import { getTranslations } from "next-intl/server";
import Container from "@/components/Container";

function MethodBadge({ method }: { method: string }) {
  const colors: Record<string, string> = {
    GET: "bg-emerald-500/10 text-emerald-500",
    POST: "bg-sky-500/10 text-sky-500",
    PATCH: "bg-amber-500/10 text-amber-500",
    DELETE: "bg-rose-500/10 text-rose-500",
    WS: "bg-violet-500/10 text-violet-500",
  };
  return (
    <span
      className={`inline-flex w-14 shrink-0 justify-center rounded-md px-2 py-0.5 text-xs font-semibold ${
        colors[method] ?? "bg-text-secondary/10 text-text-secondary"
      }`}
    >
      {method}
    </span>
  );
}

export default async function DocsContent({ locale }: { locale: string }) {
  const t = await getTranslations({ locale, namespace: "landing.docs" });
  const groups = t.raw("groups") as {
    group: string;
    items: { method: string; path: string; note: string }[];
  }[];
  const wsEvents = t.raw("wsEvents") as { event: string; note: string }[];

  return (
    <section className="pb-20">
      <Container className="max-w-4xl">
        <h2 className="text-2xl font-semibold text-text-primary">
          {t("introTitle")}
        </h2>
        <p className="mt-3 leading-relaxed text-text-secondary">
          {t("introText")}
        </p>

        <div className="mt-10 rounded-2xl border border-border-default bg-surface p-6">
          <h3 className="text-lg font-semibold text-text-primary">
            {t("baseTitle")}
          </h3>
          <p className="mt-2 text-sm text-text-secondary">{t("baseText")}</p>
          <pre className="mt-4 overflow-x-auto rounded-xl bg-accent-primary/5 p-4 text-sm text-text-primary">
            {t("baseCode")}
          </pre>
        </div>

        <div className="mt-8 rounded-2xl border border-border-default bg-surface p-6">
          <h3 className="text-lg font-semibold text-text-primary">
            {t("authTitle")}
          </h3>
          <p className="mt-2 text-sm text-text-secondary">{t("authText")}</p>
          <ol className="mt-4 space-y-3">
            {(t.raw("authSteps") as { title: string; text: string }[]).map(
              (s, i) => (
                <li key={s.title} className="flex gap-3 text-sm">
                  <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-accent-primary/10 text-xs font-semibold text-accent-primary">
                    {i + 1}
                  </span>
                  <span className="text-text-secondary">
                    <strong className="font-medium text-text-primary">
                      {s.title}.
                    </strong>{" "}
                    {s.text}
                  </span>
                </li>
              ),
            )}
          </ol>
        </div>

        <div className="mt-8">
          <h3 className="text-lg font-semibold text-text-primary">
            {t("endpointsTitle")}
          </h3>
          <p className="mt-2 text-sm text-text-secondary">
            {t("endpointsText")}
          </p>
          <div className="mt-4 space-y-6">
            {groups.map((g) => (
              <div
                key={g.group}
                className="overflow-hidden rounded-2xl border border-border-default"
              >
                <div className="border-b border-border-default bg-surface px-5 py-3 text-sm font-semibold text-text-primary">
                  {g.group}
                </div>
                <ul className="divide-y divide-border-default bg-surface/50">
                  {g.items.map((item) => (
                    <li
                      key={`${item.method}-${item.path}`}
                      className="flex items-center gap-3 px-5 py-3 text-sm"
                    >
                      <MethodBadge method={item.method} />
                      <code className="font-mono text-[13px] text-accent-ai">
                        {item.path}
                      </code>
                      <span className="ml-auto hidden text-right text-xs text-text-secondary sm:block">
                        {item.note}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>

        <div className="mt-8 rounded-2xl border border-border-default bg-surface p-6">
          <h3 className="text-lg font-semibold text-text-primary">
            {t("wsTitle")}
          </h3>
          <p className="mt-2 text-sm text-text-secondary">{t("wsText")}</p>
          <pre className="mt-4 overflow-x-auto rounded-xl bg-accent-primary/5 p-4 text-sm text-text-primary">
            {t("wsCode")}
          </pre>
          <div className="mt-4 flex flex-wrap gap-2">
            {wsEvents.map((e) => (
              <span
                key={e.event}
                className="rounded-lg border border-border-default bg-surface px-3 py-1.5 text-xs text-text-secondary"
                title={e.note}
              >
                <code className="font-mono text-accent-ai">{e.event}</code>
              </span>
            ))}
          </div>
        </div>

        <div className="mt-8 rounded-2xl border border-border-default bg-surface p-6">
          <h3 className="text-lg font-semibold text-text-primary">
            {t("securityTitle")}
          </h3>
          <p className="mt-2 text-sm leading-relaxed text-text-secondary">
            {t("securityText")}
          </p>
          <p className="mt-4 rounded-xl bg-accent-primary/5 p-4 text-sm text-text-secondary">
            {t("swaggerText")}
          </p>
          <p className="mt-3 text-sm text-text-secondary">{t("swaggerNote")}</p>
        </div>
      </Container>
    </section>
  );
}