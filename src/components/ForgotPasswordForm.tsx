"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { useRouter } from "@/i18n/navigation";
import { Loader2, MailCheck, ArrowLeft } from "lucide-react";
import { authApi, ApiError } from "@/lib/api";
import Button from "@/components/Button";

export default function ForgotPasswordForm() {
  const t = useTranslations("auth");
  const router = useRouter();

  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      // Always 202 (existing or unknown address) — no account disclosure.
      await authApi.requestPasswordReset(email);
      setSent(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : t("genericError"));
    } finally {
      setLoading(false);
    }
  }

  const inputClass =
    "h-11 w-full rounded-xl border border-border-default bg-surface px-4 text-sm text-text-primary outline-none transition-colors placeholder:text-text-secondary/60 focus:border-accent-primary focus:ring-4 focus:ring-accent-primary/10";

  if (sent) {
    return (
      <div className="text-center">
        <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-success/10">
          <MailCheck className="h-7 w-7 text-success" aria-hidden="true" />
        </div>
        <h2 className="text-lg font-semibold text-text-primary">{t("emailSentTitle")}</h2>
        <p className="mx-auto mt-2 max-w-sm text-sm text-text-secondary">
          {t("emailSentBody")}
        </p>
        <Button
          variant="secondary"
          className="mt-6 w-full"
          onClick={() => router.push("/login")}
        >
          {t("backToLogin")}
        </Button>
      </div>
    );
  }

  return (
    <div>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label htmlFor="email" className="mb-1.5 block text-sm font-medium text-text-primary">
            {t("email")}
          </label>
          <input
            id="email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder={t("emailPlaceholder")}
            className={inputClass}
          />
        </div>

        {error && (
          <p role="alert" className="rounded-xl border border-error/30 bg-error/5 px-4 py-2.5 text-sm text-error">
            {error}
          </p>
        )}

        <Button type="submit" className="w-full" size="lg" disabled={loading} aria-busy={loading}>
          {loading && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
          {t("sendResetLink")}
        </Button>
      </form>

      <Link
        href="/login"
        className="mt-6 flex items-center justify-center gap-1.5 text-sm text-text-secondary transition-colors hover:text-text-primary"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden="true" />
        {t("backToLogin")}
      </Link>
    </div>
  );
}