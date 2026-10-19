"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Plus, Trash2, Receipt } from "lucide-react";
import { ExpenseCategory, ExpenseOut, expensesApi } from "@/lib/api";
import { formatMoney, formatDate } from "@/lib/format";
import type { LoadState } from "@/lib/load-state";
import { loadingState, errorState, dataState } from "@/lib/load-state";
import { useAuth } from "@/lib/auth-context";
import { useBranch } from "@/lib/branch-context";
import Modal from "@/components/Modal";
import Button from "@/components/Button";
import StateView from "@/components/dashboard/StateView";
import PageHeader from "@/components/dashboard/PageHeader";

const CATEGORIES: ExpenseCategory[] = ["RENT", "SALARY", "PRODUCT", "UTILITIES", "OTHER"];

const CATEGORY_STYLES: Record<string, string> = {
  RENT: "bg-accent-primary/10 text-accent-primary",
  SALARY: "bg-accent-ai/10 text-accent-ai",
  PRODUCT: "bg-success/10 text-success",
  UTILITIES: "bg-warning/10 text-warning",
  OTHER: "bg-background-secondary text-text-secondary",
};

export default function ExpensesPage() {
  const t = useTranslations("expensesPage");
  const tc = useTranslations("common");
  const { can } = useAuth();
  const { selectedBranchId } = useBranch();

  const [expenses, setExpenses] = useState<LoadState<ExpenseOut[]>>(loadingState());
  const [categoryFilter, setCategoryFilter] = useState<string | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [currency] = useState("UZS");

  const canManage = can("finance.manage");

  const load = useCallback(async () => {
    try {
      const list = await expensesApi.list({
        branch_id: selectedBranchId ?? undefined,
        category: categoryFilter ?? undefined,
      });
      setExpenses(dataState(list));
    } catch (err) {
      setExpenses(errorState((err as Error).message));
    }
  }, [selectedBranchId, categoryFilter]);

  useEffect(() => {
    void load();
  }, [load]);

  const flash = (message: string) => {
    setNotice(message);
    setTimeout(() => setNotice(null), 3000);
  };

  const handleCreate = async (payload: {
    category: ExpenseCategory;
    amount: string;
    description: string;
    expenseDate: string;
  }) => {
    if (!selectedBranchId) return;
    try {
      await expensesApi.create({
        branch_id: selectedBranchId,
        category: payload.category,
        amount: payload.amount,
        description: payload.description || undefined,
        expense_date: payload.expenseDate,
      });
      setModalOpen(false);
      flash(tc("actions.saved"));
      load();
    } catch (err) {
      alert((err as Error).message);
    }
  };

  const handleDelete = async (expense: ExpenseOut) => {
    if (!window.confirm(t("confirmDelete"))) return;
    try {
      await expensesApi.delete(expense.id);
      flash(tc("actions.saved"));
      load();
    } catch (err) {
      alert((err as Error).message);
    }
  };

  const list = expenses.type === "data" ? expenses.data : [];
  const total = list.reduce((sum, e) => sum + parseFloat(e.amount), 0);

  return (
    <div>
      <PageHeader
        title={t("title")}
        description={t("description")}
        actions={
          canManage ? (
            <Button size="sm" onClick={() => setModalOpen(true)} disabled={!selectedBranchId}>
              <Plus className="h-4 w-4" />
              {t("addExpense")}
            </Button>
          ) : undefined
        }
      />

      {notice && (
        <div className="mb-4 rounded-lg border border-success/30 bg-success/10 px-4 py-2 text-sm text-success">
          {notice}
        </div>
      )}

      <div className="mb-5 flex flex-wrap items-center gap-2">
        <button
          onClick={() => setCategoryFilter(null)}
          className={`rounded-full px-3 py-1.5 text-xs font-semibold transition-colors ${
            categoryFilter === null
              ? "bg-accent-primary/10 text-accent-primary"
              : "bg-background-secondary text-text-secondary hover:text-text-primary"
          }`}
        >
          {t("filterAll")}
        </button>
        {CATEGORIES.map((cat) => (
          <button
            key={cat}
            onClick={() => setCategoryFilter(cat)}
            className={`rounded-full px-3 py-1.5 text-xs font-semibold transition-colors ${
              categoryFilter === cat
                ? "bg-accent-primary/10 text-accent-primary"
                : "bg-background-secondary text-text-secondary hover:text-text-primary"
            }`}
          >
            {tc(`expenseCategory.${cat}`)}
          </button>
        ))}
      </div>

      {expenses.type === "data" ? (
        list.length === 0 ? (
          <StateView kind="empty" message={t("empty")} />
        ) : (
          <div className="overflow-hidden rounded-xl border border-border-default bg-surface">
            <div className="flex items-center justify-between border-b border-border-default px-5 py-3">
              <span className="text-sm text-text-secondary">{t("total")}</span>
              <span className="text-base font-bold text-text-primary">
                {formatMoney(total.toFixed(2), currency)}
              </span>
            </div>
            <ul className="divide-y divide-border-default">
              {list.map((expense) => (
                <li key={expense.id} className="flex items-center gap-3 px-5 py-4">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-background-secondary text-text-secondary">
                    <Receipt className="h-4 w-4" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-medium text-text-primary">
                      {expense.description || tc(`expenseCategory.${expense.category}`)}
                    </p>
                    <p className="text-xs text-text-secondary">{formatDate(expense.expense_date)}</p>
                  </div>
                  <span
                    className={`rounded-full px-2.5 py-1 text-xs font-semibold ${CATEGORY_STYLES[expense.category] ?? "bg-background-secondary text-text-secondary"}`}
                  >
                    {tc(`expenseCategory.${expense.category}`)}
                  </span>
                  <span className="font-semibold text-text-primary">
                    {formatMoney(expense.amount, currency)}
                  </span>
                  {canManage && (
                    <button
                      onClick={() => handleDelete(expense)}
                      className="text-text-secondary hover:text-error"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )
      ) : (
        <StateView
          kind={expenses.type}
          message={expenses.type === "error" ? expenses.message : undefined}
          onRetry={expenses.type === "error" ? () => load() : undefined}
        />
      )}

      {modalOpen && (
        <ExpenseFormModal onClose={() => setModalOpen(false)} onSubmit={handleCreate} />
      )}
    </div>
  );
}

function ExpenseFormModal({
  onClose,
  onSubmit,
}: {
  onClose: () => void;
  onSubmit: (payload: {
    category: ExpenseCategory;
    amount: string;
    description: string;
    expenseDate: string;
  }) => void;
}) {
  const t = useTranslations("expensesPage");
  const tc = useTranslations("common");
  const [category, setCategory] = useState<ExpenseCategory>("OTHER");
  const [amount, setAmount] = useState("");
  const [description, setDescription] = useState("");
  const [expenseDate, setExpenseDate] = useState(() => new Date().toISOString().slice(0, 10));

  return (
    <Modal open onClose={onClose} title={t("addExpense")}>
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          onSubmit({ category, amount, description: description.trim(), expenseDate });
        }}
      >
        <div>
          <label className="mb-1 block text-sm font-medium text-text-primary">{t("category")}</label>
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value as ExpenseCategory)}
            className="w-full rounded-lg border border-border-default bg-background px-3 py-2 text-sm text-text-primary outline-none focus:border-accent-primary"
          >
            {CATEGORIES.map((cat) => (
              <option key={cat} value={cat}>
                {tc(`expenseCategory.${cat}`)}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-text-primary">{t("amount")}</label>
          <input
            type="number"
            min={0}
            step="0.01"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            required
            className="w-full rounded-lg border border-border-default bg-background px-3 py-2 text-sm text-text-primary outline-none focus:border-accent-primary"
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-text-primary">{t("expenseDate")}</label>
          <input
            type="date"
            value={expenseDate}
            onChange={(e) => setExpenseDate(e.target.value)}
            required
            className="w-full rounded-lg border border-border-default bg-background px-3 py-2 text-sm text-text-primary outline-none focus:border-accent-primary"
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-text-primary">{t("descriptionField")}</label>
          <input
            value={description}
            onChange={(e) => setDescription(e.target.value)}
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
