function randomToken(): string {
  const cryptoApi = globalThis.crypto;
  if (cryptoApi?.getRandomValues) {
    const bytes = new Uint8Array(16);
    cryptoApi.getRandomValues(bytes);
    return Array.from(bytes, (value) =>
      value.toString(16).padStart(2, "0"),
    ).join("");
  }

  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
}

export function idempotencyKey(prefix: string): string {
  return `${prefix}-${randomToken()}`;
}
