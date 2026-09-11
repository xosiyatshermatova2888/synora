"use client";

import { useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { ImagePlus, Loader2, X } from "lucide-react";
import { uploadsApi, ApiError } from "@/lib/api";

/**
 * Square image picker used for menu category/product photos. Uploads
 * immediately on file selection via POST /v1/uploads/image and hands the
 * returned URL back to the parent form through `onChange` — the parent just
 * stores it as `image_url` on the create/update payload.
 */
export default function ImageUploadField({
  value,
  onChange,
  label,
}: {
  value: string | null;
  onChange: (url: string | null) => void;
  label: string;
}) {
  const t = useTranslations("menuPage");
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFile = async (file: File) => {
    setError(null);
    setUploading(true);
    try {
      const result = await uploadsApi.uploadImage(file);
      onChange(result.url);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("uploadError"));
    } finally {
      setUploading(false);
    }
  };

  return (
    <div>
      <label className="mb-1 block text-sm font-medium text-text-primary">
        {label}
      </label>
      <div className="flex items-center gap-3">
        <div className="relative h-20 w-20 shrink-0 overflow-hidden rounded-xl border border-border-default bg-background-secondary">
          {value ? (
            // eslint-disable-next-line @next/next/no-img-element -- images may come from any S3-compatible endpoint the operator configures; next/image would require listing that domain ahead of time.
            <img src={value} alt="" className="h-full w-full object-cover" />
          ) : (
            <div className="flex h-full w-full items-center justify-center text-text-secondary/50">
              <ImagePlus className="h-6 w-6" aria-hidden="true" />
            </div>
          )}
          {uploading && (
            <div className="absolute inset-0 flex items-center justify-center bg-background/70">
              <Loader2 className="h-5 w-5 animate-spin text-accent-primary" aria-hidden="true" />
            </div>
          )}
          {value && !uploading && (
            <button
              type="button"
              onClick={() => onChange(null)}
              aria-label={t("removeImage")}
              className="absolute right-1 top-1 flex h-5 w-5 items-center justify-center rounded-full bg-background/90 text-text-secondary shadow-sm hover:text-error"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>

        <div className="flex flex-col gap-1">
          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            disabled={uploading}
            className="rounded-lg border border-border-default bg-surface px-3 py-1.5 text-xs font-medium text-text-primary hover:border-accent-primary hover:text-accent-primary disabled:opacity-50"
          >
            {uploading ? t("uploading") : value ? t("changeImage") : t("uploadImage")}
          </button>
          <p className="text-xs text-text-secondary">{t("imageHint")}</p>
          {error && (
            <p role="alert" className="text-xs text-error">
              {error}
            </p>
          )}
        </div>

        <input
          ref={inputRef}
          type="file"
          accept="image/jpeg,image/png,image/webp,image/avif,image/gif"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            e.target.value = ""; // allow re-selecting the same file later
            if (file) void handleFile(file);
          }}
        />
      </div>
    </div>
  );
}
