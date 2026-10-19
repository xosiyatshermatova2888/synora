"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { useRouter } from "@/i18n/routing";
import {
  PlanName,
  PlatformPaymentOut,
  PlatformRestaurantOut,
  platformApi,
} from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { formatDate, formatMoney, safeUrl } from "@/lib/format";
import Button from "@/components/Button";
import Modal from "@/components/Modal";
import PageHeader from "@/components/dashboard/PageHeader";
import StateView from "@/components/dashboard/StateView";
import Tabs from "@/components/ui/Tabs";
import ConfirmDialog from "@/components/ui/ConfirmDialog";
import { useToast } from "@/components/ui/Toast";

const PLANS: PlanName[] = ["BUSINESS", "PRO", "AI_PREMIUM", "ENTERPRISE"];
const ACCESS_TONE: Record<string, string> = {
  FULL: "bg-success/15 text-success",
  GRACE: "bg-warning/15 text-warning",
  READ_ONLY: "bg-error/15 text-error",
};
/** yyyy-mm-dd in the browser's own timezone (what the user sees in the table). */
function localDate(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

const field =
  "mt-1 w-full rounded-lg border border-border-default bg-background px-3 py-2 text-sm text-text-primary outline-none focus:border-accent-primary";

/** SYNORA owner console. The route is open to everyone who guesses it, but the
 * API refuses (403) anyone who isn't a platform admin, so there is no data to
 * leak — the redirect below just keeps the page tidy. */
export default function PlatformPage() {
  const { user, status } = useAuth();
  const router = useRouter();
  const allowed = !!user?.is_platform_admin;

  useEffect(() => {
    if (status === "authenticated" && !allowed) router.replace("/dashboard");
  }, [status, allowed, router]);

  if (!allowed) return <StateView kind="loading" />;
  return <PlatformConsole />;
}

function PlatformConsole() {
  const t = useTranslations("platformPage");
  const [tab, setTab] = useState("payments");

  return (
    <div>
      <PageHeader title={t("title")} description={t("description")} />
      <Tabs
        className="mb-5"
        value={tab}
        onChange={setTab}
        items={[
          { key: "payments", label: t("tabs.payments") },
          { key: "restaurants", label: t("tabs.restaurants") },
        ]}
      />
      {tab === "payments" ? <PaymentsTab /> : <RestaurantsTab />}
    </div>
  );
}

function PaymentsTab() {
  const t = useTranslations("platformPage.payments");
  const ts = useTranslations("subscription");
  const toast = useToast();
  const [rows, setRows] = useState<PlatformPaymentOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [approving, setApproving] = useState<PlatformPaymentOut | null>(null);
  const [rejecting, setRejecting] = useState<PlatformPaymentOut | null>(null);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setRows(await platformApi.payments());
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const act = async (fn: () => Promise<unknown>, okMessage: string) => {
    setBusy(true);
    try {
      await fn();
      toast.success(okMessage);
      setApproving(null);
      setRejecting(null);
      setReason("");
      await load();
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  if (error) return <StateView kind="error" message={error} onRetry={() => void load()} />;
  if (!rows) return <StateView kind="loading" />;

  const pending = rows.filter((r) => r.status === "PENDING");
  const decided = rows.filter((r) => r.status !== "PENDING").slice(0, 10);

  return (
    <div className="space-y-6">
      <section>
        <h2 className="mb-3 text-base font-semibold text-text-primary">{t("pending")}</h2>
        {pending.length === 0 ? (
          <p className="rounded-xl border border-border-default bg-surface py-8 text-center text-sm text-text-secondary">
            {t("none")}
          </p>
        ) : (
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {pending.map((p) => (
              <div key={p.id} className="flex gap-4 rounded-xl border border-border-default bg-surface p-4">
                {safeUrl(p.receipt_url) ? (
                  <a href={safeUrl(p.receipt_url)!} target="_blank" rel="noreferrer" title={t("receipt")} className="shrink-0">
                    {/* eslint-disable-next-line @next/next/no-img-element -- receipts live on the configured object store */}
                    <img src={safeUrl(p.receipt_url)!} alt="" className="h-28 w-24 rounded-lg border border-border-default object-cover" />
                  </a>
                ) : (
                  <div className="flex h-28 w-24 shrink-0 items-center justify-center rounded-lg border border-dashed border-border-default p-2 text-center text-xs text-text-secondary">
                    {t("noReceipt")}
                  </div>
                )}
                <div className="flex min-w-0 flex-1 flex-col">
                  <p className="truncate font-semibold text-text-primary">{p.restaurant_name}</p>
                  <p className="text-sm text-text-secondary">
                    {ts(`plans.name.${p.plan}`)} · {ts(`history.cycle.${p.billing_cycle}`)}
                  </p>
                  <p className="mt-1 text-lg font-bold text-text-primary">{formatMoney(p.amount, p.currency)}</p>
                  <p className="text-xs text-text-secondary">{formatDate(p.created_at)}</p>
                  <div className="mt-auto flex gap-2 pt-3">
                    <Button size="sm" onClick={() => setApproving(p)} disabled={!safeUrl(p.receipt_url)}>
                      {t("approve")}
                    </Button>
                    <Button size="sm" variant="secondary" onClick={() => setRejecting(p)}>
                      {t("reject")}
                    </Button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {decided.length > 0 && (
        <section>
          <h2 className="mb-3 text-base font-semibold text-text-primary">{t("history")}</h2>
          <ul className="divide-y divide-border-default rounded-xl border border-border-default bg-surface">
            {decided.map((p) => (
              <li key={p.id} className="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3 text-sm">
                <span className="min-w-0 flex-1 truncate font-medium text-text-primary">{p.restaurant_name}</span>
                <span className="text-text-secondary">{ts(`plans.name.${p.plan}`)}</span>
                <span className="font-semibold text-text-primary">{formatMoney(p.amount, p.currency)}</span>
                <span
                  className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                    p.status === "APPROVED" ? "bg-success/15 text-success" : "bg-error/15 text-error"
                  }`}
                >
                  {ts(`history.status.${p.status}`)}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <ConfirmDialog
        open={approving !== null}
        tone="primary"
        loading={busy}
        title={t("approve")}
        message={
          approving
            ? t("confirmApprove", {
                restaurant: approving.restaurant_name,
                amount: new Intl.NumberFormat("ru-RU").format(Number(approving.amount)),
              })
            : undefined
        }
        confirmLabel={t("approve")}
        onClose={() => setApproving(null)}
        onConfirm={() => approving && void act(() => platformApi.approve(approving.id), t("approved"))}
      />

      <Modal open={rejecting !== null} onClose={() => setRejecting(null)} title={t("rejectTitle")}>
        <label className="block text-sm font-medium text-text-primary">
          {t("rejectReason")}
          <input value={reason} onChange={(e) => setReason(e.target.value)} maxLength={300} className={field} />
        </label>
        <div className="mt-5 flex justify-end gap-2">
          <Button variant="ghost" onClick={() => setRejecting(null)}>
            {ts("checkout.cancel")}
          </Button>
          <Button
            variant="danger"
            loading={busy}
            onClick={() => rejecting && void act(() => platformApi.reject(rejecting.id, reason.trim()), t("rejected"))}
          >
            {t("reject")}
          </Button>
        </div>
      </Modal>
    </div>
  );
}

function RestaurantsTab() {
  const t = useTranslations("platformPage.restaurants");
  const ts = useTranslations("subscription");
  const toast = useToast();
  const [rows, setRows] = useState<PlatformRestaurantOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<PlatformRestaurantOut | null>(null);
  const [plan, setPlan] = useState<PlanName>("BUSINESS");
  const [subStatus, setSubStatus] = useState<"TRIAL" | "ACTIVE">("ACTIVE");
  const [endDate, setEndDate] = useState("");
  const [noExpiry, setNoExpiry] = useState(false);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      setRows(await platformApi.restaurants());
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const open = (r: PlatformRestaurantOut) => {
    setEditing(r);
    setPlan(r.plan);
    setSubStatus(r.status);
    setEndDate(r.ends_at ? localDate(new Date(r.ends_at)) : "");
    setNoExpiry(!r.ends_at);
  };

  const extend30 = () => {
    const base = endDate && new Date(endDate) > new Date() ? new Date(endDate) : new Date();
    base.setDate(base.getDate() + 30);
    setEndDate(localDate(base));
    setNoExpiry(false);
  };

  const save = async () => {
    if (!editing) return;
    setSaving(true);
    try {
      await platformApi.override(editing.id, {
        plan,
        status: subStatus,
        ...(noExpiry || !endDate
          ? { clear_period_end: true }
          : { period_end: new Date(`${endDate}T23:59:59`).toISOString() }),
      });
      toast.success(t("saved"));
      setEditing(null);
      await load();
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setSaving(false);
    }
  };

  if (error) return <StateView kind="error" message={error} onRetry={() => void load()} />;
  if (!rows) return <StateView kind="loading" />;
  if (rows.length === 0) return <StateView kind="empty" message={t("empty")} />;

  return (
    <>
      <div className="overflow-x-auto rounded-xl border border-border-default bg-surface">
        <table className="w-full min-w-[640px] text-left text-sm">
          <thead className="border-b border-border-default text-xs uppercase tracking-wide text-text-secondary">
            <tr>
              <th className="px-4 py-3 font-semibold">{t("name")}</th>
              <th className="px-4 py-3 font-semibold">{t("plan")}</th>
              <th className="px-4 py-3 font-semibold">{t("status")}</th>
              <th className="px-4 py-3 font-semibold">{t("until")}</th>
              <th className="px-4 py-3 font-semibold">{t("access")}</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody className="divide-y divide-border-default">
            {rows.map((r) => (
              <tr key={r.id}>
                <td className="px-4 py-3 font-medium text-text-primary">{r.name}</td>
                <td className="px-4 py-3 text-text-secondary">{ts(`plans.name.${r.effective_plan}`)}</td>
                <td className="px-4 py-3 text-text-secondary">{ts(`current.${r.status}`)}</td>
                <td className="px-4 py-3 text-text-secondary">{r.ends_at ? formatDate(r.ends_at) : t("noExpiry")}</td>
                <td className="px-4 py-3">
                  <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${ACCESS_TONE[r.access]}`}>
                    {ts(`current.access.${r.access}`)}
                  </span>
                </td>
                <td className="px-4 py-3 text-right">
                  <Button size="sm" variant="secondary" onClick={() => open(r)}>
                    {t("edit")}
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Modal open={editing !== null} onClose={() => setEditing(null)} title={t("editTitle")}>
        {editing && (
          <div className="space-y-3">
            <p className="font-semibold text-text-primary">{editing.name}</p>
            <div className="grid grid-cols-2 gap-3">
              <label className="block text-sm font-medium text-text-primary">
                {t("plan")}
                <select value={plan} onChange={(e) => setPlan(e.target.value as PlanName)} className={field}>
                  {PLANS.map((p) => (
                    <option key={p} value={p}>
                      {ts(`plans.name.${p}`)}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block text-sm font-medium text-text-primary">
                {t("status")}
                <select value={subStatus} onChange={(e) => setSubStatus(e.target.value as "TRIAL" | "ACTIVE")} className={field}>
                  <option value="ACTIVE">{ts("current.ACTIVE")}</option>
                  <option value="TRIAL">{ts("current.TRIAL")}</option>
                </select>
              </label>
            </div>
            <label className="block text-sm font-medium text-text-primary">
              {t("date")}
              <input
                type="date"
                value={endDate}
                disabled={noExpiry}
                onChange={(e) => setEndDate(e.target.value)}
                className={field}
              />
            </label>
            <div className="flex flex-wrap items-center gap-4">
              <label className="flex items-center gap-2 text-sm text-text-primary">
                <input type="checkbox" checked={noExpiry} onChange={(e) => setNoExpiry(e.target.checked)} />
                {t("noExpiry")}
              </label>
              <Button size="sm" variant="secondary" onClick={extend30}>
                {t("extend30")}
              </Button>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="ghost" onClick={() => setEditing(null)}>
                {ts("checkout.cancel")}
              </Button>
              <Button loading={saving} onClick={() => void save()}>
                {t("save")}
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </>
  );
}
