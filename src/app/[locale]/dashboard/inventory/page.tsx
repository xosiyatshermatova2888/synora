"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Plus, ArrowDownCircle, ArrowUpCircle, Settings2, AlertTriangle, History } from "lucide-react";
import {
  InventoryItemOut,
  InventoryTransactionOut,
  InventoryTransactionType,
  inventoryApi,
} from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { LoadState } from "@/lib/load-state";
import { loadingState, errorState, dataState } from "@/lib/load-state";
import { useAuth } from "@/lib/auth-context";
import { useBranch } from "@/lib/branch-context";
import Modal from "@/components/Modal";
import Button from "@/components/Button";
import StateView from "@/components/dashboard/StateView";
import PageHeader from "@/components/dashboard/PageHeader";
import PlanGate from "@/components/dashboard/PlanGate";

function InventoryPageContent() {
  const t = useTranslations("inventoryPage");
  const tc = useTranslations("common");
  const { can } = useAuth();
  const { selectedBranchId } = useBranch();

  const [items, setItems] = useState<LoadState<InventoryItemOut[]>>(loadingState());
  const [createOpen, setCreateOpen] = useState(false);
  const [txTarget, setTxTarget] = useState<InventoryItemOut | null>(null);
  const [historyTarget, setHistoryTarget] = useState<InventoryItemOut | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const canManage = can("inventory.manage");

  const load = useCallback(async () => {
    try {
      const list = await inventoryApi.list(selectedBranchId ?? undefined);
      setItems(dataState(list));
    } catch (err) {
      setItems(errorState((err as Error).message));
    }
  }, [selectedBranchId]);

  useEffect(() => {
    void load();
  }, [load]);

  const flash = (message: string) => {
    setNotice(message);
    setTimeout(() => setNotice(null), 3000);
  };

  const handleCreate = async (payload: {
    name: string;
    unit: string;
    minimumQuantity: string;
    costPerUnit: string;
    supplier: string;
  }) => {
    if (!selectedBranchId) return;
    try {
      await inventoryApi.create({
        branch_id: selectedBranchId,
        name: payload.name,
        unit: payload.unit,
        minimum_quantity: payload.minimumQuantity || undefined,
        cost_per_unit: payload.costPerUnit || undefined,
        supplier: payload.supplier || null,
      });
      setCreateOpen(false);
      flash(tc("actions.saved"));
      load();
    } catch (err) {
      alert((err as Error).message);
    }
  };

  const handleTransaction = async (type: InventoryTransactionType, quantity: string, reason: string) => {
    if (!txTarget) return;
    try {
      await inventoryApi.addTransaction(txTarget.id, type, quantity, reason || undefined);
      setTxTarget(null);
      flash(tc("actions.saved"));
      load();
    } catch (err) {
      alert((err as Error).message);
    }
  };

  const list = items.type === "data" ? items.data : [];
  const lowStockCount = list.filter((i) => i.is_low_stock).length;

  return (
    <div>
      <PageHeader
        title={t("title")}
        description={t("description")}
        actions={
          canManage ? (
            <Button size="sm" onClick={() => setCreateOpen(true)} disabled={!selectedBranchId}>
              <Plus className="h-4 w-4" />
              {t("addItem")}
            </Button>
          ) : undefined
        }
      />

      {notice && (
        <div className="mb-4 rounded-lg border border-success/30 bg-success/10 px-4 py-2 text-sm text-success">
          {notice}
        </div>
      )}

      {lowStockCount > 0 && (
        <div className="mb-4 flex items-center gap-2 rounded-lg border border-error/30 bg-error/10 px-4 py-2 text-sm text-error">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          {t("lowStockWarning", { count: lowStockCount })}
        </div>
      )}

      {items.type === "data" ? (
        list.length === 0 ? (
          <StateView kind="empty" message={t("empty")} />
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {list.map((item) => (
              <div
                key={item.id}
                className={`flex flex-col rounded-xl border p-4 shadow-sm ${
                  item.is_low_stock ? "border-error/30 bg-error/[0.04]" : "border-border-default bg-surface"
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <p className="font-semibold text-text-primary">{item.name}</p>
                  {item.is_low_stock && (
                    <span className="rounded-full bg-error/10 px-2.5 py-1 text-xs font-semibold text-error">
                      {t("lowStock")}
                    </span>
                  )}
                </div>
                <p className="mt-1 text-2xl font-bold text-text-primary">
                  {item.quantity} <span className="text-sm font-normal text-text-secondary">{item.unit}</span>
                </p>
                <p className="text-xs text-text-secondary">
                  {t("minimum")}: {item.minimum_quantity} {item.unit}
                </p>
                {item.supplier && (
                  <p className="mt-1 text-xs text-text-secondary">{t("supplier")}: {item.supplier}</p>
                )}
                {canManage && (
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    <button
                      onClick={() => setTxTarget(item)}
                      className="flex items-center gap-1.5 rounded-lg border border-border-default px-2.5 py-1.5 text-xs font-medium text-text-primary hover:border-accent-primary hover:text-accent-primary"
                    >
                      <Settings2 className="h-3.5 w-3.5" />
                      {t("recordTransaction")}
                    </button>
                    <button
                      onClick={() => setHistoryTarget(item)}
                      className="flex items-center gap-1.5 rounded-lg border border-border-default px-2.5 py-1.5 text-xs font-medium text-text-primary hover:border-accent-primary hover:text-accent-primary"
                    >
                      <History className="h-3.5 w-3.5" />
                      {t("history")}
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )
      ) : (
        <StateView
          kind={items.type}
          message={items.type === "error" ? items.message : undefined}
          onRetry={items.type === "error" ? () => load() : undefined}
        />
      )}

      {createOpen && (
        <ItemFormModal onClose={() => setCreateOpen(false)} onSubmit={handleCreate} />
      )}
      {txTarget && (
        <TransactionModal item={txTarget} onClose={() => setTxTarget(null)} onSubmit={handleTransaction} />
      )}
      {historyTarget && (
        <HistoryModal item={historyTarget} onClose={() => setHistoryTarget(null)} />
      )}
    </div>
  );
}

function ItemFormModal({
  onClose,
  onSubmit,
}: {
  onClose: () => void;
  onSubmit: (payload: {
    name: string;
    unit: string;
    minimumQuantity: string;
    costPerUnit: string;
    supplier: string;
  }) => void;
}) {
  const t = useTranslations("inventoryPage");
  const tc = useTranslations("common");
  const [name, setName] = useState("");
  const [unit, setUnit] = useState("kg");
  const [minimumQuantity, setMinimumQuantity] = useState("0");
  const [costPerUnit, setCostPerUnit] = useState("0");
  const [supplier, setSupplier] = useState("");

  return (
    <Modal open onClose={onClose} title={t("addItem")}>
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          onSubmit({ name: name.trim(), unit: unit.trim(), minimumQuantity, costPerUnit, supplier: supplier.trim() });
        }}
      >
        <div>
          <label className="mb-1 block text-sm font-medium text-text-primary">{t("itemName")}</label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            placeholder={t("itemNamePlaceholder")}
            className="w-full rounded-lg border border-border-default bg-background px-3 py-2 text-sm text-text-primary outline-none focus:border-accent-primary"
          />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="mb-1 block text-sm font-medium text-text-primary">{t("unit")}</label>
            <input
              value={unit}
              onChange={(e) => setUnit(e.target.value)}
              required
              placeholder="kg"
              className="w-full rounded-lg border border-border-default bg-background px-3 py-2 text-sm text-text-primary outline-none focus:border-accent-primary"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-text-primary">{t("minimum")}</label>
            <input
              type="number"
              min={0}
              step="0.001"
              value={minimumQuantity}
              onChange={(e) => setMinimumQuantity(e.target.value)}
              className="w-full rounded-lg border border-border-default bg-background px-3 py-2 text-sm text-text-primary outline-none focus:border-accent-primary"
            />
          </div>
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-text-primary">{t("costPerUnit")}</label>
          <input
            type="number"
            min={0}
            step="0.01"
            value={costPerUnit}
            onChange={(e) => setCostPerUnit(e.target.value)}
            className="w-full rounded-lg border border-border-default bg-background px-3 py-2 text-sm text-text-primary outline-none focus:border-accent-primary"
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-text-primary">{t("supplier")}</label>
          <input
            value={supplier}
            onChange={(e) => setSupplier(e.target.value)}
            className="w-full rounded-lg border border-border-default bg-background px-3 py-2 text-sm text-text-primary outline-none focus:border-accent-primary"
          />
        </div>
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

function TransactionModal({
  item,
  onClose,
  onSubmit,
}: {
  item: InventoryItemOut;
  onClose: () => void;
  onSubmit: (type: InventoryTransactionType, quantity: string, reason: string) => void;
}) {
  const t = useTranslations("inventoryPage");
  const tc = useTranslations("common");
  const [type, setType] = useState<InventoryTransactionType>("IN");
  const [quantity, setQuantity] = useState("");
  const [reason, setReason] = useState("");

  return (
    <Modal open onClose={onClose} title={`${t("recordTransaction")} — ${item.name}`}>
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          onSubmit(type, quantity, reason.trim());
        }}
      >
        <div className="grid grid-cols-3 gap-2">
          <button
            type="button"
            onClick={() => setType("IN")}
            className={`flex flex-col items-center gap-1 rounded-lg border p-2.5 text-xs font-medium ${
              type === "IN" ? "border-success bg-success/10 text-success" : "border-border-default text-text-secondary"
            }`}
          >
            <ArrowDownCircle className="h-4 w-4" />
            {t("typeIn")}
          </button>
          <button
            type="button"
            onClick={() => setType("OUT")}
            className={`flex flex-col items-center gap-1 rounded-lg border p-2.5 text-xs font-medium ${
              type === "OUT" ? "border-error bg-error/10 text-error" : "border-border-default text-text-secondary"
            }`}
          >
            <ArrowUpCircle className="h-4 w-4" />
            {t("typeOut")}
          </button>
          <button
            type="button"
            onClick={() => setType("ADJUSTMENT")}
            className={`flex flex-col items-center gap-1 rounded-lg border p-2.5 text-xs font-medium ${
              type === "ADJUSTMENT" ? "border-accent-primary bg-accent-primary/10 text-accent-primary" : "border-border-default text-text-secondary"
            }`}
          >
            <Settings2 className="h-4 w-4" />
            {t("typeAdjustment")}
          </button>
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-text-primary">
            {type === "ADJUSTMENT" ? t("newQuantity") : t("quantity")} ({item.unit})
          </label>
          <input
            type="number"
            min={0}
            step="0.001"
            value={quantity}
            onChange={(e) => setQuantity(e.target.value)}
            required
            className="w-full rounded-lg border border-border-default bg-background px-3 py-2 text-sm text-text-primary outline-none focus:border-accent-primary"
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-text-primary">{t("reason")}</label>
          <input
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            className="w-full rounded-lg border border-border-default bg-background px-3 py-2 text-sm text-text-primary outline-none focus:border-accent-primary"
          />
        </div>
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

function HistoryModal({ item, onClose }: { item: InventoryItemOut; onClose: () => void }) {
  const t = useTranslations("inventoryPage");
  const [history, setHistory] = useState<InventoryTransactionOut[] | null>(null);

  useEffect(() => {
    inventoryApi.listTransactions(item.id).then(setHistory).catch(() => setHistory([]));
  }, [item.id]);

  return (
    <Modal open onClose={onClose} title={`${t("history")} — ${item.name}`}>
      {!history ? (
        <p className="text-sm text-text-secondary">{t("historyLoading")}</p>
      ) : history.length === 0 ? (
        <p className="text-sm text-text-secondary">{t("historyEmpty")}</p>
      ) : (
        <ul className="max-h-96 space-y-2 overflow-y-auto">
          {history.map((tx) => (
            <li
              key={tx.id}
              className="flex items-center justify-between rounded-lg border border-border-default px-3 py-2 text-sm"
            >
              <div>
                <p className="font-medium text-text-primary">
                  {t(`type${tx.type.charAt(0)}${tx.type.slice(1).toLowerCase()}`)}
                  {" "}— {tx.quantity} {item.unit}
                </p>
                {tx.reason && <p className="text-xs text-text-secondary">{tx.reason}</p>}
              </div>
              <span className="shrink-0 text-xs text-text-secondary">{formatDateTime(tx.created_at)}</span>
            </li>
          ))}
        </ul>
      )}
    </Modal>
  );
}

export default function InventoryPage() {
  return (
    <PlanGate feature="inventory">
      <InventoryPageContent />
    </PlanGate>
  );
}
