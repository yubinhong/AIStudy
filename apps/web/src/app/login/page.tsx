"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError(null);
    const response = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ username, password, client: "web" }),
    });
    setPending(false);
    if (!response.ok) {
      setError("用户名或密码不正确");
      return;
    }
    const result = (await response.json()) as {
      account?: { must_change_password?: boolean };
    };
    router.push(result.account?.must_change_password ? "/first-password" : "/");
    router.refresh();
  }

  return (
    <main className="auth-shell">
      <section className="auth-card" aria-labelledby="login-heading">
        <p className="eyebrow">家庭 AI 学习助手</p>
        <h1 id="login-heading">欢迎回来</h1>
        <p className="auth-copy">登录后继续查看家庭学习进度。</p>
        <form onSubmit={submit} className="auth-form">
          <label>
            用户名
            <input
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              autoComplete="username"
              required
            />
          </label>
          <label>
            密码
            <input
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              type="password"
              autoComplete="current-password"
              required
            />
          </label>
          {error ? (
            <p className="auth-error" role="alert">
              {error}
            </p>
          ) : null}
          <button className="primary-button" type="submit" disabled={pending}>
            {pending ? "登录中…" : "登录"}
          </button>
        </form>
      </section>
    </main>
  );
}
