"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { BarChart3, KeyRound, Lock, Pencil, Plus, ShieldCheck, UserRound, UserX } from "lucide-react";
import { StaffOut, StaffRole, WaiterStatsOut, ordersApi, usersApi } from "@/lib/api";
import { formatMoney } from "@/lib/format";
import type { LoadState } from "@/lib/load-state";
import { loadingState, errorState, dataState } from "@/lib/load-state";
import { useAuth } from "@/lib/auth-context";
import Modal from "@/components/Modal";
import Button from "@/components/Button";
import StateView from "@/components/dashboard/StateView";
import PageHeader from "@/components/dashboard/PageHeader";

const ROLES: StaffRole[] = ["MANAGER", "CASHIER", "WAITER", "KITCHEN", "ACCOUNTANT"];

const ROLE_BADGE_STYLES: Record<string, string> = {
  OWNER: "bg-accent-primary/10 text-accent-primary",
  ADMIN: "bg-accent-primary/10 text-accent-primary",
  MANAGER: "bg-accent-ai/10 text-accent-ai",
  CASHIER: "bg-success/10 text-success",
  WAITER: "bg-warning/10 text-warning",
  KITCHEN: "bg-error/10 text-error",
  ACCOUNTANT: "bg-background-secondary text-text-secondary",
};

export default function StaffPage() {
  const t = useTranslations("staffPage");
  const tc = useTranslations("common");
  const { can } = useAuth();

  const [staff, setStaff] = useState<LoadState<StaffOut[]>>(loadingState());
  const [modalOpen, setModalOpen] = useState(false);
  const [pinTarget, setPinTarget] = useState<StaffOut | null>(null);
  const [passwordTarget, setPasswordTarget] = useState<StaffOut | null>(null);
  const [statsTarget, setStatsTarget] = useState<StaffOut | null>(null);
  const [editTarget, setEditTarget] = useState<StaffOut | null>(null);
  const [roleTarget, setRoleTarget] = useState<StaffOut | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const canManage = can("users.manage");

  const load = useCallback(async () => {
    try {
      const list = await usersApi.list();
      setStaff(dataState(list));
    } catch (err) {
      setStaff(errorState((err as Error).message));
    }
  }, []);

  useEffect(() => {
    void (async () => {
      try {
        const list = await usersApi.list();
        setStaff(dataState(list));
      } catch (err) {
        setStaff(errorState((err as Error).message));
      }
    })();
  }, []);

  if (!can("users.read")) {
    return (
      <div className="flex flex-col items-center gap-2 py-16 text-center">
        <p className="text-sm font-medium text-text-secondary">{t("noPermission")}</p>
      </div>
    );
  }

  const flash = (message: string) => {
    setNotice(message);
    setTimeout(() => setNotice(null), 3000);
  };

  const handleCreate = async (payload: {
    fullName: string;
    username: string;
    password: string;
    role: StaffRole;
  }) => {
    try {
      await usersApi.create({
        full_name: payload.fullName,
        username: payload.username,
        password: payload.password,
        role: payload.role,
      });
      setModalOpen(false);
      flash(t("created"));
      load();
    } catch (err) {
      alert((err as Error).message);
    }
  };

  const handleSetPin = async (pin: string) => {
    if (!pinTarget) return;
    try {
      await usersApi.setPin(pinTarget.id, pin);
      setPinTarget(null);
      flash(pin ? t("pinUpdated") : t("pinCleared"));
      load();
    } catch (err) {
      alert((err as Error).message);
    }
  };

  const handleSetPassword = async (password: string) => {
    if (!passwordTarget) return;
    try {
      await usersApi.setPassword(passwordTarget.id, password);
      setPasswordTarget(null);
      flash(t("passwordUpdated"));
      load();
    } catch (err) {
      alert((err as Error).message);
    }
  };

  const handleUpdateProfile = async (payload: { fullName: string; phone: string }) => {
    if (!editTarget) return;
    try {
      await usersApi.update(editTarget.id, { full_name: payload.fullName, phone: payload.phone });
      setEditTarget(null);
      flash(tc("actions.saved"));
      load();
    } catch (err) {
      alert((err as Error).message);
    }
  };

  const handleChangeRole = async (role: StaffRole) => {
    if (!roleTarget) return;
    try {
      await usersApi.changeRole(roleTarget.id, role);
      setRoleTarget(null);
      flash(tc("actions.saved"));
      load();
    } catch (err) {
      alert((err as Error).message);
    }
  };

  const handleToggleActive = async (member: StaffOut) => {
    if (member.is_active && !window.confirm(t("confirmDeactivate", { name: member.full_name }))) {
      return;
    }
    try {
      await usersApi.setActive(member.id, !member.is_active);
      flash(tc("actions.saved"));
      load();
    } catch (err) {
      alert((err as Error).message);
    }
  };

  return (
    <div>
      <PageHeader
        title={t("title")}
        description={t("description")}
        actions={
          canManage ? (
            <Button size="sm" onClick={() => setModalOpen(true)}>
              <Plus className="h-4 w-4" />
              {t("addStaff")}
            </Button>
          ) : undefined
        }
      />

      {notice && (
        <div className="mb-4 rounded-lg border border-success/30 bg-success/10 px-4 py-2 text-sm text-success">
          {notice}
        </div>
      )}

      {staff.type === "data" ? (
        staff.data.length === 0 ? (
          <StateView kind="empty" message={t("empty")} />
        ) : (
          <div className="overflow-hidden rounded-xl border border-border-default bg-surface">
            <ul className="divide-y divide-border-default">
              {staff.data.map((member) => (
                <li
                  key={member.id}
                  className="flex flex-wrap items-center gap-3 px-5 py-4"
                >
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-brand-gradient text-sm font-bold text-white">
                    {member.full_name.charAt(0).toUpperCase()}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-medium text-text-primary">
                      {member.full_name}
                    </p>
                    <p className="truncate text-xs text-text-secondary">{member.username}</p>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {member.roles.map((role) => (
                      <span
                        key={role}
                        className={`rounded-full px-2.5 py-1 text-xs font-semibold ${ROLE_BADGE_STYLES[role] ?? "bg-background-secondary text-text-secondary"}`}
                      >
                        {tc(`roles.${role}`)}
                      </span>
                    ))}
                  </div>
                  <span
                    className={`rounded-full px-2.5 py-1 text-xs font-medium ${
                      member.has_pin
                        ? "bg-success/10 text-success"
                        : "bg-background-secondary text-text-secondary"
                    }`}
                  >
                    {member.has_pin ? t("pinBadgeSet") : t("pinBadgeNotSet")}
                  </span>
                  {!member.is_active && (
                    <span className="rounded-full bg-background-secondary px-2.5 py-1 text-xs font-medium text-text-secondary">
                      {t("inactive")}
                    </span>
                  )}
                  {member.roles.includes("WAITER") && (
                    <button
                      onClick={() => setStatsTarget(member)}
                      className="flex items-center gap-1.5 rounded-lg border border-border-default px-2.5 py-1.5 text-xs font-medium text-text-primary hover:border-accent-primary hover:text-accent-primary"
                    >
                      <BarChart3 className="h-3.5 w-3.5" />
                      {t("viewStats")}
                    </button>
                  )}
                  {canManage && !member.roles.includes("OWNER") && !member.roles.includes("ADMIN") && (
                    <div className="flex flex-wrap gap-1.5">
                      <button
                        onClick={() => setEditTarget(member)}
                        aria-label={t("editProfile")}
                        title={t("editProfile")}
                        className="flex h-8 w-8 items-center justify-center rounded-lg border border-border-default text-text-primary hover:border-accent-primary hover:text-accent-primary"
                      >
                        <Pencil className="h-3.5 w-3.5" />
                      </button>
                      <button
                        onClick={() => setRoleTarget(member)}
                        className="flex items-center gap-1.5 rounded-lg border border-border-default px-2.5 py-1.5 text-xs font-medium text-text-primary hover:border-accent-primary hover:text-accent-primary"
                      >
                        <ShieldCheck className="h-3.5 w-3.5" />
                        {t("changeRole")}
                      </button>
                      <button
                        onClick={() => setPinTarget(member)}
                        className="flex items-center gap-1.5 rounded-lg border border-border-default px-2.5 py-1.5 text-xs font-medium text-text-primary hover:border-accent-primary hover:text-accent-primary"
                      >
                        <KeyRound className="h-3.5 w-3.5" />
                        {member.has_pin ? t("editPin") : t("setPin")}
                      </button>
                      <button
                        onClick={() => setPasswordTarget(member)}
                        className="flex items-center gap-1.5 rounded-lg border border-border-default px-2.5 py-1.5 text-xs font-medium text-text-primary hover:border-accent-primary hover:text-accent-primary"
                      >
                        <Lock className="h-3.5 w-3.5" />
                        {t("resetPassword")}
                      </button>
                      <button
                        onClick={() => handleToggleActive(member)}
                        className={`flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs font-medium ${
                          member.is_active
                            ? "border-border-default text-error hover:border-error"
                            : "border-border-default text-success hover:border-success"
                        }`}
                      >
                        <UserX className="h-3.5 w-3.5" />
                        {member.is_active ? t("deactivate") : t("activate")}
                      </button>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )
      ) : (
        <StateView
          kind={staff.type}
          message={staff.type === "error" ? staff.message : undefined}
          onRetry={staff.type === "error" ? () => load() : undefined}
        />
      )}

      {modalOpen && (
        <StaffFormModal onClose={() => setModalOpen(false)} onSubmit={handleCreate} />
      )}
      {pinTarget && (
        <PinModal
          member={pinTarget}
          onClose={() => setPinTarget(null)}
          onSubmit={handleSetPin}
        />
      )}
      {passwordTarget && (
        <PasswordModal
          member={passwordTarget}
          onClose={() => setPasswordTarget(null)}
          onSubmit={handleSetPassword}
        />
      )}
      {statsTarget && (
        <StatsModal member={statsTarget} onClose={() => setStatsTarget(null)} />
      )}
      {editTarget && (
        <EditProfileModal
          member={editTarget}
          onClose={() => setEditTarget(null)}
          onSubmit={handleUpdateProfile}
        />
      )}
      {roleTarget && (
        <RoleModal member={roleTarget} onClose={() => setRoleTarget(null)} onSubmit={handleChangeRole} />
      )}
    </div>
  );
}

function StatsModal({ member, onClose }: { member: StaffOut; onClose: () => void }) {
  const t = useTranslations("staffPage");
  const [stats, setStats] = useState<WaiterStatsOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    ordersApi
      .statsFor(member.id)
      .then(setStats)
      .catch((err) => setError((err as Error).message));
  }, [member.id]);

  return (
    <Modal open onClose={onClose} title={`${t("statsTitle")} — ${member.full_name}`}>
      {error ? (
        <p className="text-sm text-error">{error}</p>
      ) : !stats ? (
        <p className="text-sm text-text-secondary">{t("statsLoading")}</p>
      ) : (
        <div className="grid grid-cols-2 gap-3">
          <StatTile label={t("statsSalesToday")} value={formatMoney(stats.total_sales, "UZS")} />
          <StatTile label={t("statsOrdersToday")} value={String(stats.order_count)} />
          <StatTile label={t("statsTablesServed")} value={String(stats.tables_served)} />
          <StatTile label={t("statsAverageCheck")} value={formatMoney(stats.average_check, "UZS")} />
          <StatTile label={t("statsCancelled")} value={String(stats.cancelled_count)} />
        </div>
      )}
    </Modal>
  );
}

function StatTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-border-default bg-background p-3">
      <p className="text-xs text-text-secondary">{label}</p>
      <p className="mt-0.5 text-base font-bold text-text-primary">{value}</p>
    </div>
  );
}

function PinModal({
  member,
  onClose,
  onSubmit,
}: {
  member: StaffOut;
  onClose: () => void;
  onSubmit: (pin: string) => void;
}) {
  const t = useTranslations("staffPage");
  const tc = useTranslations("common");
  const [pin, setPin] = useState("");

  return (
    <Modal open onClose={onClose} title={`${t("pinModalTitle")} — ${member.full_name}`}>
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          onSubmit(pin);
        }}
      >
        <p className="text-xs text-text-secondary">{t("pinModalHint")}</p>
        <div>
          <label className="mb-1 block text-sm font-medium text-text-primary">
            {t("pinLabel")}
          </label>
          <input
            value={pin}
            onChange={(e) => setPin(e.target.value.replace(/\D/g, "").slice(0, 6))}
            inputMode="numeric"
            pattern="\d{4,6}"
            placeholder="••••"
            className="w-full rounded-lg border border-border-default bg-background px-3 py-2 text-sm tracking-widest text-text-primary outline-none focus:border-accent-primary"
          />
        </div>
        <div className="flex justify-end gap-2">
          <Button variant="secondary" size="sm" onClick={onClose}>
            {tc("actions.cancel")}
          </Button>
          <Button type="submit" size="sm" disabled={pin.length > 0 && pin.length < 4}>
            {tc("actions.save")}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

function PasswordModal({
  member,
  onClose,
  onSubmit,
}: {
  member: StaffOut;
  onClose: () => void;
  onSubmit: (password: string) => void;
}) {
  const t = useTranslations("staffPage");
  const tc = useTranslations("common");
  const [password, setPassword] = useState("");

  return (
    <Modal open onClose={onClose} title={`${t("resetPasswordTitle")} — ${member.full_name}`}>
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          onSubmit(password);
        }}
      >
        <p className="text-xs text-text-secondary">{t("resetPasswordHint")}</p>
        <div>
          <label className="mb-1 block text-sm font-medium text-text-primary">
            {t("newPasswordLabel")}
          </label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={8}
            className="w-full rounded-lg border border-border-default bg-background px-3 py-2 text-sm text-text-primary outline-none focus:border-accent-primary"
          />
        </div>
        <div className="flex justify-end gap-2">
          <Button variant="secondary" size="sm" onClick={onClose}>
            {tc("actions.cancel")}
          </Button>
          <Button type="submit" size="sm">
            {tc("actions.save")}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

function EditProfileModal({
  member,
  onClose,
  onSubmit,
}: {
  member: StaffOut;
  onClose: () => void;
  onSubmit: (payload: { fullName: string; phone: string }) => void;
}) {
  const t = useTranslations("staffPage");
  const tc = useTranslations("common");
  const [fullName, setFullName] = useState(member.full_name);
  const [phone, setPhone] = useState("");

  return (
    <Modal open onClose={onClose} title={`${t("editProfile")} — ${member.full_name}`}>
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          onSubmit({ fullName: fullName.trim(), phone: phone.trim() });
        }}
      >
        <div>
          <label className="mb-1 block text-sm font-medium text-text-primary">{t("fullName")}</label>
          <input
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            required
            minLength={2}
            className="w-full rounded-lg border border-border-default bg-background px-3 py-2 text-sm text-text-primary outline-none focus:border-accent-primary"
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-text-primary">{t("phone")}</label>
          <input
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            className="w-full rounded-lg border border-border-default bg-background px-3 py-2 text-sm text-text-primary outline-none focus:border-accent-primary"
          />
        </div>
        <div className="flex justify-end gap-2">
          <Button variant="secondary" size="sm" onClick={onClose}>
            {tc("actions.cancel")}
          </Button>
          <Button type="submit" size="sm">
            {tc("actions.save")}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

function RoleModal({
  member,
  onClose,
  onSubmit,
}: {
  member: StaffOut;
  onClose: () => void;
  onSubmit: (role: StaffRole) => void;
}) {
  const t = useTranslations("staffPage");
  const tc = useTranslations("common");
  const currentRole = ROLES.find((r) => member.roles.includes(r)) ?? "WAITER";
  const [role, setRole] = useState<StaffRole>(currentRole);

  return (
    <Modal open onClose={onClose} title={`${t("changeRole")} — ${member.full_name}`}>
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          onSubmit(role);
        }}
      >
        <select
          value={role}
          onChange={(e) => setRole(e.target.value as StaffRole)}
          className="w-full rounded-lg border border-border-default bg-background px-3 py-2 text-sm text-text-primary outline-none focus:border-accent-primary"
        >
          {ROLES.map((r) => (
            <option key={r} value={r}>
              {tc(`roles.${r}`)}
            </option>
          ))}
        </select>
        <div className="flex justify-end gap-2">
          <Button variant="secondary" size="sm" onClick={onClose}>
            {tc("actions.cancel")}
          </Button>
          <Button type="submit" size="sm">
            {tc("actions.save")}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

function StaffFormModal({
  onClose,
  onSubmit,
}: {
  onClose: () => void;
  onSubmit: (values: {
    fullName: string;
    username: string;
    password: string;
    role: StaffRole;
  }) => void;
}) {
  const t = useTranslations("staffPage");
  const tc = useTranslations("common");
  const [fullName, setFullName] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<StaffRole>("WAITER");

  return (
    <Modal open onClose={onClose} title={t("addStaff")}>
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          onSubmit({ fullName: fullName.trim(), username: username.trim(), password, role });
        }}
      >
        <div className="flex items-center gap-2 rounded-lg bg-accent-primary/5 px-3 py-2 text-xs text-text-secondary">
          <UserRound className="h-4 w-4 shrink-0 text-accent-primary" />
          {t("addStaffHint")}
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-text-primary">
            {t("fullName")}
          </label>
          <input
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            required
            minLength={2}
            className="w-full rounded-lg border border-border-default bg-background px-3 py-2 text-sm text-text-primary outline-none focus:border-accent-primary"
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-text-primary">
            {t("username")}
          </label>
          <input
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
            minLength={3}
            className="w-full rounded-lg border border-border-default bg-background px-3 py-2 text-sm text-text-primary outline-none focus:border-accent-primary"
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-text-primary">
            {t("password")}
          </label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={8}
            className="w-full rounded-lg border border-border-default bg-background px-3 py-2 text-sm text-text-primary outline-none focus:border-accent-primary"
          />
          <p className="mt-1 text-xs text-text-secondary">{t("passwordHint")}</p>
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-text-primary">
            {t("role")}
          </label>
          <select
            value={role}
            onChange={(e) => setRole(e.target.value as StaffRole)}
            className="w-full rounded-lg border border-border-default bg-background px-3 py-2 text-sm text-text-primary outline-none focus:border-accent-primary"
          >
            {ROLES.map((r) => (
              <option key={r} value={r}>
                {tc(`roles.${r}`)}
              </option>
            ))}
          </select>
        </div>
        <div className="flex justify-end gap-2">
          <Button variant="secondary" size="sm" onClick={onClose}>
            {tc("actions.cancel")}
          </Button>
          <Button type="submit" size="sm">
            {tc("actions.save")}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
