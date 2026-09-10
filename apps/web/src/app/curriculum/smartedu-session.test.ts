import { describe, expect, it, vi } from "vitest";

import {
  clearSmartEduCredentials,
  clearSmartEduImport,
  getOrCreateSmartEduImportIdempotencyKey,
  readSmartEduCredentials,
  SMARTEDU_CREDENTIALS_STORAGE_KEY,
  SMARTEDU_IMPORT_STORAGE_KEY,
  SmartEduStorage,
  writeSmartEduCredentials,
} from "./smartedu-session";

function memoryStorage(): SmartEduStorage {
  const values = new Map<string, string>();
  return {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => void values.set(key, value),
    removeItem: (key) => void values.delete(key),
  };
}

describe("SmartEdu browser session storage", () => {
  it("stores credentials only in the supplied temporary storage and clears them", () => {
    const storage = memoryStorage();

    writeSmartEduCredentials('  {"access_token":"session-token"}  ', storage);

    expect(readSmartEduCredentials(storage)).toBe(
      '{"access_token":"session-token"}',
    );
    expect(storage.getItem(SMARTEDU_CREDENTIALS_STORAGE_KEY)).toBe(
      '{"access_token":"session-token"}',
    );

    clearSmartEduCredentials(storage);
    expect(readSmartEduCredentials(storage)).toBe("");
  });

  it("reuses a pending key for the same child and resource, then rotates it", () => {
    const storage = memoryStorage();
    const createKey = vi
      .fn<() => string>()
      .mockReturnValueOnce("web-smartedu-first")
      .mockReturnValueOnce("web-smartedu-second");

    expect(
      getOrCreateSmartEduImportIdempotencyKey(
        "child-1",
        "resource-1",
        storage,
        createKey,
      ),
    ).toBe("web-smartedu-first");
    expect(
      getOrCreateSmartEduImportIdempotencyKey(
        "child-1",
        "resource-1",
        storage,
        createKey,
      ),
    ).toBe("web-smartedu-first");
    expect(
      getOrCreateSmartEduImportIdempotencyKey(
        "child-1",
        "resource-2",
        storage,
        createKey,
      ),
    ).toBe("web-smartedu-second");
    expect(createKey).toHaveBeenCalledTimes(2);
    expect(storage.getItem(SMARTEDU_IMPORT_STORAGE_KEY)).not.toContain(
      "access_token",
    );

    clearSmartEduImport(storage);
    expect(storage.getItem(SMARTEDU_IMPORT_STORAGE_KEY)).toBeNull();
  });
});
