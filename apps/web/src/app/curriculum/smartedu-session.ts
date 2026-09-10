import { idempotencyKey } from "../../lib/idempotency-key";

export const SMARTEDU_CREDENTIALS_STORAGE_KEY =
  "aistudy.smartedu.credentials.v1";
export const SMARTEDU_IMPORT_STORAGE_KEY = "aistudy.smartedu.import.v1";
const MAX_CREDENTIALS_LENGTH = 8192;
const MAX_IDENTITY_LENGTH = 120;
const MAX_IDEMPOTENCY_KEY_LENGTH = 128;

export type SmartEduStorage = Pick<
  Storage,
  "getItem" | "setItem" | "removeItem"
>;

type PendingSmartEduImport = {
  childId: string;
  resourceId: string;
  idempotencyKey: string;
};

function browserSessionStorage(): SmartEduStorage | null {
  if (typeof window === "undefined") return null;
  try {
    return window.sessionStorage;
  } catch {
    return null;
  }
}

function isBoundedString(value: unknown, maxLength: number): value is string {
  return (
    typeof value === "string" && value.length > 0 && value.length <= maxLength
  );
}

function readValue(
  storage: SmartEduStorage | null,
  key: string,
): string | null {
  if (!storage) return null;
  try {
    return storage.getItem(key);
  } catch {
    return null;
  }
}

function writeValue(
  storage: SmartEduStorage | null,
  key: string,
  value: string,
): void {
  if (!storage) return;
  try {
    storage.setItem(key, value);
  } catch {
    // Private browsing and storage quotas must not block textbook loading.
  }
}

function removeValue(storage: SmartEduStorage | null, key: string): void {
  if (!storage) return;
  try {
    storage.removeItem(key);
  } catch {
    // Storage is an optional convenience, not part of the import contract.
  }
}

export function readSmartEduCredentials(
  storage: SmartEduStorage | null = browserSessionStorage(),
): string {
  const value = readValue(storage, SMARTEDU_CREDENTIALS_STORAGE_KEY);
  return isBoundedString(value, MAX_CREDENTIALS_LENGTH) ? value : "";
}

export function writeSmartEduCredentials(
  value: string,
  storage: SmartEduStorage | null = browserSessionStorage(),
): void {
  const trimmed = value.trim();
  if (!trimmed) {
    removeValue(storage, SMARTEDU_CREDENTIALS_STORAGE_KEY);
    return;
  }
  if (trimmed.length <= MAX_CREDENTIALS_LENGTH) {
    writeValue(storage, SMARTEDU_CREDENTIALS_STORAGE_KEY, trimmed);
  }
}

export function clearSmartEduCredentials(
  storage: SmartEduStorage | null = browserSessionStorage(),
): void {
  removeValue(storage, SMARTEDU_CREDENTIALS_STORAGE_KEY);
}

function readPendingSmartEduImport(
  storage: SmartEduStorage | null,
): PendingSmartEduImport | null {
  const raw = readValue(storage, SMARTEDU_IMPORT_STORAGE_KEY);
  if (!raw) return null;
  try {
    const value: unknown = JSON.parse(raw);
    if (!value || typeof value !== "object") return null;
    const pending = value as Record<string, unknown>;
    if (
      !isBoundedString(pending.childId, MAX_IDENTITY_LENGTH) ||
      !isBoundedString(pending.resourceId, MAX_IDENTITY_LENGTH) ||
      !isBoundedString(pending.idempotencyKey, MAX_IDEMPOTENCY_KEY_LENGTH)
    ) {
      return null;
    }
    return {
      childId: pending.childId,
      resourceId: pending.resourceId,
      idempotencyKey: pending.idempotencyKey,
    };
  } catch {
    return null;
  }
}

function writePendingSmartEduImport(
  pending: PendingSmartEduImport,
  storage: SmartEduStorage | null,
): void {
  writeValue(storage, SMARTEDU_IMPORT_STORAGE_KEY, JSON.stringify(pending));
}

export function getOrCreateSmartEduImportIdempotencyKey(
  childId: string,
  resourceId: string,
  storage: SmartEduStorage | null = browserSessionStorage(),
  createKey: () => string = () => idempotencyKey("web-curriculum-smartedu"),
): string {
  const pending = readPendingSmartEduImport(storage);
  if (pending?.childId === childId && pending.resourceId === resourceId) {
    return pending.idempotencyKey;
  }
  const key = createKey();
  writePendingSmartEduImport(
    { childId, resourceId, idempotencyKey: key },
    storage,
  );
  return key;
}

export function clearSmartEduImport(
  storage: SmartEduStorage | null = browserSessionStorage(),
): void {
  removeValue(storage, SMARTEDU_IMPORT_STORAGE_KEY);
}
