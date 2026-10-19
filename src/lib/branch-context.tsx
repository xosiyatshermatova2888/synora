"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { BranchOut, branchesApi } from "./api";

const STORAGE_KEY = "synora.selectedBranchId";

interface BranchContextValue {
  branches: BranchOut[];
  selectedBranchId: string | null;
  setSelectedBranchId: (id: string) => void;
  reload: () => Promise<void>;
}

const BranchContext = createContext<BranchContextValue | undefined>(undefined);

export function BranchProvider({ children }: { children: React.ReactNode }) {
  const [branches, setBranches] = useState<BranchOut[]>([]);
  const [selectedBranchId, setSelectedBranchIdState] = useState<string | null>(null);

  const setSelectedBranchId = useCallback((id: string) => {
    setSelectedBranchIdState(id);
    try {
      localStorage.setItem(STORAGE_KEY, id);
    } catch {
      // ignore (private mode / blocked storage)
    }
  }, []);

  const reload = useCallback(async () => {
    try {
      const list = await branchesApi.list();
      setBranches(list);
      setSelectedBranchIdState((prev) => {
        if (prev && list.some((b) => b.id === prev)) return prev;
        let stored: string | null = null;
        try {
          stored = localStorage.getItem(STORAGE_KEY);
        } catch {
          stored = null;
        }
        if (stored && list.some((b) => b.id === stored)) return stored;
        return list[0]?.id ?? null;
      });
    } catch {
      setBranches([]);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  return (
    <BranchContext.Provider value={{ branches, selectedBranchId, setSelectedBranchId, reload }}>
      {children}
    </BranchContext.Provider>
  );
}

export function useBranch(): BranchContextValue {
  const ctx = useContext(BranchContext);
  if (!ctx) throw new Error("useBranch must be used within a BranchProvider");
  return ctx;
}
