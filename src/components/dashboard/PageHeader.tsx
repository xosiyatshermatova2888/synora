"use client";

interface PageHeaderProps {
  title: string;
  description?: string;
  /** Primary + secondary actions, right-aligned. */
  actions?: React.ReactNode;
  /** Optional small line above the title (e.g. a section label). */
  eyebrow?: string;
}

export default function PageHeader({ title, description, actions, eyebrow }: PageHeaderProps) {
  return (
    <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0">
        {eyebrow && (
          <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-accent-primary">
            {eyebrow}
          </p>
        )}
        <h1 className="text-[22px] font-semibold leading-7 text-text-primary">{title}</h1>
        {description && <p className="mt-1 text-sm text-text-secondary">{description}</p>}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}
