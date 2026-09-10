"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { CheckCircle2, Loader2 } from "lucide-react";

type Field = {
  name: string;
  type?: string;
  optional?: boolean;
};

export default function LeadForm({
  fields,
  submitKey,
}: {
  fields: Field[];
  submitKey: "submit" | "contactSubmit";
}) {
  const t = useTranslations("form");
  const [values, setValues] = useState<Record<string, string>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  const validate = () => {
    const next: Record<string, string> = {};
    for (const f of fields) {
      const val = (values[f.name] || "").trim();
      if (!f.optional && !val) {
        next[f.name] = t("required");
      }
      if (f.type === "email" && val && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(val)) {
        next[f.name] = t("emailInvalid");
      }
    }
    setErrors(next);
    return Object.keys(next).length === 0;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;
    // Placeholder handler — collect lead and show a static success state.
    // Replace with a real API route / CRM when available.
    setSubmitting(true);
    setTimeout(() => {
      setSubmitting(false);
      setDone(true);
    }, 600);
  };

  if (done) {
    return (
      <div className="flex flex-col items-center gap-3 py-6 text-center">
        <CheckCircle2 className="h-12 w-12 text-success" />
        <p className="text-lg font-semibold">{t("successTitle")}</p>
        <p className="text-sm text-text-secondary">{t("successText")}</p>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-4">
      {fields.map((f) => (
        <div key={f.name}>
          <label
            htmlFor={f.name}
            className="mb-1.5 block text-sm font-medium text-text-primary"
          >
            {t(f.name)}
          </label>
          <input
            id={f.name}
            name={f.name}
            type={f.type || "text"}
            value={values[f.name] || ""}
            onChange={(e) =>
              setValues((v) => ({ ...v, [f.name]: e.target.value }))
            }
            placeholder={t(`${f.name}Placeholder`)}
            aria-invalid={!!errors[f.name]}
            className="w-full rounded-xl border border-border-default bg-surface px-4 py-3 text-sm text-text-primary placeholder:text-text-secondary/60 transition-colors focus:border-accent-primary focus:outline-none focus:ring-2 focus:ring-accent-primary/30"
          />
          {errors[f.name] && (
            <p className="mt-1 text-xs text-error">{errors[f.name]}</p>
          )}
        </div>
      ))}
      <button
        type="submit"
        disabled={submitting}
        className="flex h-11 w-full items-center justify-center gap-2 rounded-xl bg-accent-primary font-medium text-white transition-all duration-200 hover:brightness-110 disabled:opacity-60"
      >
        {submitting ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          t(submitKey)
        )}
      </button>
    </form>
  );
}
