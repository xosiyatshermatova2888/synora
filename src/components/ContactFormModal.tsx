"use client";

import { useTranslations } from "next-intl";
import Modal from "@/components/Modal";
import LeadForm from "@/components/LeadForm";

export default function ContactFormModal({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const t = useTranslations("form");

  return (
    <Modal open={open} onClose={onClose} title={t("contactTitle")}>
      <p className="mb-5 text-sm text-text-secondary">
        {t("contactDescription")}
      </p>
      <LeadForm
        fields={[
          { name: "name" },
          { name: "restaurant" },
          { name: "email", type: "email" },
          { name: "message", optional: true },
        ]}
        submitKey="contactSubmit"
      />
    </Modal>
  );
}
