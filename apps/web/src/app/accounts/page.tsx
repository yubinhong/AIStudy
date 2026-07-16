"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";

type Account = {
  id: string;
  username: string;
  role: "parent" | "child";
  child_id: string | null;
  status: "active" | "disabled";
  must_change_password: boolean;
};

function csrfToken() {
  return document.cookie
    .split("; ")
    .find((value) => value.startsWith("study_csrf="))
    ?.split("=")[1];
}

export default function AccountsPage() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [childId, setChildId] = useState("");
  const [message, setMessage] = useState<string | null>(null);

  async function load() {
    const response = await fetch("/api/auth/accounts", { cache: "no-store" });
    if (response.ok) setAccounts((await response.json()) as Account[]);
  }

  useEffect(() => {
    let active = true;
    fetch("/api/auth/accounts", { cache: "no-store" })
      .then((response) => (response.ok ? response.json() : []))
      .then((result: Account[]) => {
        if (active) setAccounts(result);
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, []);

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const response = await fetch("/api/auth/accounts", {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "Idempotency-Key": `web-child-${username}-${childId}`,
        ...(csrfToken()
          ? { "X-CSRF-Token": decodeURIComponent(csrfToken()!) }
          : {}),
      },
      body: JSON.stringify({ username, password, child_id: childId }),
    });
    setMessage(
      response.ok ? "孩子账号已创建" : "创建失败，请检查用户名、密码和孩子 ID",
    );
    if (response.ok) {
      setUsername("");
      setPassword("");
      setChildId("");
      await load();
    }
  }

  async function toggle(account: Account) {
    const currentPassword = window.prompt("请输入当前家长密码以确认此操作");
    if (!currentPassword) return;
    const response = await fetch(`/api/auth/accounts/${account.id}/status`, {
      method: "PATCH",
      headers: {
        "content-type": "application/json",
        ...(csrfToken()
          ? { "X-CSRF-Token": decodeURIComponent(csrfToken()!) }
          : {}),
      },
      body: JSON.stringify({
        enabled: account.status !== "active",
        current_password: currentPassword,
      }),
    });
    if (response.ok) await load();
  }

  async function resetPassword(account: Account) {
    const currentPassword = window.prompt("请输入当前家长密码以确认重置");
    if (!currentPassword) return;
    const nextPassword = window.prompt(
      `为 ${account.username} 设置新密码（至少 8 位）`,
    );
    if (!nextPassword) return;
    if (nextPassword.length < 8) {
      setMessage("新密码至少需要 8 位");
      return;
    }
    const response = await fetch(
      `/api/auth/accounts/${account.id}/reset-password`,
      {
        method: "POST",
        headers: {
          "content-type": "application/json",
          ...(csrfToken()
            ? { "X-CSRF-Token": decodeURIComponent(csrfToken()!) }
            : {}),
        },
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: nextPassword,
        }),
      },
    );
    setMessage(response.ok ? "密码已重置，旧会话已失效" : "密码重置失败");
  }

  return (
    <main className="shell">
      <header className="topbar">
        <Link className="brand" href="/">
          家庭 AI 学习助手
        </Link>
        <Link className="text-button" href="/">
          返回概览
        </Link>
      </header>
      <section className="hero">
        <div>
          <p className="eyebrow">家长设置</p>
          <h1>孩子账号</h1>
          <p className="hero-copy">账号只绑定本家庭中的一个孩子。</p>
        </div>
      </section>
      <section className="content-grid">
        <article className="panel">
          <div className="panel-heading">
            <div>
              <p className="section-kicker">已创建</p>
              <h2>家庭账号</h2>
            </div>
          </div>
          {accounts.map((account) => (
            <div className="task-row" key={account.id}>
              <div className="task-details">
                <strong>{account.username}</strong>
                <span>
                  {account.role === "child" ? "孩子账号" : "家长账号"} ·{" "}
                  {account.status === "active" ? "启用" : "已停用"}
                </span>
              </div>
              {account.role === "child" ? (
                <>
                  <button
                    className="text-button"
                    type="button"
                    onClick={() => void toggle(account)}
                  >
                    {account.status === "active" ? "停用" : "启用"}
                  </button>
                  <button
                    className="text-button"
                    type="button"
                    onClick={() => void resetPassword(account)}
                  >
                    重置密码
                  </button>
                </>
              ) : null}
            </div>
          ))}
        </article>
        <article className="panel">
          <div className="panel-heading">
            <div>
              <p className="section-kicker">新增</p>
              <h2>创建孩子账号</h2>
            </div>
          </div>
          <form onSubmit={create} className="auth-form">
            <label>
              用户名
              <input
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                required
              />
            </label>
            <label>
              初始密码（至少 8 位）
              <input
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                type="password"
                minLength={8}
                required
              />
            </label>
            <label>
              孩子档案 ID
              <input
                value={childId}
                onChange={(event) => setChildId(event.target.value)}
                placeholder="UUID"
                required
              />
            </label>
            {message ? <p>{message}</p> : null}
            <button className="primary-button" type="submit">
              创建账号
            </button>
          </form>
        </article>
      </section>
    </main>
  );
}
