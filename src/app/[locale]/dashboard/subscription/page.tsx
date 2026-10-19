"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Check, Copy, Clock, Gem } from "lucide-react";
import {
  BillingCycle,
  PlanInfo,
  PlanName,
  PlansOut,
  SubscriptionPaymentOut,
  subscriptionApi,
} from "@/lib/api";
import { formatDate, formatMoney, safeUrl } from "@/lib/format";
import { useSubscription } from "@/lib/subscription-context";
import Button from "@/components/Button";
import Modal from "@/components/Modal";
import ImageUploadField from "@/components/ImageUploadField";
import PageHeader from "@/components/dashboard/PageHeader";
import StateView from "@/components/dashboard/StateView";
import { useToast } from "@/components/ui/Toast";

const PLAN_ORDER: PlanName[] = ["BUSINESS", "PRO", "AI_PREMIUM", "ENTERPRISE"];
const RANK: Record<PlanName, number> = { BUSINESS: 0, PRO: 1, AI_PREMIUM: 2, ENTERPRISE: 3 };

const STATUS_TONE: Record<SubscriptionPaymentOut["status"], string> = {
  PENDING: "bg-warning/15 text-warning",
  APPROVED: "bg-success/15 text-success",
  REJECTED: "bg-error/15 text-error",
};

interface Checkout {
  plan: PlanName;
  cycle: BillingCycle;
  amount: number;
  /** Set when resuming a request that exists but has no receipt yet. */
  payment: SubscriptionPaymentOut | null;
}

function priceOf(info: PlanInfo, cycle: BillingCycle): number | null {
  return cycle === "ANNUAL" ? info.annual_price : info.monthly_price;
}

export default function SubscriptionPage() {
  const t = useTranslations("subscription");
  const toast = useToast();
  const { subscription, refresh } = useSubscription();

  const [plans, setPlans] = useState<PlansOut | null>(null);
  const [payments, setPayments] = useState<SubscriptionPaymentOut[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [cycle, setCycle] = useState<BillingCycle>("MONTHLY");
  const [checkout, setCheckout] = useState<Checkout | null>(null);

  const load = useCallback(async () => {
    try {
      const [p, pay] = await Promise.all([subscriptionApi.plans(), subscriptionApi.payments()]);
      setPlans(p);
      setPayments(pay);
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (error) return <StateView kind="error" message={error} onRetry={() => void load()} />;
  if (!plans || !subscription) return <StateView kind="loading" />;

  const pending = payments.find((p) => p.status === "PENDING") ?? null;
  const awaitingReceipt = pending && !pending.receipt_url ? pending : null;
  const awaitingReview = pending && pending.receipt_url ? pending : null;

  const openCheckout = (info: PlanInfo) => {
    const amount = priceOf(info, cycle);
    if (amount === null) return;
    setCheckout({ plan: info.plan, cycle, amount, payment: null });
  };

  const resume = (p: SubscriptionPaymentOut) =>
    setCheckout({ plan: p.plan, cycle: p.billing_cycle, amount: Number(p.amount), payment: p });

  const done = async () => {
    setCheckout(null);
    await Promise.all([load(), refresh()]);
  };

  return (
    <div>
      <PageHeader title={t("title")} description={t("description")} />

      <CurrentCard />

      {awaitingReview && (
        <div className="mb-6 flex items-start gap-3 rounded-xl border border-warning/40 bg-warning/10 p-4 text-sm text-text-primary">
          <Clock className="mt-0.5 h-4 w-4 shrink-0 text-warning" aria-hidden="true" />
          <span>
            {t("plans.name." + awaitingReview.plan)} · {formatMoney(awaitingReview.amount, "UZS")} — {t("checkout.pending")}
          </span>
        </div>
      )}
      {awaitingReceipt && (
        <div className="mb-6 flex flex-wrap items-center gap-3 rounded-xl border border-warning/40 bg-warning/10 p-4 text-sm text-text-primary">
          <Clock className="h-4 w-4 shrink-0 text-warning" aria-hidden="true" />
          <span className="flex-1">
            {t("plans.name." + awaitingReceipt.plan)} · {formatMoney(awaitingReceipt.amount, "UZS")} — {t("checkout.uploadFirst")}
          </span>
          <Button size="sm" onClick={() => resume(awaitingReceipt)}>
            {t("checkout.submit")}
          </Button>
        </div>
      )}

      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-base font-semibold text-text-primary">{t("plans.title")}</h2>
        <div className="inline-flex rounded-lg border border-border-default bg-surface p-0.5 text-sm">
          {(["MONTHLY", "ANNUAL"] as BillingCycle[]).map((c) => (
            <button
              key={c}
              onClick={() => setCycle(c)}
              className={`rounded-md px-3 py-1.5 font-medium transition-colors ${
                cycle === c ? "bg-accent-primary text-white" : "text-text-secondary hover:text-text-primary"
              }`}
            >
              {c === "MONTHLY" ? t("plans.monthly") : t("plans.annual")}
              {c === "ANNUAL" && (
                <span className={`ml-1.5 text-[11px] ${cycle === c ? "text-white/80" : "text-success"}`}>
                  {t("plans.annualHint")}
                </span>
              )}
            </button>
          ))}
        </div>
      </div>

      <div className="mb-8 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        {PLAN_ORDER.map((name) => {
          const info = plans.plans.find((p) => p.plan === name);
          if (!info) return null;
          const price = priceOf(info, cycle);
          const isCurrent = subscription.status === "ACTIVE" && subscription.plan === name;
          const downgrade = subscription.status === "ACTIVE" && RANK[name] < RANK[subscription.plan];
          return (
            <PlanCard
              key={name}
              info={info}
              price={price}
              cycle={cycle}
              current={isCurrent}
              disabled={!!pending || downgrade}
              onChoose={() => openCheckout(info)}
            />
          );
        })}
      </div>

      <div className="rounded-xl border border-border-default bg-surface p-5">
        <p className="mb-3 font-semibold text-text-primary">{t("history.title")}</p>
        {payments.length === 0 ? (
          <p className="py-4 text-center text-sm text-text-secondary">{t("history.empty")}</p>
        ) : (
          <ul className="divide-y divide-border-default">
            {payments.map((p) => (
              <li key={p.id} className="flex flex-wrap items-center gap-x-4 gap-y-1 py-3 text-sm">
                <span className="min-w-0 flex-1">
                  <span className="font-medium text-text-primary">
                    {t(`plans.name.${p.plan}`)} · {t(`history.cycle.${p.billing_cycle}`)}
                  </span>
                  <span className="ml-2 text-text-secondary">{formatDate(p.created_at)}</span>
                  {p.note && (
                    <span className="mt-0.5 block text-xs text-error">
                      {t("history.reason")}: {p.note}
                    </span>
                  )}
                </span>
                {p.period_end && p.status === "APPROVED" && (
                  <span className="text-xs text-text-secondary">{t("history.until", { date: formatDate(p.period_end) })}</span>
                )}
                {safeUrl(p.receipt_url) && (
                  <a href={safeUrl(p.receipt_url)!} target="_blank" rel="noreferrer" className="text-xs text-accent-primary hover:underline">
                    {t("history.receipt")}
                  </a>
                )}
                <span className="font-semibold text-text-primary">{formatMoney(p.amount, p.currency)}</span>
                <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${STATUS_TONE[p.status]}`}>
                  {t(`history.status.${p.status}`)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>

      <CheckoutModal
        checkout={checkout}
        plans={plans}
        onClose={() => setCheckout(null)}
        onDone={() => {
          toast.success(t("checkout.sent"));
          void done();
        }}
      />
    </div>
  );
}

function CurrentCard() {
  const t = useTranslations("subscription.current");
  const { subscription: s } = useSubscription();
  if (!s) return null;
  const tone =
    s.access === "FULL" ? "text-success" : s.access === "GRACE" ? "text-warning" : "text-error";
  const limit = s.branch_limit === null ? t("unlimited") : String(s.branch_limit);
  return (
    <div className="mb-6 rounded-xl border border-border-default bg-surface p-5">
      <div className="mb-4 flex items-center gap-3">
        <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent-primary/10 text-accent-primary">
          <Gem className="h-5 w-5" aria-hidden="true" />
        </span>
        <p className="font-semibold text-text-primary">{t("title")}</p>
      </div>
      <dl className="grid grid-cols-2 gap-4 text-sm lg:grid-cols-4">
        <div>
          <dt className="text-text-secondary">{t("plan")}</dt>
          <dd className="mt-0.5 font-semibold text-text-primary">{s.plan.replace("_", " ")}</dd>
        </div>
        <div>
          <dt className="text-text-secondary">{t("status")}</dt>
          <dd className="mt-0.5 font-semibold text-text-primary">
            {t(s.status)} · <span className={tone}>{t(`access.${s.access}`)}</span>
          </dd>
        </div>
        <div>
          <dt className="text-text-secondary">{t("validUntil")}</dt>
          <dd className="mt-0.5 font-semibold text-text-primary">
            {s.ends_at ? formatDate(s.ends_at) : t("noExpiry")}
            {s.ends_at && s.days_left !== null && s.days_left >= 0 && (
              <span className="ml-1.5 text-xs font-normal text-text-secondary">
                ({t("daysLeft", { days: s.days_left })})
              </span>
            )}
          </dd>
        </div>
        <div>
          <dt className="text-text-secondary">{t("branches")}</dt>
          <dd className="mt-0.5 font-semibold text-text-primary">
            {s.branch_count} / {limit}
          </dd>
        </div>
      </dl>
    </div>
  );
}

function PlanCard({
  info,
  price,
  cycle,
  current,
  disabled,
  onChoose,
}: {
  info: PlanInfo;
  price: number | null;
  cycle: BillingCycle;
  current: boolean;
  disabled: boolean;
  onChoose: () => void;
}) {
  const t = useTranslations("subscription.plans");
  const branches =
    info.branch_limit === null
      ? t("branchesUnlimited")
      : info.branch_limit === 1
        ? t("branchesOne")
        : t("branchesUpTo", { n: info.branch_limit });
  const payable = price !== null;

  return (
    <div
      className={`flex flex-col rounded-xl border bg-surface p-5 ${
        current ? "border-accent-primary shadow-card" : "border-border-default"
      }`}
    >
      <p className="text-sm font-semibold text-accent-primary">{t(`name.${info.plan}`)}</p>
      <p className="mt-2 text-2xl font-bold text-text-primary">
        {payable ? new Intl.NumberFormat("ru-RU").format(price) : t("custom")}
      </p>
      {payable && <p className="text-xs text-text-secondary">{cycle === "ANNUAL" ? t("perYear") : t("perMonth")}</p>}

      <ul className="mt-4 flex-1 space-y-2 text-sm text-text-secondary">
        <li className="flex gap-2">
          <Check className="mt-0.5 h-4 w-4 shrink-0 text-success" aria-hidden="true" />
          <span>{t("base")}</span>
        </li>
        <li className="flex gap-2">
          <Check className="mt-0.5 h-4 w-4 shrink-0 text-success" aria-hidden="true" />
          <span>{branches}</span>
        </li>
        {info.features
          .filter((f) => f !== "multi_branch")
          .map((f) => (
            <li key={f} className="flex gap-2">
              <Check className="mt-0.5 h-4 w-4 shrink-0 text-success" aria-hidden="true" />
              <span>{t(`feature.${f}`)}</span>
            </li>
          ))}
      </ul>

      <div className="mt-5">
        {current ? (
          <p className="rounded-lg bg-accent-primary/10 py-2 text-center text-sm font-semibold text-accent-primary">
            {t("currentPlan")}
          </p>
        ) : payable ? (
          <Button className="w-full" variant={info.plan === "PRO" ? "primary" : "secondary"} onClick={onChoose} disabled={disabled}>
            {t("choose")}
          </Button>
        ) : (
          <p className="rounded-lg border border-border-default py-2 text-center text-sm text-text-secondary">
            {t("contactSales")}
          </p>
        )}
      </div>
    </div>
  );
}

function CheckoutModal({
  checkout,
  plans,
  onClose,
  onDone,
}: {
  checkout: Checkout | null;
  plans: PlansOut;
  onClose: () => void;
  onDone: () => void;
}) {
  const t = useTranslations("subscription.checkout");
  const tp = useTranslations("subscription.plans");
  const toast = useToast();
  const [receipt, setReceipt] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    setReceipt(null);
  }, [checkout]);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(plans.payment_card.replace(/\s/g, ""));
      toast.success(t("copied"));
    } catch {
      // clipboard blocked: the number is still on screen
    }
  };

  const submit = async () => {
    if (!checkout) return;
    if (!receipt) {
      toast.error(t("needReceipt"));
      return;
    }
    setSubmitting(true);
    try {
      const payment = checkout.payment ?? (await subscriptionApi.requestPayment(checkout.plan, checkout.cycle));
      await subscriptionApi.attachReceipt(payment.id, receipt);
      onDone();
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal open={checkout !== null} onClose={onClose} title={t("title")}>
      {checkout && (
        <div className="space-y-4">
          <div className="rounded-lg bg-background-secondary p-4">
            <p className="text-sm text-text-secondary">
              {tp(`name.${checkout.plan}`)} · {checkout.cycle === "ANNUAL" ? tp("annual") : tp("monthly")}
            </p>
            <p className="text-xs text-text-secondary">{t("amount")}</p>
            <p className="text-2xl font-bold text-text-primary">{formatMoney(checkout.amount, plans.currency)}</p>
          </div>

          <div>
            <p className="mb-1.5 text-sm font-medium text-text-primary">{t("cardTitle")}</p>
            {plans.payment_card ? (
              <div className="flex items-center justify-between gap-3 rounded-lg border border-border-default p-3">
                <div className="min-w-0">
                  <p className="font-mono text-lg font-semibold tracking-wider text-text-primary">{plans.payment_card}</p>
                  {plans.payment_holder && (
                    <p className="text-xs text-text-secondary">
                      {t("holder")}: {plans.payment_holder}
                    </p>
                  )}
                </div>
                <Button size="sm" variant="secondary" onClick={() => void copy()}>
                  <Copy className="h-4 w-4" aria-hidden="true" />
                  {t("copy")}
                </Button>
              </div>
            ) : (
              <p className="rounded-lg border border-warning/40 bg-warning/10 p-3 text-sm text-text-primary">
                {t("cardMissing")}
              </p>
            )}
          </div>

          <div>
            <p className="mb-2 text-sm font-medium text-text-primary">{t("receiptStep")}</p>
            <ImageUploadField value={receipt} onChange={setReceipt} label={t("receiptLabel")} />
          </div>

          <div className="flex justify-end gap-2 pt-1">
            <Button variant="ghost" onClick={onClose}>
              {t("cancel")}
            </Button>
            <Button onClick={() => void submit()} loading={submitting} disabled={!receipt}>
              {t("submit")}
            </Button>
          </div>
        </div>
      )}
    </Modal>
  );
}
