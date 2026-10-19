"use client";

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import QRCode from "qrcode";
import { Copy, Check } from "lucide-react";
import Modal from "@/components/Modal";

export default function QrCodeModal({
  title,
  url,
  onClose,
}: {
  title: string;
  url: string;
  onClose: () => void;
}) {
  const t = useTranslations("branchesPage");
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (canvasRef.current) {
      QRCode.toCanvas(canvasRef.current, url, { width: 240, margin: 1 }).catch(() => {});
    }
  }, [url]);

  const copyUrl = async () => {
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // ignore
    }
  };

  return (
    <Modal open onClose={onClose} title={title}>
      <div className="flex flex-col items-center gap-4">
        <div className="rounded-xl border border-border-default bg-white p-3">
          <canvas ref={canvasRef} />
        </div>
        <p className="break-all text-center text-xs text-text-secondary">{url}</p>
        <button
          onClick={copyUrl}
          className="flex items-center gap-1.5 rounded-lg border border-border-default px-3 py-1.5 text-xs font-medium text-text-primary hover:border-accent-primary hover:text-accent-primary"
        >
          {copied ? <Check className="h-3.5 w-3.5 text-success" /> : <Copy className="h-3.5 w-3.5" />}
          {copied ? t("linkCopied") : t("copyLink")}
        </button>
      </div>
    </Modal>
  );
}
