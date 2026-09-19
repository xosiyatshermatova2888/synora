// Offline action queue + replay engine for the waiter app. v1 scope: only
// order CREATION is queued while offline — it's the one thing that must
// never be lost, and it's the one write that's safe to blindly retry (the
// backend dedupes on the idempotency key, see
// backend/app/services/orders.py::create_order). Status updates and reads
// simply go stale until reconnect rather than being queued.

import { queuePut, queueAll, queueRemove, type QueueEntry } from "./db";
import { ordersApi, OfflineError, type OrderCreate } from "@/lib/api";

type QueueListener = (pending: QueueEntry[]) => void;
const listeners = new Set<QueueListener>();

async function notify(): Promise<void> {
  const pending = await queueAll();
  listeners.forEach((l) => l(pending));
}

/** Subscribe to the pending queue; fires immediately with the current state. */
export function subscribeQueue(listener: QueueListener): () => void {
  listeners.add(listener);
  void queueAll().then(listener);
  return () => listeners.delete(listener);
}

export async function enqueueCreateOrder(
  payload: OrderCreate,
  idempotencyKey: string
): Promise<void> {
  const entry: QueueEntry = {
    id: idempotencyKey,
    kind: "create_order",
    payload,
    idempotencyKey,
    createdAt: Date.now(),
    attempts: 0,
  };
  await queuePut(entry);
  await notify();
}

let draining = false;

/** Replay queued actions in submission order. Stops early on the first sign
 * we're still offline (no point trying the rest); a genuine server-side
 * rejection (e.g. a product no longer available) stays queued with the
 * error attached rather than being silently dropped — it needs a human. */
export async function drainQueue(): Promise<void> {
  if (draining) return;
  draining = true;
  try {
    const entries = (await queueAll()).sort((a, b) => a.createdAt - b.createdAt);
    for (const entry of entries) {
      try {
        if (entry.kind === "create_order") {
          await ordersApi.create(entry.payload as OrderCreate, entry.idempotencyKey);
        }
        await queueRemove(entry.id);
      } catch (err) {
        entry.attempts += 1;
        entry.lastError = err instanceof Error ? err.message : String(err);
        await queuePut(entry);
        if (err instanceof OfflineError) break;
      }
    }
  } finally {
    draining = false;
    await notify();
  }
}
