"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Printer, Plus, Pencil, Trash2, Send, RotateCcw, Copy, KeyRound } from "lucide-react";
import {
  AgentStatus,
  BranchOut,
  PrinterCreate,
  PrinterMode,
  PrinterOut,
  PrinterRole,
  PrintJobOut,
  printersApi,
  printJobsApi,
} from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { useBranch } from "@/lib/branch-context";
import Button from "@/components/Button";
import Modal from "@/components/Modal";
import ConfirmDialog from "@/components/ui/ConfirmDialog";
import StatusBadge, { Tone } from "@/components/ui/StatusBadge";
import { useToast } from "@/components/ui/Toast";

const ROLES: PrinterRole[] = ["KITCHEN", "RECEIPT"];
const JOB_TONE: Record<PrintJobOut["status"], Tone> = { PRINTED: "success", PENDING: "warning", FAILED: "error" };

type FormState = { branchId: string; role: PrinterRole; printer: PrinterOut | null } | null;

export default function PrintersSettings() {
  const t = useTranslations("printersSettings");
  const tc = useTranslations("common");
  const toast = useToast();
  const { branches } = useBranch();

  const [printers, setPrinters] = useState<PrinterOut[]>([]);
  const [jobs, setJobs] = useState<PrintJobOut[]>([]);
  const [form, setForm] = useState<FormState>(null);
  const [confirmDelete, setConfirmDelete] = useState<PrinterOut | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [agents, setAgents] = useState<Record<string, AgentStatus>>({});
  const [issuedToken, setIssuedToken] = useState<string | null>(null);

  const load = useCallback(async () => {
    const [p, j] = await Promise.all([printersApi.list().catch(() => []), printJobsApi.list(15).catch(() => [])]);
    setPrinters(p);
    setJobs(j);
    // Agent status only matters for branches that use an agent printer.
    const agentBranches = [...new Set(p.filter((x) => x.mode === "AGENT").map((x) => x.branch_id))];
    const entries = await Promise.all(
      agentBranches.map(async (id) => [id, await printersApi.agentStatus(id).catch(() => null)] as const)
    );
    setAgents(Object.fromEntries(entries.filter((e): e is readonly [string, AgentStatus] => e[1] !== null)));
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const printerFor = (branchId: string, role: PrinterRole) =>
    printers.find((p) => p.branch_id === branchId && p.role === role) ?? null;

  const reportJob = (job: PrintJobOut, okMessage: string) => {
    if (job.status === "PRINTED") toast.success(okMessage);
    else if (job.status === "PENDING") toast.info(t("queued"));
    else toast.error(`${t("printFailed")}: ${job.error ?? ""}`);
  };

  const runTest = async (printer: PrinterOut) => {
    setBusyId(printer.id);
    try {
      reportJob(await printersApi.test(printer.id), t("testOk"));
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setBusyId(null);
      void load();
    }
  };

  const retry = async (job: PrintJobOut) => {
    setBusyId(job.id);
    try {
      reportJob(await printJobsApi.retry(job.id), t("retryOk"));
    } catch (err) {
      toast.error((err as Error).message);
    } finally {
      setBusyId(null);
      void load();
    }
  };

  const issueToken = async (branchId: string) => {
    try {
      const { token } = await printersApi.rotateAgentToken(branchId);
      setIssuedToken(token);
      void load();
    } catch (err) {
      toast.error((err as Error).message);
    }
  };

  const remove = async () => {
    if (!confirmDelete) return;
    try {
      await printersApi.remove(confirmDelete.id);
      toast.success(tc("actions.saved"));
      setConfirmDelete(null);
      void load();
    } catch (err) {
      toast.error((err as Error).message);
    }
  };

  return (
    <section className="rounded-xl border border-border-default bg-surface p-5 shadow-card">
      <div className="mb-4 flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent-primary/10 text-accent-primary">
          <Printer className="h-5 w-5" />
        </div>
        <div>
          <p className="font-semibold text-text-primary">{t("title")}</p>
          <p className="text-xs text-text-secondary">{t("description")}</p>
        </div>
      </div>

      <div className="space-y-4">
        {branches.map((branch: BranchOut) => (
          <div key={branch.id} className="rounded-lg border border-border-default">
            <p className="border-b border-border-default px-4 py-2 text-sm font-semibold text-text-primary">
              {branch.name}
            </p>
            <ul className="divide-y divide-border-default">
              {ROLES.map((role) => {
                const printer = printerFor(branch.id, role);
                return (
                  <li key={role} className="flex flex-wrap items-center gap-3 px-4 py-3">
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-text-primary">{t(`role.${role}`)}</p>
                      {printer ? (
                        <p className="tabular text-xs text-text-secondary">
                          {printer.name} · {printer.host === "local" ? t("usbLabel") : `${printer.host}:${printer.port}`} · {printer.paper_width}mm
                          {printer.mode === "AGENT" ? ` · ${t("agentTag")}` : ""}
                          {role === "RECEIPT" && printer.auto_print_receipt ? ` · ${t("autoOn")}` : ""}
                          {role === "RECEIPT" && printer.auto_print_orders ? ` · ${t("autoOrdersOn")}` : ""}
                          {!printer.is_active ? ` · ${t("inactive")}` : ""}
                        </p>
                      ) : (
                        <p className="text-xs text-text-secondary">{t("notConfigured")}</p>
                      )}
                    </div>
                    {printer ? (
                      <div className="flex items-center gap-1.5">
                        <Button size="sm" variant="secondary" loading={busyId === printer.id} onClick={() => runTest(printer)}>
                          <Send className="h-3.5 w-3.5" />
                          {t("test")}
                        </Button>
                        <Button size="icon" variant="ghost" aria-label={t("edit")} onClick={() => setForm({ branchId: branch.id, role, printer })}>
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button size="icon" variant="ghost" aria-label={t("delete")} onClick={() => setConfirmDelete(printer)}>
                          <Trash2 className="h-4 w-4 text-error" />
                        </Button>
                      </div>
                    ) : (
                      <Button size="sm" onClick={() => setForm({ branchId: branch.id, role, printer: null })}>
                        <Plus className="h-4 w-4" />
                        {t("add")}
                      </Button>
                    )}
                  </li>
                );
              })}
            </ul>
            {agents[branch.id] !== undefined && (
              <AgentRow status={agents[branch.id]} onIssue={() => void issueToken(branch.id)} />
            )}
          </div>
        ))}
      </div>

      <div className="mt-6">
        <p className="mb-2 text-sm font-semibold text-text-primary">{t("jobsTitle")}</p>
        {jobs.length === 0 ? (
          <p className="text-sm text-text-secondary">{t("noJobs")}</p>
        ) : (
          <ul className="divide-y divide-border-default rounded-lg border border-border-default">
            {jobs.map((job) => (
              <li key={job.id} className="flex flex-wrap items-center gap-3 px-4 py-2.5 text-sm">
                <span className="tabular w-36 text-xs text-text-secondary">{formatDateTime(job.created_at)}</span>
                <span className="font-medium text-text-primary">{t(`kind.${job.kind}`)}</span>
                <StatusBadge tone={JOB_TONE[job.status]}>{t(`status.${job.status}`)}</StatusBadge>
                {job.error && <span className="min-w-0 flex-1 truncate text-xs text-error" title={job.error}>{job.error}</span>}
                {job.status === "FAILED" && (
                  <Button size="sm" variant="secondary" className="ml-auto" loading={busyId === job.id} onClick={() => retry(job)}>
                    <RotateCcw className="h-3.5 w-3.5" />
                    {t("retry")}
                  </Button>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>

      <AgentTokenModal token={issuedToken} onClose={() => setIssuedToken(null)} />

      {form && (
        <PrinterFormModal
          state={form}
          onClose={() => setForm(null)}
          onSaved={() => {
            setForm(null);
            toast.success(tc("actions.saved"));
            void load();
          }}
        />
      )}

      <ConfirmDialog
        open={confirmDelete !== null}
        title={t("delete")}
        message={t("confirmDelete")}
        confirmLabel={tc("actions.delete")}
        onConfirm={() => void remove()}
        onClose={() => setConfirmDelete(null)}
      />
    </section>
  );
}

function PrinterFormModal({
  state,
  onClose,
  onSaved,
}: {
  state: NonNullable<FormState>;
  onClose: () => void;
  onSaved: () => void;
}) {
  const t = useTranslations("printersSettings");
  const tc = useTranslations("common");
  const { printer, role, branchId } = state;

  const [name, setName] = useState(printer?.name ?? t(`role.${role}`));
  const [host, setHost] = useState(printer && printer.host !== "local" ? printer.host : "");
  const [port, setPort] = useState(String(printer?.port ?? 9100));
  const [paper, setPaper] = useState<58 | 80>(printer?.paper_width ?? 80);
  const [auto, setAuto] = useState(printer?.auto_print_receipt ?? false);
  const [autoOrders, setAutoOrders] = useState(printer?.auto_print_orders ?? false);
  const [active, setActive] = useState(printer?.is_active ?? true);
  const [mode, setMode] = useState<PrinterMode>(printer?.mode ?? "DIRECT");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const body = {
        name: name.trim(),
        host: host.trim(),
        port: Number(port) || 9100,
        paper_width: paper,
        is_active: active,
        auto_print_receipt: role === "RECEIPT" ? auto : false,
        auto_print_orders: role === "RECEIPT" ? autoOrders : false,
        mode,
      };
      if (printer) await printersApi.update(printer.id, body);
      else await printersApi.create({ branch_id: branchId, role, ...body } as PrinterCreate);
      onSaved();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const field = "w-full rounded-lg border border-border-default bg-background px-3 py-2 text-sm text-text-primary outline-none focus:border-accent-primary";

  return (
    <Modal open onClose={onClose} title={`${t(`role.${role}`)} — ${printer ? t("edit") : t("add")}`}>
      <form onSubmit={submit} className="space-y-4">
        <label className="block text-sm font-medium text-text-primary">
          {t("name")}
          <input value={name} onChange={(e) => setName(e.target.value)} required className={`mt-1 ${field}`} />
        </label>
        <div className="grid grid-cols-[1fr_96px] gap-3">
          <label className="block text-sm font-medium text-text-primary">
            {t("ip")}
            <input
              value={host}
              onChange={(e) => setHost(e.target.value)}
              placeholder={mode === "AGENT" ? t("ipPlaceholderAgent") : "192.168.1.50"}
              inputMode="decimal"
              required={mode === "DIRECT"}
              className={`mt-1 ${field}`}
            />
          </label>
          <label className="block text-sm font-medium text-text-primary">
            {t("port")}
            <input value={port} onChange={(e) => setPort(e.target.value)} inputMode="numeric" className={`mt-1 ${field}`} />
          </label>
        </div>
        <p className="-mt-2 text-xs text-text-secondary">{mode === "AGENT" ? t("ipHintAgent") : t("ipHint")}</p>
        <label className="block text-sm font-medium text-text-primary">
          {t("mode")}
          <select value={mode} onChange={(e) => setMode(e.target.value as PrinterMode)} className={`mt-1 ${field}`}>
            <option value="DIRECT">{t("modeDirect")}</option>
            <option value="AGENT">{t("modeAgent")}</option>
          </select>
        </label>
        <p className="-mt-2 text-xs text-text-secondary">{t("modeHint")}</p>
        <label className="block text-sm font-medium text-text-primary">
          {t("paperWidth")}
          <select value={paper} onChange={(e) => setPaper(Number(e.target.value) as 58 | 80)} className={`mt-1 ${field}`}>
            <option value={80}>80 mm</option>
            <option value={58}>58 mm</option>
          </select>
        </label>
        {role === "RECEIPT" && (
          <label className="flex items-center gap-2 text-sm text-text-primary">
            <input type="checkbox" checked={auto} onChange={(e) => setAuto(e.target.checked)} />
            {t("autoPrintReceipt")}
          </label>
        )}
        {role === "RECEIPT" && (
          <label className="flex items-center gap-2 text-sm text-text-primary">
            <input type="checkbox" checked={autoOrders} onChange={(e) => setAutoOrders(e.target.checked)} />
            {t("autoPrintOrders")}
          </label>
        )}
        {printer && (
          <label className="flex items-center gap-2 text-sm text-text-primary">
            <input type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} />
            {t("activeLabel")}
          </label>
        )}
        {error && <p className="text-sm text-error">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button variant="secondary" size="sm" type="button" onClick={onClose}>
            {tc("actions.cancel")}
          </Button>
          <Button size="sm" type="submit" loading={saving}>
            {tc("actions.save")}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

function AgentRow({ status, onIssue }: { status: AgentStatus; onIssue: () => void }) {
  const t = useTranslations("printersSettings.agent");
  return (
    <div className="flex flex-wrap items-center gap-3 border-t border-border-default bg-background-secondary/50 px-4 py-2.5">
      <KeyRound className="h-4 w-4 text-text-secondary" aria-hidden="true" />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-text-primary">{t("title")}</p>
        <p className={`text-xs ${status.online ? "text-success" : "text-text-secondary"}`}>
          {!status.configured ? t("notSet") : status.online ? t("online") : t("offline")}
          {status.last_seen_at ? ` · ${t("lastSeen")}: ${formatDateTime(status.last_seen_at)}` : ""}
        </p>
      </div>
      <Button size="sm" variant="secondary" onClick={onIssue}>
        {status.configured ? t("rotate") : t("create")}
      </Button>
    </div>
  );
}

function AgentTokenModal({ token, onClose }: { token: string | null; onClose: () => void }) {
  const t = useTranslations("printersSettings.agent");
  const toast = useToast();
  const command = token
    ? `python print_agent.py --server ${typeof window !== "undefined" ? window.location.origin : ""} --token ${token}`
    : "";
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(token ?? "");
      toast.success(t("copied"));
    } catch {
      // clipboard blocked: the token is still visible
    }
  };
  return (
    <Modal open={token !== null} onClose={onClose} title={t("tokenTitle")}>
      <div className="space-y-3">
        <p className="rounded-lg border border-warning/40 bg-warning/10 p-3 text-sm text-text-primary">{t("tokenWarning")}</p>
        <div className="flex items-center gap-2">
          <code className="min-w-0 flex-1 break-all rounded-lg bg-background-secondary p-3 text-xs text-text-primary">{token}</code>
          <Button size="sm" variant="secondary" onClick={() => void copy()}>
            <Copy className="h-4 w-4" aria-hidden="true" />
            {t("copy")}
          </Button>
        </div>
        <p className="text-sm text-text-secondary">{t("command")}</p>
        <code className="block break-all rounded-lg bg-background-secondary p-3 text-xs text-text-primary">{command}</code>
        <div className="flex justify-end">
          <Button size="sm" onClick={onClose}>
            {t("close")}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
