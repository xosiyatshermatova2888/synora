"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslations, useLocale } from "next-intl";
import { Plus, Pencil, Building2, QrCode } from "lucide-react";
import { BranchOut, RestaurantOut, branchesApi, restaurantsApi } from "@/lib/api";
import type { LoadState } from "@/lib/load-state";
import { loadingState, errorState, dataState } from "@/lib/load-state";
import { useAuth } from "@/lib/auth-context";
import { useBranch } from "@/lib/branch-context";
import Modal from "@/components/Modal";
import Button from "@/components/Button";
import StateView from "@/components/dashboard/StateView";
import PageHeader from "@/components/dashboard/PageHeader";
import QrCodeModal from "@/components/dashboard/QrCodeModal";

export default function BranchesPage() {
  const t = useTranslations("branchesPage");
  const tc = useTranslations("common");
  const locale = useLocale();
  const { can } = useAuth();
  const { reload: reloadBranchContext } = useBranch();

  const [branches, setBranches] = useState<LoadState<BranchOut[]>>(loadingState());
  const [restaurant, setRestaurant] = useState<RestaurantOut | null>(null);
  const [modal, setModal] = useState<
    { type: "create" } | { type: "edit"; branch: BranchOut } | { type: "qr"; branch: BranchOut } | null
  >(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    restaurantsApi.getMine().then(setRestaurant).catch(() => {});
  }, []);

  const canManage = can("users.manage");

  const load = useCallback(async () => {
    try {
      const list = await branchesApi.list();
      setBranches(dataState(list));
    } catch (err) {
      setBranches(errorState((err as Error).message));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const flash = (message: string) => {
    setNotice(message);
    setTimeout(() => setNotice(null), 3000);
  };

  const handleCreate = async (payload: { name: string; address: string; phone: string }) => {
    try {
      await branchesApi.create({
        name: payload.name,
        address: payload.address || null,
        phone: payload.phone || null,
      });
      setModal(null);
      flash(tc("actions.saved"));
      load();
      reloadBranchContext();
    } catch (err) {
      alert((err as Error).message);
    }
  };

  const handleUpdate = async (
    branch: BranchOut,
    payload: { name: string; address: string; phone: string; is_active: boolean }
  ) => {
    try {
      await branchesApi.update(branch.id, {
        name: payload.name,
        address: payload.address || null,
        phone: payload.phone || null,
        is_active: payload.is_active,
      });
      setModal(null);
      flash(tc("actions.saved"));
      load();
      reloadBranchContext();
    } catch (err) {
      alert((err as Error).message);
    }
  };

  const list = branches.type === "data" ? branches.data : [];

  return (
    <div>
      <PageHeader
        title={t("title")}
        description={t("description")}
        actions={
          canManage ? (
            <Button size="sm" onClick={() => setModal({ type: "create" })}>
              <Plus className="h-4 w-4" />
              {t("addBranch")}
            </Button>
          ) : undefined
        }
      />

      {notice && (
        <div className="mb-4 rounded-lg border border-success/30 bg-success/10 px-4 py-2 text-sm text-success">
          {notice}
        </div>
      )}

      {branches.type === "data" ? (
        list.length === 0 ? (
          <StateView kind="empty" message={t("noBranches")} />
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {list.map((branch) => (
              <div
                key={branch.id}
                className="flex flex-col rounded-xl border border-border-default bg-surface p-4 shadow-sm"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-accent-primary/10 text-accent-primary">
                    <Building2 className="h-5 w-5" />
                  </div>
                  {!branch.is_active && (
                    <span className="rounded-full bg-background-secondary px-2.5 py-1 text-xs font-medium text-text-secondary">
                      {t("inactive")}
                    </span>
                  )}
                </div>
                <p className="mt-3 font-semibold text-text-primary">{branch.name}</p>
                {branch.address && <p className="text-sm text-text-secondary">{branch.address}</p>}
                {branch.phone && <p className="text-sm text-text-secondary">{branch.phone}</p>}
                <div className="mt-3 flex justify-end gap-1.5">
                  <button
                    onClick={() => setModal({ type: "qr", branch })}
                    aria-label={t("showQr")}
                    title={t("showQr")}
                    className="flex h-7 w-7 items-center justify-center rounded-lg text-text-secondary hover:bg-background hover:text-accent-primary"
                  >
                    <QrCode className="h-3.5 w-3.5" />
                  </button>
                  {canManage && (
                    <button
                      onClick={() => setModal({ type: "edit", branch })}
                      aria-label={t("editBranch")}
                      className="flex h-7 w-7 items-center justify-center rounded-lg text-text-secondary hover:bg-background hover:text-accent-primary"
                    >
                      <Pencil className="h-3.5 w-3.5" />
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )
      ) : (
        <StateView
          kind={branches.type}
          message={branches.type === "error" ? branches.message : undefined}
          onRetry={branches.type === "error" ? () => load() : undefined}
        />
      )}

      {modal?.type === "qr" && restaurant && (
        <QrCodeModal
          title={`${t("showQr")} — ${modal.branch.name}`}
          url={`${window.location.origin}/${locale}/order/${restaurant.slug}/${modal.branch.id}`}
          onClose={() => setModal(null)}
        />
      )}
      {modal?.type === "create" && (
        <BranchFormModal title={t("addBranch")} onClose={() => setModal(null)} onSubmit={handleCreate} />
      )}
      {modal?.type === "edit" && (
        <BranchFormModal
          title={t("editBranch")}
          initial={modal.branch}
          onClose={() => setModal(null)}
          onSubmit={(payload) => handleUpdate(modal.branch, payload)}
        />
      )}
    </div>
  );
}

function BranchFormModal({
  title,
  initial,
  onClose,
  onSubmit,
}: {
  title: string;
  initial?: BranchOut;
  onClose: () => void;
  onSubmit: (payload: { name: string; address: string; phone: string; is_active: boolean }) => void;
}) {
  const t = useTranslations("branchesPage");
  const tc = useTranslations("common");
  const [name, setName] = useState(initial?.name ?? "");
  const [address, setAddress] = useState(initial?.address ?? "");
  const [phone, setPhone] = useState(initial?.phone ?? "");
  const [isActive, setIsActive] = useState(initial?.is_active ?? true);

  return (
    <Modal open onClose={onClose} title={title}>
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          onSubmit({ name: name.trim(), address: address.trim(), phone: phone.trim(), is_active: isActive });
        }}
      >
        <div>
          <label className="mb-1 block text-sm font-medium text-text-primary">{t("branchName")}</label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            className="w-full rounded-lg border border-border-default bg-background px-3 py-2 text-sm text-text-primary outline-none focus:border-accent-primary"
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-text-primary">{t("address")}</label>
          <input
            value={address}
            onChange={(e) => setAddress(e.target.value)}
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
        {initial && (
          <label className="flex items-center gap-2 text-sm text-text-primary">
            <input
              type="checkbox"
              checked={isActive}
              onChange={(e) => setIsActive(e.target.checked)}
              className="h-4 w-4 rounded border-border-default"
            />
            {t("isActive")}
          </label>
        )}
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
