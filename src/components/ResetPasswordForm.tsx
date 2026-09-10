"use client";

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useRouter } from "@/i18n/navigation";
import { Loader2, CheckCircle2 } from "lucide-react";
import { authApi, ApiError } from "@/lib/api";
import Button from "@/components/Button";

function ResetFormInner() {
  const t = useTranslations("auth");
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get("token") ?? "";

  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);
  const [fatal, setFatal] = useState<string | null>(null);

  const inputClass =
    "h-11 w-full rounded-xl border border-border-default bg-surface px-4 text-sm text-text-primary outline-none transition-colors placeholder:text-text-secondary/60 focus:border-accent-primary focus:ring-4 focus:ring-accent-primary/10";

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    if (password !== confirm) {
      setError(t("passwordsDontMatch"));
      return;
    }
    setLoading(true);
    try {
      await authApi.confirmPasswordReset(token, password);
      setDone(true);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setFatal(t("linkInvalid"));
      } else {
        setError(t("genericError"));
      }
    } finally {
      setLoading(false);
    }
  }

  if (fatal) {
    return (
      <div className="text-center">
        <p className="rounded-xl border border-error/30 bg-error/5 px-4 py-3 text-sm text-error">
          {fatal}
        </p>
        <Button variant="secondary" className="mt-6 w-full" onClick={() => router.push("/forgot-password")}>
          {t("requestNewLink")}
        </Button>
      </div>
    );
  }

  if (done) {
    return (
      <div className="text-center">
        <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-success/10">
          <CheckCircle2 className="h-7 w-7 text-success" aria-hidden="true" />
        </div>
        <h2 className="text-lg font-semibold text-text-primary">{t("resetSuccessTitle")}</h2>
        <p className="mx-auto mt-2 max-w-sm text-sm text-text-secondary">{t("resetSuccessBody")}</p>
        <Button className="mt-6 w-full" onClick={() => router.push("/login")}>
          {t("backToLogin")}
        </Button>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label htmlFor="password" className="mb-1.5 block text-sm font-medium text-text-primary">
          {t("password")}
        </label>
        <input
          id="password"
          type="password"
          autoComplete="new-password"
          required
          minLength={8}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder={t("passwordPlaceholder")}
          className={inputClass}
        />
        <p className="mt-1 text-xs text-text-secondary">{t("passwordHelp")}</p>
      </div>
      <div>
        <label htmlFor="confirm" className="mb-1.5 block text-sm font-medium text-text-primary">
          {t("confirmPassword")}
        </label>
        <input
          id="confirm"
          type="password"
          autoComplete="new-password"
          required
          minLength={8}
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          placeholder={t("passwordPlaceholder")}
          className={inputClass}
        />
      </div>

      {error && (
        <p role="alert" className="rounded-xl border border-error/30 bg-error/5 px-4 py-2.5 text-sm text-error">
          {error}
        </p>
      )}

      <Button type="submit" className="w-full" size="lg" disabled={loading || !token} aria-busy={loading}>
        {loading && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
        {t("resetPassword")}
      </Button>
    </form>
  );
}

export default function ResetPasswordForm() {
  return (
    <Suspense fallback={null}>
      <ResetFormInner />
    </Suspense>
  );
}