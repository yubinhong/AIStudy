"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

export default function FirstPasswordPage() {
  const router = useRouter();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError(null);
    const csrf = document.cookie
      .split("; ")
      .find((value) => value.startsWith("study_csrf="))
      ?.split("=")[1];
    const response = await fetch("/api/auth/change-password", {
      method: "POST",
      headers: {
        "content-type": "application/json",
        ...(csrf ? { "X-CSRF-Token": decodeURIComponent(csrf) } : {}),
      },
      body: JSON.stringify({
        current_password: currentPassword,
        new_password: newPassword,
      }),
    });
    setPending(false);
    if (!response.ok) {
      setError("密码不符合要求，或当前密码不正确");
      return;
    }
    router.push("/");
    router.refresh();
  }

  return (
    <main className="auth-shell">
      <section className="auth-card" aria-labelledby="password-heading">
        <p className="eyebrow">首次登录</p>
        <h1 id="password-heading">先设置新密码</h1>
        <p className="auth-copy">设置完成后，家庭数据才会开放。</p>
        <form onSubmit={submit} className="auth-form">
          <label>
            当前密码
            <input
              value={currentPassword}
              onChange={(event) => setCurrentPassword(event.target.value)}
              type="password"
              autoComplete="current-password"
              required
            />
          </label>
          <label>
            新密码（至少 12 位）
            <input
              value={newPassword}
              onChange={(event) => setNewPassword(event.target.value)}
              type="password"
              autoComplete="new-password"
              minLength={12}
              required
            />
          </label>
          {error ? (
            <p className="auth-error" role="alert">
              {error}
            </p>
          ) : null}
          <button className="primary-button" type="submit" disabled={pending}>
            {pending ? "保存中…" : "保存新密码"}
          </button>
        </form>
      </section>
    </main>
  );
}
