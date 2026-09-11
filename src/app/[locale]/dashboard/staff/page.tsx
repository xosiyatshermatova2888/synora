"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Plus, UserRound } from "lucide-react";
import { StaffOut, StaffRole, usersApi } from "@/lib/api";
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
    email: string;
    password: string;
    role: StaffRole;
  }) => {
    try {
      await usersApi.create({
        full_name: payload.fullName,
        email: payload.email,
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
                    <p className="truncate text-xs text-text-secondary">{member.email}</p>
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
                  {!member.is_active && (
                    <span className="rounded-full bg-background-secondary px-2.5 py-1 text-xs font-medium text-text-secondary">
                      {t("inactive")}
                    </span>
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
    </div>
  );
}

function StaffFormModal({
  onClose,
  onSubmit,
}: {
  onClose: () => void;
  onSubmit: (values: {
    fullName: string;
    email: string;
    password: string;
    role: StaffRole;
  }) => void;
}) {
  const t = useTranslations("staffPage");
  const tc = useTranslations("common");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<StaffRole>("WAITER");

  return (
    <Modal open onClose={onClose} title={t("addStaff")}>
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          onSubmit({ fullName: fullName.trim(), email: email.trim(), password, role });
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
            {t("email")}
          </label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
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
