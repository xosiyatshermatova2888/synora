"use client";

import { createContext, useContext, useState, useCallback } from "react";
import TrialFormModal from "@/components/TrialFormModal";
import ContactFormModal from "@/components/ContactFormModal";

interface CTAContextValue {
  openTrial: () => void;
  openContact: () => void;
}

const CTAContext = createContext<CTAContextValue | null>(null);

export function useCTA() {
  const ctx = useContext(CTAContext);
  if (!ctx) throw new Error("useCTA must be used within CTAProvider");
  return ctx;
}

export default function CTAProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const [trialOpen, setTrialOpen] = useState(false);
  const [contactOpen, setContactOpen] = useState(false);

  const openTrial = useCallback(() => setTrialOpen(true), []);
  const openContact = useCallback(() => setContactOpen(true), []);

  return (
    <CTAContext.Provider value={{ openTrial, openContact }}>
      {children}
      <TrialFormModal open={trialOpen} onClose={() => setTrialOpen(false)} />
      <ContactFormModal
        open={contactOpen}
        onClose={() => setContactOpen(false)}
      />
    </CTAContext.Provider>
  );
}
