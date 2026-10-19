"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { CreditCard } from "lucide-react";
import { restaurantsApi } from "@/lib/api";
import Button from "@/components/Button";
import { useToast } from "@/components/ui/Toast";

/** Card shown to customers who choose "card transfer" in the Telegram bot. */
export default function PaymentDetailsSettings() {
  const t = useTranslations("paymentDetailsSettings");
  const tc = useTranslations("common");
  const toast = useToast();
  const [number, setNumber] = useState("");
  const [holder, setHolder] = useState("");
  const [loaded, setLoaded] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    restaurantsApi
      .getMine()
      .then((r) => {
        setNumber(r.payment_card_number ?? "");
        setHolder(r.payment_card_holder ?? "");
      })
      .catch(() => {})
      .finally(() => setLoaded(true));
  }, []);

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      await restaurantsApi.updatePaymentDetails({
        payment_card_number: number.trim() || null,
        payment_card_holder: holder.trim() || null,
      });
      toast.success(tc("actions.saved"));
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const field =
    "mt-1 w-full rounded-lg border border-border-default bg-background px-3 py-2 text-sm text-text-primary outline-none focus:border-accent-primary";

  return (
    <form onSubmit={save} className="rounded-xl border border-border-default bg-surface p-5 shadow-card">
      <div className="mb-4 flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent-primary/10 text-accent-primary">
          <CreditCard className="h-5 w-5" />
        </div>
        <div>
          <p className="font-semibold text-text-primary">{t("title")}</p>
          <p className="text-xs text-text-secondary">{t("description")}</p>
        </div>
      </div>
      <div className="space-y-3">
        <label className="block text-sm font-medium text-text-primary">
          {t("cardNumber")}
          <input
            value={number}
            onChange={(e) => setNumber(e.target.value)}
            placeholder="8600 0000 0000 0000"
            inputMode="numeric"
            maxLength={32}
            disabled={!loaded}
            className={field}
          />
        </label>
        <label className="block text-sm font-medium text-text-primary">
          {t("cardHolder")}
          <input value={holder} onChange={(e) => setHolder(e.target.value)} maxLength={100} disabled={!loaded} className={field} />
        </label>
        <p className="text-xs text-text-secondary">{t("hint")}</p>
        <Button size="sm" type="submit" loading={saving} disabled={!loaded}>
          {tc("actions.save")}
        </Button>
      </div>
    </form>
  );
}
