const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function createChildAccountIdempotencyKey(): string {
  return `web-child-${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
}

export function isUuid(value: string): boolean {
  return UUID_PATTERN.test(value.trim());
}

export function childAccountCreationMessage(
  status: number,
  apiMessage?: string,
): string {
  if (status >= 200 && status < 300) return "孩子账号已创建";
  if (status === 409 && apiMessage === "username already exists") {
    return "用户名已存在，请在上方账号列表中管理现有账号，或更换用户名。";
  }
  return "创建失败，请检查用户名、密码和绑定的孩子档案";
}
