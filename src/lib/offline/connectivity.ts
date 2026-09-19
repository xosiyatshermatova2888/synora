// Connectivity detection for the waiter app. `navigator.onLine` only reflects
// the device's network adapter state, not "can I actually reach the local
// server" — the real failure mode on a restaurant LAN (Wi-Fi up, server
// briefly unreachable, or vice versa). So this also pings the backend's
// public health endpoint on an interval and on the browser's own online event.

const HEALTH_PATH = "/api/v1/health";
const PING_INTERVAL_MS = 15000;

type Listener = (online: boolean) => void;

let online = typeof navigator === "undefined" ? true : navigator.onLine;
const listeners = new Set<Listener>();
let pingTimer: ReturnType<typeof setInterval> | null = null;
let started = false;

function setOnline(next: boolean) {
  if (next === online) return;
  online = next;
  listeners.forEach((l) => l(online));
}

async function ping(): Promise<void> {
  try {
    const res = await fetch(HEALTH_PATH, { cache: "no-store" });
    setOnline(res.ok);
  } catch {
    setOnline(false);
  }
}

export function isOnline(): boolean {
  return online;
}

/** Subscribe to online/offline transitions; returns an unsubscribe function. */
export function subscribeConnectivity(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** Idempotent — safe to call from every screen that cares about connectivity;
 * the underlying listeners/timer are only ever set up once. */
export function startConnectivityMonitor(): void {
  if (started || typeof window === "undefined") return;
  started = true;
  window.addEventListener("online", () => void ping());
  window.addEventListener("offline", () => setOnline(false));
  void ping();
  pingTimer = setInterval(() => void ping(), PING_INTERVAL_MS);
}

export function stopConnectivityMonitor(): void {
  if (pingTimer) clearInterval(pingTimer);
  pingTimer = null;
  started = false;
}
