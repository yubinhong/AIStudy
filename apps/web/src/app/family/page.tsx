"use client";

import {
  ShieldCheck,
  Trash,
  UserPlus,
  UsersThree,
} from "@phosphor-icons/react";
import { FormEvent, useEffect, useState } from "react";

import { AdminShell } from "@/app/components/admin-shell";
import { idempotencyKey } from "@/lib/idempotency-key";

type CurrentAccount = {
  username: string;
  role: "super_admin" | "parent" | "child";
};

type ParentAccount = {
  id: string;
  household_id: string;
  username: string;
  status: "active" | "disabled";
  must_change_password: boolean;
};

type FamilyParent = {
  account: ParentAccount;
  child_count: number;
};

function csrfToken() {
  return document.cookie
    .split("; ")
    .find((value) => value.startsWith("study_csrf="))
    ?.split("=")[1];
}

function headers(includeJson = false) {
  return {
    ...(includeJson ? { "content-type": "application/json" } : {}),
    ...(csrfToken()
      ? { "X-CSRF-Token": decodeURIComponent(csrfToken()!) }
      : {}),
  };
}

export default function FamilyPermissionsPage() {
  const [currentAccount, setCurrentAccount] = useState<CurrentAccount | null>(
    null,
  );
  const [parents, setParents] = useState<FamilyParent[]>([]);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState<string | null>(null);

  async function loadParents() {
    const response = await fetch("/api/auth/family-parents", {
      cache: "no-store",
    });
    if (!response.ok) {
      setMessage("暂时无法读取家庭家长账号");
      return;
    }
    setParents((await response.json()) as FamilyParent[]);
  }

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void fetch("/api/auth/session", { cache: "no-store" })
        .then(async (response) => {
          if (!response.ok) throw new Error("session unavailable");
          return (await response.json()) as CurrentAccount;
        })
        .then(async (account) => {
          setCurrentAccount(account);
          if (account.role !== "super_admin") {
            window.location.replace("/accounts");
            return;
          }
          await loadParents();
        })
        .catch(() => setMessage("暂时无法验证当前账号权限"));
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  async function provisionFamily(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const response = await fetch("/api/auth/households", {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "Idempotency-Key": idempotencyKey("web-provision-family"),
        ...headers(),
      },
      body: JSON.stringify({
        parent_username: username,
        parent_password: password,
      }),
    });
    setMessage(
      response.ok
        ? "家庭已开通，新家长首次登录时需要修改密码"
        : "开通家庭失败，请检查用户名和密码",
    );
    if (response.ok) {
      setUsername("");
      setPassword("");
      await loadParents();
    }
  }

  async function deleteParent(parent: FamilyParent) {
    if (parent.child_count > 0) return;
    if (
      !window.confirm(
        `删除家长账号“${parent.account.username}”？此操作无法撤销。`,
      )
    ) {
      return;
    }
    const currentPassword = window.prompt("请输入当前超级管理员密码以确认删除");
    if (!currentPassword) return;
    const response = await fetch(
      `/api/auth/family-parents/${parent.account.id}`,
      {
        method: "DELETE",
        headers: headers(true),
        body: JSON.stringify({ current_password: currentPassword }),
      },
    );
    setMessage(
      response.ok
        ? "家长账号已删除，相关登录会话已撤销"
        : response.status === 409
          ? "该家长仍拥有孩子档案，不能删除"
          : "删除家长账号失败",
    );
    if (response.ok) await loadParents();
  }

  if (currentAccount && currentAccount.role !== "super_admin") return null;

  return (
    <AdminShell active="family">
      <div className="page-header">
        <div>
          <p className="page-eyebrow">家庭权限</p>
          <h1>家庭与家长账号</h1>
          <p>为亲戚开通独立家庭，并维护其首个家长账号。</p>
        </div>
        <span className="header-stat">
          <UsersThree size={19} /> {parents.length} 个家庭家长
        </span>
      </div>

      {message ? (
        <div className="notice-banner" role="status">
          {message}
        </div>
      ) : null}

      <section className="management-grid">
        <article className="dashboard-panel form-panel">
          <div className="section-heading">
            <div>
              <p className="section-kicker">开通家庭</p>
              <h2>创建家长账号</h2>
            </div>
            <span className="section-icon">
              <UserPlus size={22} />
            </span>
          </div>
          <form className="auth-form" onSubmit={provisionFamily}>
            <label>
              新家庭家长用户名
              <input
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                minLength={3}
                required
              />
            </label>
            <label>
              初始密码（至少 12 位）
              <input
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                type="password"
                minLength={12}
                required
              />
            </label>
            <button className="primary-button" type="submit">
              <UsersThree size={18} /> 开通家庭并创建家长
            </button>
          </form>
        </article>

        <article className="dashboard-panel">
          <div className="section-heading">
            <div>
              <p className="section-kicker">已开通家庭</p>
              <h2>家长账号</h2>
            </div>
            <span className="quiet-label">{parents.length} 个账号</span>
          </div>
          <div className="account-list">
            {parents.length === 0 ? (
              <p className="muted-copy">尚未开通其他家庭。</p>
            ) : null}
            {parents.map((parent) => (
              <div className="account-row" key={parent.account.id}>
                <span className="account-avatar">
                  <ShieldCheck size={19} />
                </span>
                <div className="task-details">
                  <strong>{parent.account.username}</strong>
                  <span>
                    {parent.child_count} 个孩子 ·{" "}
                    {parent.account.status === "active" ? "启用" : "已停用"}
                  </span>
                </div>
                <span className="status-pill">
                  {parent.account.must_change_password ? "待改密" : "正常"}
                </span>
                <button
                  className="icon-button danger-button"
                  type="button"
                  aria-label={`删除家长 ${parent.account.username}`}
                  disabled={parent.child_count > 0}
                  title={
                    parent.child_count > 0
                      ? "该家长仍拥有孩子档案，不能删除"
                      : "删除家长账号"
                  }
                  onClick={() => void deleteParent(parent)}
                >
                  <Trash size={17} />
                </button>
              </div>
            ))}
          </div>
        </article>
      </section>
    </AdminShell>
  );
}
