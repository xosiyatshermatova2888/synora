// Thin IndexedDB wrapper for the waiter app's offline support. Two stores:
// `queue` (actions taken while offline, replayed on reconnect) and `cache`
// (last-known-good reads, served while offline). Deliberately never stores
// the access token here — see src/lib/api.ts's header comment.

import { openDB, type DBSchema, type IDBPDatabase } from "idb";

export interface QueueEntry {
  id: string;
  kind: "create_order";
  payload: unknown;
  idempotencyKey?: string;
  createdAt: number;
  attempts: number;
  lastError?: string;
}

interface CacheRow {
  key: string;
  value: unknown;
  savedAt: number;
}

interface SynoraOfflineDB extends DBSchema {
  queue: { key: string; value: QueueEntry };
  cache: { key: string; value: CacheRow };
}

const DB_NAME = "synora-waiter-offline";
const DB_VERSION = 1;

let dbPromise: Promise<IDBPDatabase<SynoraOfflineDB>> | null = null;

function getDB(): Promise<IDBPDatabase<SynoraOfflineDB>> {
  if (typeof indexedDB === "undefined") {
    return Promise.reject(new Error("IndexedDB unavailable in this environment."));
  }
  if (!dbPromise) {
    dbPromise = openDB<SynoraOfflineDB>(DB_NAME, DB_VERSION, {
      upgrade(db) {
        if (!db.objectStoreNames.contains("queue")) {
          db.createObjectStore("queue", { keyPath: "id" });
        }
        if (!db.objectStoreNames.contains("cache")) {
          db.createObjectStore("cache", { keyPath: "key" });
        }
      },
    });
  }
  return dbPromise;
}

export async function queuePut(entry: QueueEntry): Promise<void> {
  const db = await getDB();
  await db.put("queue", entry);
}

export async function queueAll(): Promise<QueueEntry[]> {
  const db = await getDB();
  return db.getAll("queue");
}

export async function queueRemove(id: string): Promise<void> {
  const db = await getDB();
  await db.delete("queue", id);
}

export async function cacheSet(key: string, value: unknown): Promise<void> {
  const db = await getDB();
  await db.put("cache", { key, value, savedAt: Date.now() });
}

export async function cacheGet<T>(key: string): Promise<T | null> {
  try {
    const db = await getDB();
    const row = await db.get("cache", key);
    return row ? (row.value as T) : null;
  } catch {
    return null;
  }
}
