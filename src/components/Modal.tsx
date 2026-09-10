"use client";

import { useEffect, useRef, useCallback } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";

export default function Modal({
  open,
  onClose,
  title,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
}) {
  const panelRef = useRef<HTMLDivElement>(null);
  const previouslyFocused = useRef<HTMLElement | null>(null);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (!panelRef.current) return;

      const focusables = panelRef.current.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), textarea, input, select, [tabindex]:not([tabindex="-1"])'
      );
      if (focusables.length === 0) return;

      const first = focusables[0];
      const last = focusables[focusables.length - 1];

      if (e.key === "Tab") {
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    },
    [onClose]
  );

  useEffect(() => {
    if (open) {
      previouslyFocused.current = document.activeElement as HTMLElement;
      document.addEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "hidden";
      const timer = setTimeout(() => {
        panelRef.current?.querySelector<HTMLElement>("input, button")?.focus();
      }, 50);
      return () => {
        clearTimeout(timer);
        document.removeEventListener("keydown", handleKeyDown);
        document.body.style.overflow = "";
        previouslyFocused.current?.focus();
      };
    }
  }, [open, handleKeyDown]);

  if (typeof document === "undefined") return null;

  return createPortal(
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm"
          onClick={onClose}
        >
          <motion.div
            ref={panelRef}
            role="dialog"
            aria-modal="true"
            aria-label={title}
            initial={{ opacity: 0, y: 16, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 16, scale: 0.98 }}
            transition={{ duration: 0.25 }}
            className="max-h-[90vh] w-full max-w-md overflow-y-auto rounded-2xl border border-border-default bg-background-secondary p-6 sm:p-8"
            onClick={(e: React.MouseEvent) => e.stopPropagation()}
          >
            <div className="mb-5 flex items-center justify-between">
              <h2 className="text-xl font-semibold">{title}</h2>
              <button
                onClick={onClose}
                aria-label="Close"
                className="rounded-lg p-1.5 text-text-secondary transition-colors hover:bg-surface hover:text-text-primary focus-visible:outline-2 focus-visible:outline-accent-primary"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            {children}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body
  );
}

