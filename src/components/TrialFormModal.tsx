"use client";

import { useTranslations } from "next-intl";
import Modal from "@/components/Modal";
import LeadForm from "@/components/LeadForm";

export default function TrialFormModal({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const t = useTranslations("trial");

  return (
    <Modal open={open} onClose={onClose} title={t("primaryCta")}>
      <p className="mb-5 text-sm text-text-secondary">
        {t("description")} {t("noCard")}
      </p>
      <LeadForm
        fields={[
          { name: "name" },
          { name: "restaurant" },
          { name: "email", type: "email" },
          { name: "phone", optional: true },
        ]}
        submitKey="submit"
      />
    </Modal>
  );
}
