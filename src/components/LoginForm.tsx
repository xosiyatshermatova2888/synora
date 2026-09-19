"use client";

import { Suspense, useState } from "react";
import { useTranslations } from "next-intl";
import { useSearchParams } from "next/navigation";
import { useRouter } from "@/i18n/navigation";
import { Loader2 } from "lucide-react";
import { authApi, ApiError, setAccessToken } from "@/lib/api";
import Button from "@/components/Button";

type Mode = "login" | "register";

function LoginFormInner() {
  const t = useTranslations("auth");
  const router = useRouter();
  const searchParams = useSearchParams();
  const next = searchParams.get("next");
  const redirectTo = next && next.startsWith("/") && !next.startsWith("//") ? next : "/dashboard";

  const [mode, setMode] = useState<Mode>("login");
  const [fullName, setFullName] = useState("");
  const [restaurantName, setRestaurantName] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const token =
        mode === "login"
          ? await authApi.login(username, password)
          : await authApi.register({
              full_name: fullName,
              username,
              password,
              restaurant_name: restaurantName,
            });
      setAccessToken(token.access_token);
      router.push(redirectTo);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 401) setError(t("invalidCredentials"));
        else if ((err.status === 409 || err.status === 422) && mode === "register")
          setError(t("registerFailed"));
        else setError(t("genericError"));
      } else {
        setError(t("genericError"));
      }
    } finally {
      setLoading(false);
    }
  }

  const switchMode = (next: Mode) => {
    setMode(next);
    setError(null);
  };

  const inputClass =
    "h-11 w-full rounded-xl border border-border-default bg-surface px-4 text-sm text-text-primary outline-none transition-colors placeholder:text-text-secondary/60 focus:border-accent-primary focus:ring-4 focus:ring-accent-primary/10";

  return (
    <div className="w-full">
      <div className="mb-6 grid grid-cols-2 gap-1 rounded-xl border border-border-default bg-background-secondary/60 p-1">
        <button
          type="button"
          onClick={() => switchMode("login")}
          className={`h-10 rounded-lg text-sm font-medium transition-colors ${
            mode === "login"
              ? "bg-surface text-text-primary shadow-sm"
              : "text-text-secondary hover:text-text-primary"
          }`}
        >
          {t("loginTab")}
        </button>
        <button
          type="button"
          onClick={() => switchMode("register")}
          className={`h-10 rounded-lg text-sm font-medium transition-colors ${
            mode === "register"
              ? "bg-surface text-text-primary shadow-sm"
              : "text-text-secondary hover:text-text-primary"
          }`}
        >
          {t("registerTab")}
        </button>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        {mode === "register" && (
          <>
            <div>
              <label
                htmlFor="fullName"
                className="mb-1.5 block text-sm font-medium text-text-primary"
              >
                {t("fullName")}
              </label>
              <input
                id="fullName"
                type="text"
                autoComplete="name"
                required
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder={t("fullNamePlaceholder")}
                className={inputClass}
              />
            </div>
            <div>
              <label
                htmlFor="restaurantName"
                className="mb-1.5 block text-sm font-medium text-text-primary"
              >
                {t("restaurantName")}
              </label>
              <input
                id="restaurantName"
                type="text"
                autoComplete="organization"
                required
                minLength={2}
                value={restaurantName}
                onChange={(e) => setRestaurantName(e.target.value)}
                placeholder={t("restaurantNamePlaceholder")}
                className={inputClass}
              />
              <p className="mt-1 text-xs text-text-secondary">{t("restaurantHelp")}</p>
            </div>
          </>
        )}

        <div>
          <label htmlFor="username" className="mb-1.5 block text-sm font-medium text-text-primary">
            {t("username")}
          </label>
          <input
            id="username"
            type="text"
            autoComplete="username"
            required
            minLength={3}
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder={t("usernamePlaceholder")}
            className={inputClass}
          />
        </div>

        <div>
          <label htmlFor="password" className="mb-1.5 block text-sm font-medium text-text-primary">
            {t("password")}
          </label>
          <input
            id="password"
            type="password"
            autoComplete={mode === "login" ? "current-password" : "new-password"}
            required
            minLength={mode === "register" ? 8 : undefined}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder={t("passwordPlaceholder")}
            className={inputClass}
          />
          {mode === "register" && (
            <p className="mt-1 text-xs text-text-secondary">{t("passwordHelp")}</p>
          )}
        </div>

        {error && (
          <p
            role="alert"
            className="rounded-xl border border-error/30 bg-error/5 px-4 py-2.5 text-sm text-error"
          >
            {error}
          </p>
        )}

        <Button
          type="submit"
          className="w-full"
          size="lg"
          disabled={loading}
          aria-busy={loading}
        >
          {loading && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
          {mode === "login" ? t("signIn") : t("createAccount")}
        </Button>
      </form>

      <p className="mt-6 text-center text-sm text-text-secondary">
        {mode === "login" ? t("newHere") : t("haveAccount")}{" "}
        <button
          type="button"
          onClick={() => switchMode(mode === "login" ? "register" : "login")}
          className="font-medium text-accent-primary hover:underline"
        >
          {mode === "login" ? t("registerTab") : t("loginTab")}
        </button>
      </p>
    </div>
  );
}

export default function LoginForm() {
  return (
    <Suspense fallback={null}>
      <LoginFormInner />
    </Suspense>
  );
}