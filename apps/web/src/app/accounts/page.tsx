"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";

import { createChildAccountIdempotencyKey } from "../../lib/account-request";

type Account = {
  id: string;
  username: string;
  role: "parent" | "child";
  child_id: string | null;
  status: "active" | "disabled";
  must_change_password: boolean;
};

type ChildProfile = {
  id: string;
  display_name: string;
  grade: number;
};

type ChildManagement = {
  child: ChildProfile;
  account: Account | null;
};

function csrfToken() {
  return document.cookie
    .split("; ")
    .find((value) => value.startsWith("study_csrf="))
    ?.split("=")[1];
}

export default function AccountsPage() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [children, setChildren] = useState<ChildProfile[]>([]);
  const [management, setManagement] = useState<ChildManagement[]>([]);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [profileName, setProfileName] = useState("");
  const [profileGrade, setProfileGrade] = useState("3");
  const [taskTitle, setTaskTitle] = useState("");
  const [taskChildId, setTaskChildId] = useState("");
  const [message, setMessage] = useState<string | null>(null);

  async function load() {
    const [accountsResponse, managementResponse, childrenResponse] =
      await Promise.all([
        fetch("/api/auth/accounts", { cache: "no-store" }),
        fetch("/api/children/management", { cache: "no-store" }),
        fetch("/api/children", { cache: "no-store" }),
      ]);
    if (accountsResponse.ok)
      setAccounts((await accountsResponse.json()) as Account[]);
    if (managementResponse.ok) {
      const aggregates = (await managementResponse.json()) as ChildManagement[];
      setManagement(aggregates);
      const childProfiles = aggregates.map((item) => item.child);
      setChildren(childProfiles);
      setTaskChildId((current) => current || childProfiles[0]?.id || "");
    } else if (childrenResponse.ok) {
      const childProfiles = (await childrenResponse.json()) as ChildProfile[];
      setChildren(childProfiles);
      setTaskChildId((current) => current || childProfiles[0]?.id || "");
    }
  }

  useEffect(() => {
    let active = true;
    const timer = window.setTimeout(() => {
      load().catch(() => {
        if (active) setMessage("暂时无法加载家庭数据");
      });
    }, 0);
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, []);

  async function createManagement(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const response = await fetch("/api/children/management", {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "Idempotency-Key": createChildAccountIdempotencyKey(),
        ...(csrfToken()
          ? { "X-CSRF-Token": decodeURIComponent(csrfToken()!) }
          : {}),
      },
      body: JSON.stringify({
        display_name: profileName,
        grade: Number(profileGrade),
        curriculum_version: "math-demo-2026",
        subjects: ["math"],
        username,
        password,
      }),
    });
    setMessage(
      response.ok
        ? "孩子档案和账号已创建"
        : "创建失败，请检查姓名、用户名和密码",
    );
    if (response.ok) {
      setProfileName("");
      setProfileGrade("3");
      setUsername("");
      setPassword("");
      await load();
    }
  }

  async function createTask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const today = new Date().toLocaleDateString("en-CA", {
      timeZone: "Asia/Shanghai",
    });
    const response = await fetch("/api/tasks", {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "Idempotency-Key": createChildAccountIdempotencyKey(),
        ...(csrfToken()
          ? { "X-CSRF-Token": decodeURIComponent(csrfToken()!) }
          : {}),
      },
      body: JSON.stringify({
        child_id: taskChildId,
        title: taskTitle,
        subject: "math",
        scheduled_for: today,
      }),
    });
    setMessage(
      response.ok ? "今日数学任务已安排" : "创建任务失败，请检查孩子档案",
    );
    if (response.ok) setTaskTitle("");
  }

  async function editProfile(child: ChildProfile) {
    const displayName = window.prompt("孩子姓名", child.display_name);
    if (!displayName) return;
    const grade = window.prompt("年级（1 到 6）", String(child.grade));
    if (!grade || !/^[1-6]$/.test(grade)) {
      setMessage("年级必须是 1 到 6");
      return;
    }
    const response = await fetch(`/api/children/${child.id}`, {
      method: "PATCH",
      headers: {
        "content-type": "application/json",
        "Idempotency-Key": createChildAccountIdempotencyKey(),
        ...(csrfToken()
          ? { "X-CSRF-Token": decodeURIComponent(csrfToken()!) }
          : {}),
      },
      body: JSON.stringify({
        display_name: displayName,
        grade: Number(grade),
        curriculum_version: "math-demo-2026",
        subjects: ["math"],
      }),
    });
    setMessage(response.ok ? "孩子档案已更新" : "更新孩子档案失败");
    if (response.ok) await load();
  }

  async function deleteProfile(child: ChildProfile) {
    if (
      !window.confirm(
        `删除“${child.display_name}”的孩子档案及相关图片？此操作不能撤销。`,
      )
    )
      return;
    const response = await fetch(`/api/children/${child.id}`, {
      method: "DELETE",
      headers: {
        "Idempotency-Key": createChildAccountIdempotencyKey(),
        ...(csrfToken()
          ? { "X-CSRF-Token": decodeURIComponent(csrfToken()!) }
          : {}),
      },
    });
    setMessage(response.ok ? "孩子档案已删除" : "删除孩子档案失败");
    if (response.ok) await load();
  }

  async function exportProfile(child: ChildProfile) {
    const response = await fetch(`/api/children/${child.id}/export`, {
      method: "POST",
      headers: {
        "Idempotency-Key": createChildAccountIdempotencyKey(),
        ...(csrfToken()
          ? { "X-CSRF-Token": decodeURIComponent(csrfToken()!) }
          : {}),
      },
    });
    if (!response.ok) {
      setMessage("导出孩子数据失败，请稍后重试");
      return;
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `study-child-${child.id}.json`;
    link.click();
    URL.revokeObjectURL(url);
    setMessage("孩子数据已导出；服务端快照将在 24 小时后清理");
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
              <p className="section-kicker">今日安排</p>
              <h2>创建数学任务</h2>
            </div>
          </div>
          <form onSubmit={createTask} className="auth-form">
            <label>
              孩子档案
              <select
                value={taskChildId}
                onChange={(event) => setTaskChildId(event.target.value)}
                required
              >
                <option value="">请选择孩子</option>
                {children.map((child) => (
                  <option key={child.id} value={child.id}>
                    {child.display_name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              任务名称
              <input
                value={taskTitle}
                onChange={(event) => setTaskTitle(event.target.value)}
                placeholder="例如：完成今天的分数练习"
                maxLength={120}
                required
              />
            </label>
            <button
              className="primary-button"
              type="submit"
              disabled={!children.length}
            >
              安排今日任务
            </button>
          </form>
        </article>
        <article className="panel" id="profiles">
          <div className="panel-heading">
            <div>
              <p className="section-kicker">家庭成员</p>
              <h2>孩子档案管理</h2>
            </div>
          </div>
          {management.map((item) => {
            const child = item.child;
            return (
              <div className="task-row" key={child.id}>
                <div className="task-details">
                  <strong>{child.display_name}</strong>
                  <span>
                    小学{child.grade}年级 ·{" "}
                    {item.account?.username ?? "账号未创建"}
                  </span>
                </div>
                <button
                  className="text-button"
                  type="button"
                  onClick={() => void editProfile(child)}
                >
                  编辑
                </button>
                <button
                  className="text-button"
                  type="button"
                  onClick={() => void exportProfile(child)}
                >
                  导出
                </button>
                <button
                  className="text-button danger-button"
                  type="button"
                  onClick={() => void deleteProfile(child)}
                >
                  删除
                </button>
                {item.account ? (
                  <>
                    <button
                      className="text-button"
                      type="button"
                      onClick={() => void toggle(item.account!)}
                    >
                      {item.account.status === "active"
                        ? "停用账号"
                        : "启用账号"}
                    </button>
                    <button
                      className="text-button"
                      type="button"
                      onClick={() => void resetPassword(item.account!)}
                    >
                      重置密码
                    </button>
                  </>
                ) : null}
              </div>
            );
          })}
          <form onSubmit={createManagement} className="auth-form">
            <p className="section-kicker">新增</p>
            <h3>创建孩子档案与账号</h3>
            <label>
              孩子姓名
              <input
                value={profileName}
                onChange={(event) => setProfileName(event.target.value)}
                required
              />
            </label>
            <label>
              孩子登录用户名
              <input
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                minLength={3}
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
              年级
              <select
                value={profileGrade}
                onChange={(event) => setProfileGrade(event.target.value)}
              >
                {[1, 2, 3, 4, 5, 6].map((grade) => (
                  <option
                    key={grade}
                    value={grade}
                  >{`小学${grade}年级`}</option>
                ))}
              </select>
            </label>
            {message ? <p>{message}</p> : null}
            <button className="primary-button" type="submit">
              创建孩子档案与账号
            </button>
          </form>
        </article>
        <article className="panel">
          <div className="panel-heading">
            <div>
              <p className="section-kicker">已创建</p>
              <h2>家庭账号</h2>
            </div>
          </div>
          {accounts
            .filter((account) => account.role === "parent")
            .map((account) => (
              <div className="task-row" key={account.id}>
                <div className="task-details">
                  <strong>{account.username}</strong>
                  <span>
                    家长账号 · {account.status === "active" ? "启用" : "已停用"}
                  </span>
                </div>
              </div>
            ))}
          {accounts.every((account) => account.role !== "parent") ? (
            <p>暂无其他家长账号。</p>
          ) : null}
        </article>
      </section>
    </main>
  );
}
