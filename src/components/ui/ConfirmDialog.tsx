"use client";

import { useTranslations } from "next-intl";
import Modal from "@/components/Modal";
import Button from "@/components/Button";

export default function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel,
  tone = "danger",
  loading = false,
  onConfirm,
  onClose,
}: {
  open: boolean;
  title: string;
  message?: string;
  confirmLabel?: string;
  tone?: "danger" | "primary";
  loading?: boolean;
  onConfirm: () => void;
  onClose: () => void;
}) {
  const t = useTranslations("common");
  return (
    <Modal open={open} onClose={onClose} title={title}>
      {message && <p className="mb-6 text-sm text-text-secondary">{message}</p>}
      <div className="flex justify-end gap-2">
        <Button variant="secondary" size="sm" onClick={onClose} disabled={loading}>
          {t("actions.cancel")}
        </Button>
        <Button variant={tone} size="sm" onClick={onConfirm} loading={loading}>
          {confirmLabel ?? t("ui.confirm")}
        </Button>
      </div>
    </Modal>
  );
}
