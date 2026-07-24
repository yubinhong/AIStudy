export function csrfHeaderFromCookie(cookie: string): Record<string, string> {
  const value = cookie
    .split("; ")
    .find((item) => item.startsWith("study_csrf="))
    ?.split("=")[1];
  return value ? { "X-CSRF-Token": decodeURIComponent(value) } : {};
}

export function csrfHeaders(): Record<string, string> {
  if (typeof document === "undefined") return {};
  return csrfHeaderFromCookie(document.cookie);
}
