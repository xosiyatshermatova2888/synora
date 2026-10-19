"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Send, Copy, Check, Unlink } from "lucide-react";
import { RestaurantOut, restaurantsApi } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import Button from "@/components/Button";
import PageHeader from "@/components/dashboard/PageHeader";
import PrintersSettings from "@/components/dashboard/PrintersSettings";
import PaymentDetailsSettings from "@/components/dashboard/PaymentDetailsSettings";

export default function SettingsPage() {
  const t = useTranslations("settingsPage");
  const { can } = useAuth();

  const [restaurant, setRestaurant] = useState<RestaurantOut | null>(null);
  const [botToken, setBotToken] = useState("");
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const canManage = can("users.manage");

  const load = () => {
    restaurantsApi.getMine().then(setRestaurant).catch(() => {});
  };

  useEffect(() => {
    load();
  }, []);

  const flash = (message: string) => {
    setNotice(message);
    setTimeout(() => setNotice(null), 3000);
  };

  const handleConnect = async () => {
    if (!botToken.trim()) return;
    setConnecting(true);
    setError(null);
    try {
      await restaurantsApi.connectTelegram(botToken.trim());
      setBotToken("");
      flash(t("connected"));
      load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setConnecting(false);
    }
  };

  const handleDisconnect = async () => {
    if (!window.confirm(t("confirmDisconnect"))) return;
    try {
      await restaurantsApi.disconnectTelegram();
      flash(t("disconnected"));
      load();
    } catch (err) {
      alert((err as Error).message);
    }
  };

  const copyLink = async (username: string) => {
    try {
      await navigator.clipboard.writeText(`https://t.me/${username}`);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // ignore
    }
  };

  if (!canManage) {
    return <div className="p-6 text-sm text-text-secondary">{t("noAccess")}</div>;
  }

  return (
    <div>
      <PageHeader title={t("title")} description={t("description")} />

      {notice && (
        <div className="mb-4 rounded-lg border border-success/30 bg-success/10 px-4 py-2 text-sm text-success">
          {notice}
        </div>
      )}

      <div className="space-y-5">
      <div className="max-w-lg rounded-xl border border-border-default bg-surface p-5">
        <div className="mb-4 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent-primary/10 text-accent-primary">
            <Send className="h-5 w-5" />
          </div>
          <div>
            <p className="font-semibold text-text-primary">{t("telegramTitle")}</p>
            <p className="text-xs text-text-secondary">{t("telegramDescription")}</p>
          </div>
        </div>

        {restaurant?.telegram_connected ? (
          <div className="space-y-3">
            <div className="flex items-center justify-between rounded-lg border border-success/30 bg-success/10 px-3 py-2">
              <span className="text-sm text-success">
                {t("connectedAs")} @{restaurant.telegram_bot_username}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => copyLink(restaurant.telegram_bot_username!)}
                className="flex items-center gap-1.5 rounded-lg border border-border-default px-3 py-1.5 text-xs font-medium text-text-primary hover:border-accent-primary hover:text-accent-primary"
              >
                {copied ? <Check className="h-3.5 w-3.5 text-success" /> : <Copy className="h-3.5 w-3.5" />}
                {copied ? t("linkCopied") : t("copyCustomerLink")}
              </button>
              <button
                onClick={handleDisconnect}
                className="flex items-center gap-1.5 rounded-lg border border-border-default px-3 py-1.5 text-xs font-medium text-error hover:border-error"
              >
                <Unlink className="h-3.5 w-3.5" />
                {t("disconnect")}
              </button>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            <p className="text-xs text-text-secondary">{t("connectHint")}</p>
            <input
              value={botToken}
              onChange={(e) => setBotToken(e.target.value)}
              placeholder={t("tokenPlaceholder")}
              className="w-full rounded-lg border border-border-default bg-background px-3 py-2 text-sm text-text-primary outline-none focus:border-accent-primary"
            />
            {error && <p className="text-sm text-error">{error}</p>}
            <Button size="sm" onClick={handleConnect} disabled={connecting || !botToken.trim()}>
              {connecting ? t("connecting") : t("connect")}
            </Button>
          </div>
        )}
      </div>

      <div className="max-w-lg">
        <PaymentDetailsSettings />
      </div>

      <div className="max-w-3xl">
        <PrintersSettings />
      </div>
      </div>
    </div>
  );
}
