"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Delete, Loader2, ChevronLeft } from "lucide-react";
import { authApi, ApiError, WaiterBranchOut, WaiterDirectoryEntry } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

const PIN_LENGTH = 4;

type Step =
  | { name: "loading" }
  | { name: "unconfigured" }
  | { name: "pick-branch"; branches: WaiterBranchOut[] }
  | { name: "pick-name"; branch: WaiterBranchOut; people: WaiterDirectoryEntry[] }
  | { name: "enter-pin"; branch: WaiterBranchOut; person: WaiterDirectoryEntry };

export default function WaiterPinLogin() {
  const t = useTranslations("waiterPage.pinLogin");
  const { pinLogin, login } = useAuth();
  const [step, setStep] = useState<Step>({ name: "loading" });
  const [pin, setPin] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [mode, setMode] = useState<"pin" | "password">("pin");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  async function submitPassword(e: React.FormEvent) {
    e.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      await login(username.trim(), password);
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 429
          ? t("tooManyAttempts")
          : t("wrongCredentials")
      );
    } finally {
      setSubmitting(false);
    }
  }

  const passwordToggle = (
    <button
      type="button"
      onClick={() => {
        setError(null);
        setMode("password");
      }}
      className="text-sm font-medium text-accent-primary hover:opacity-80"
    >
      {t("usePassword")}
    </button>
  );

  useEffect(() => {
    void (async () => {
      try {
        const branches = await authApi.waiterBranches();
        if (branches.length === 0) {
          setStep({ name: "unconfigured" });
        } else if (branches.length === 1) {
          await openBranch(branches[0]);
        } else {
          setStep({ name: "pick-branch", branches });
        }
      } catch {
        setStep({ name: "unconfigured" });
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function openBranch(branch: WaiterBranchOut) {
    try {
      const people = await authApi.waiterDirectory(branch.id);
      setStep({ name: "pick-name", branch, people });
    } catch {
      setStep({ name: "unconfigured" });
    }
  }

  function pickPerson(branch: WaiterBranchOut, person: WaiterDirectoryEntry) {
    setPin("");
    setError(null);
    setStep({ name: "enter-pin", branch, person });
  }

  async function submitPin(fullPin: string) {
    if (step.name !== "enter-pin") return;
    setSubmitting(true);
    setError(null);
    try {
      await pinLogin(step.branch.id, step.person.id, fullPin);
    } catch (err) {
      setPin("");
      setError(
        err instanceof ApiError && err.status === 429
          ? t("tooManyAttempts")
          : t("wrongPin")
      );
    } finally {
      setSubmitting(false);
    }
  }

  // Functional updates only: rapid taps can fire several pressDigit calls
  // within one React batch, and reading `pin` from the closure there would
  // make each call start from the same stale value and drop digits.
  function pressDigit(d: string) {
    if (submitting) return;
    setError(null);
    setPin((prev) => (prev.length >= PIN_LENGTH ? prev : prev + d));
  }

  function pressBackspace() {
    if (submitting) return;
    setPin((prev) => prev.slice(0, -1));
  }

  useEffect(() => {
    if (pin.length === PIN_LENGTH) void submitPin(pin);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pin]);

  if (step.name === "loading") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <Loader2 className="h-8 w-8 animate-spin text-accent-primary" />
      </div>
    );
  }

  if (mode === "password") {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-5 bg-background px-6 py-10">
        <form onSubmit={submitPassword} className="flex w-full max-w-sm flex-col gap-4">
          <div>
            <label className="mb-1 block text-sm font-medium text-text-primary">
              {t("loginLabel")}
            </label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoCapitalize="none"
              autoCorrect="off"
              autoComplete="username"
              required
              className="w-full rounded-lg border border-border-default bg-surface px-3 py-3 text-base text-text-primary outline-none focus:border-accent-primary"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-text-primary">
              {t("passwordLabel")}
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              required
              className="w-full rounded-lg border border-border-default bg-surface px-3 py-3 text-base text-text-primary outline-none focus:border-accent-primary"
            />
          </div>
          {error && (
            <p role="alert" className="text-sm text-error">
              {error}
            </p>
          )}
          <button
            type="submit"
            disabled={submitting}
            className="flex items-center justify-center gap-2 rounded-lg bg-accent-primary px-4 py-3 text-base font-medium text-white disabled:opacity-50"
          >
            {submitting && <Loader2 className="h-4 w-4 animate-spin" />}
            {t("submitLogin")}
          </button>
        </form>
        <button
          type="button"
          onClick={() => {
            setError(null);
            setMode("pin");
          }}
          className="text-sm font-medium text-accent-primary hover:opacity-80"
        >
          {t("usePin")}
        </button>
      </div>
    );
  }

  if (step.name === "unconfigured") {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-background px-6 text-center">
        <p className="text-sm font-medium text-text-primary">{t("notConfigured")}</p>
        {passwordToggle}
      </div>
    );
  }

  if (step.name === "pick-branch") {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-background px-6">
        <h1 className="text-lg font-semibold text-text-primary">{t("chooseBranch")}</h1>
        <div className="flex w-full max-w-sm flex-col gap-2">
          {step.branches.map((b) => (
            <button
              key={b.id}
              onClick={() => void openBranch(b)}
              className="rounded-xl border border-border-default bg-surface px-4 py-3 text-left text-sm font-medium text-text-primary shadow-sm transition-colors hover:border-accent-primary"
            >
              {b.restaurant_name} — {b.name}
            </button>
          ))}
        </div>
        {passwordToggle}
      </div>
    );
  }

  if (step.name === "pick-name") {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-background px-6 py-10">
        <h1 className="text-lg font-semibold text-text-primary">{t("chooseName")}</h1>
        {step.people.length === 0 ? (
          <p className="max-w-sm text-center text-sm text-text-secondary">{t("noNames")}</p>
        ) : (
          <div className="grid w-full max-w-sm grid-cols-2 gap-3">
            {step.people.map((p) => (
              <button
                key={p.id}
                onClick={() => pickPerson(step.branch, p)}
                className="flex flex-col items-center gap-2 rounded-xl border border-border-default bg-surface px-3 py-4 text-center shadow-sm transition-colors hover:border-accent-primary"
              >
                <div className="flex h-12 w-12 items-center justify-center rounded-full bg-brand-gradient text-base font-bold text-white">
                  {p.full_name.charAt(0).toUpperCase()}
                </div>
                <span className="line-clamp-2 text-sm font-medium text-text-primary">
                  {p.full_name}
                </span>
              </button>
            ))}
          </div>
        )}
        {passwordToggle}
      </div>
    );
  }

  // step.name === "enter-pin"
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 bg-background px-6 py-10">
      <button
        onClick={() => void openBranch(step.branch)}
        className="flex items-center gap-1 self-start text-sm text-text-secondary hover:text-text-primary"
      >
        <ChevronLeft className="h-4 w-4" />
        {t("back")}
      </button>

      <div className="flex flex-col items-center gap-2">
        <div className="flex h-16 w-16 items-center justify-center rounded-full bg-brand-gradient text-xl font-bold text-white">
          {step.person.full_name.charAt(0).toUpperCase()}
        </div>
        <p className="text-base font-semibold text-text-primary">{step.person.full_name}</p>
        <p className="text-sm text-text-secondary">{t("enterPin")}</p>
      </div>

      <div className="flex gap-3" aria-hidden="true">
        {Array.from({ length: PIN_LENGTH }).map((_, i) => (
          <span
            key={i}
            className={`h-3.5 w-3.5 rounded-full border-2 ${
              i < pin.length
                ? "border-accent-primary bg-accent-primary"
                : "border-border-default bg-transparent"
            }`}
          />
        ))}
      </div>

      {submitting && <Loader2 className="h-5 w-5 animate-spin text-accent-primary" />}
      {error && (
        <p role="alert" className="text-sm text-error">
          {error}
        </p>
      )}

      <div className="grid grid-cols-3 gap-4">
        {["1", "2", "3", "4", "5", "6", "7", "8", "9"].map((d) => (
          <button
            key={d}
            type="button"
            disabled={submitting}
            onClick={() => pressDigit(d)}
            className="flex h-16 w-16 items-center justify-center rounded-full border border-border-default bg-surface text-xl font-semibold text-text-primary shadow-sm transition-colors hover:border-accent-primary disabled:opacity-50"
          >
            {d}
          </button>
        ))}
        <div />
        <button
          type="button"
          disabled={submitting}
          onClick={() => pressDigit("0")}
          className="flex h-16 w-16 items-center justify-center rounded-full border border-border-default bg-surface text-xl font-semibold text-text-primary shadow-sm transition-colors hover:border-accent-primary disabled:opacity-50"
        >
          0
        </button>
        <button
          type="button"
          disabled={submitting}
          onClick={pressBackspace}
          aria-label={t("back")}
          className="flex h-16 w-16 items-center justify-center rounded-full text-text-secondary transition-colors hover:text-text-primary disabled:opacity-50"
        >
          <Delete className="h-5 w-5" />
        </button>
      </div>
    </div>
  );
}
