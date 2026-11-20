"use client";
// Saved progress in IndexedDB, per page AND per person (shared phones!).
// Every function swallows storage errors: the app must still work without IndexedDB.
import { openDB, type DBSchema, type IDBPDatabase } from "idb";

interface Schema extends DBSchema {
  progress: { key: string; value: { key: string; page: string; personId: string; data: unknown; savedAt: number } };
}

let dbPromise: Promise<IDBPDatabase<Schema>> | null = null;

function db() {
  if (!dbPromise) {
    dbPromise = openDB<Schema>("bharosa", 1, {
      upgrade(d) {
        d.createObjectStore("progress", { keyPath: "key" });
      },
    });
  }
  return dbPromise;
}

const k = (page: string, personId: string) => `${page}::${personId}`;

export async function saveProgress<T>(page: string, personId: string, data: T): Promise<boolean> {
  try {
    await (await db()).put("progress", { key: k(page, personId), page, personId, data, savedAt: Date.now() });
    return true;
  } catch {
    return false;
  }
}

export async function loadProgress<T>(page: string, personId: string): Promise<{ data: T; savedAt: number } | null> {
  try {
    const row = await (await db()).get("progress", k(page, personId));
    return row ? { data: row.data as T, savedAt: row.savedAt } : null;
  } catch {
    return null;
  }
}

export async function clearProgress(page: string, personId: string): Promise<void> {
  try {
    await (await db()).delete("progress", k(page, personId));
  } catch {
    /* ignore */
  }
}
