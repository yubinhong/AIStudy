"use client";

import {
  CalendarPlus,
  DownloadSimple,
  Key,
  PencilSimple,
  Plus,
  ShieldCheck,
  Trash,
  UserPlus,
  UsersThree,
} from "@phosphor-icons/react";
import { FormEvent, useEffect, useState } from "react";

import { AdminShell } from "@/app/components/admin-shell";
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

function writeHeaders(includeJson = false) {
  return {
    ...(includeJson ? { "content-type": "application/json" } : {}),
    "Idempotency-Key": createChildAccountIdempotencyKey(),
    ...(csrfToken()
      ? { "X-CSRF-Token": decodeURIComponent(csrfToken()!) }
      : {}),
  };
}

function requestedChildId(profiles: ChildProfile[]) {
  const requested = new URLSearchParams(window.location.search).get("child");
  return profiles.some((profile) => profile.id === requested)
    ? requested
    : null;
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
    if (accountsResponse.ok) {
      setAccounts((await accountsResponse.json()) as Account[]);
    }
    if (managementResponse.ok) {
      const aggregates = (await managementResponse.json()) as ChildManagement[];
      setManagement(aggregates);
      const childProfiles = aggregates.map((item) => item.child);
      setChildren(childProfiles);
      setTaskChildId(
        (current) =>
          requestedChildId(childProfiles) ||
          current ||
          childProfiles[0]?.id ||
          "",
      );
    } else if (childrenResponse.ok) {
      const childProfiles = (await childrenResponse.json()) as ChildProfile[];
      setChildren(childProfiles);
      setTaskChildId(
        (current) =>
          requestedChildId(childProfiles) ||
          current ||
          childProfiles[0]?.id ||
          "",
      );
    }
  }

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void load().catch(() => setMessage("暂时无法加载家庭数据"));
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  async function createManagement(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const response = await fetch("/api/children/management", {
      method: "POST",
      headers: writeHeaders(true),
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
      headers: writeHeaders(true),
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
      headers: writeHeaders(true),
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
    ) {
      return;
    }
    const response = await fetch(`/api/children/${child.id}`, {
      method: "DELETE",
      headers: writeHeaders(),
    });
    setMessage(response.ok ? "孩子档案已删除" : "删除孩子档案失败");
    if (response.ok) await load();
  }

  async function exportProfile(child: ChildProfile) {
    const response = await fetch(`/api/children/${child.id}/export`, {
      method: "POST",
      headers: writeHeaders(),
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
    setMessage(response.ok ? "账号状态已更新" : "账号状态更新失败");
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

  const currentChild =
    children.find((child) => child.id === taskChildId) ?? children[0];
  const parentAccounts = accounts.filter(
    (account) => account.role === "parent",
  );

  return (
    <AdminShell
      active="accounts"
      childOptions={children.map((child) => ({
        id: child.id,
        meta: `小学${child.grade}年级`,
        name: child.display_name,
      }))}
      childMeta={currentChild ? `小学${currentChild.grade}年级` : "家庭成员"}
      childName={currentChild?.display_name ?? "家庭空间"}
      childSwitchBaseHref="/accounts"
      selectedChildId={currentChild?.id}
    >
      <div className="page-header">
        <div>
          <p className="page-eyebrow">孩子与账号</p>
          <h1>家庭成员管理</h1>
          <p>孩子档案、登录账号和今日任务都在同一个家庭范围内管理。</p>
        </div>
        <span className="header-stat">
          <UsersThree size={19} /> {children.length} 个孩子
        </span>
      </div>

      {message ? (
        <div className="notice-banner" role="status">
          {message}
        </div>
      ) : null}

      <section className="management-grid">
        <article className="dashboard-panel form-panel" id="tasks">
          <div className="section-heading">
            <div>
              <p className="section-kicker">今日安排</p>
              <h2>创建数学任务</h2>
            </div>
            <span className="section-icon">
              <CalendarPlus size={22} />
            </span>
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
              <CalendarPlus size={18} /> 安排今日任务
            </button>
          </form>
        </article>

        <article className="dashboard-panel" id="profiles">
          <div className="section-heading">
            <div>
              <p className="section-kicker">家庭成员</p>
              <h2>孩子档案管理</h2>
            </div>
            <span className="quiet-label">{management.length} 份档案</span>
          </div>
          <div className="profile-list">
            {management.length === 0 ? (
              <p className="muted-copy">尚未创建孩子档案。</p>
            ) : null}
            {management.map((item) => {
              const child = item.child;
              return (
                <article className="profile-card" key={child.id}>
                  <span className="profile-avatar" aria-hidden="true">
                    {child.display_name.slice(0, 1)}
                  </span>
                  <div className="profile-main">
                    <strong>{child.display_name}</strong>
                    <span>
                      小学{child.grade}年级 ·{" "}
                      {item.account?.username ?? "账号未创建"}
                    </span>
                  </div>
                  <span
                    className={
                      item.account?.status === "active"
                        ? "status-pill"
                        : "status-pill amber"
                    }
                  >
                    {item.account?.status === "active" ? "可登录" : "未启用"}
                  </span>
                  <div className="profile-actions">
                    <button
                      className="icon-button"
                      type="button"
                      onClick={() => void editProfile(child)}
                      aria-label={`编辑${child.display_name}`}
                    >
                      <PencilSimple size={17} />
                    </button>
                    <button
                      className="icon-button"
                      type="button"
                      onClick={() => void exportProfile(child)}
                      aria-label={`导出${child.display_name}数据`}
                    >
                      <DownloadSimple size={17} />
                    </button>
                    {item.account ? (
                      <button
                        className="icon-button"
                        type="button"
                        onClick={() => void resetPassword(item.account!)}
                        aria-label={`重置${item.account.username}密码`}
                      >
                        <Key size={17} />
                      </button>
                    ) : null}
                    <button
                      className="icon-button danger-button"
                      type="button"
                      onClick={() => void deleteProfile(child)}
                      aria-label={`删除${child.display_name}`}
                    >
                      <Trash size={17} />
                    </button>
                  </div>
                  {item.account ? (
                    <button
                      className="profile-toggle"
                      type="button"
                      onClick={() => void toggle(item.account!)}
                    >
                      <ShieldCheck size={16} />
                      {item.account.status === "active"
                        ? "停用账号"
                        : "启用账号"}
                    </button>
                  ) : null}
                </article>
              );
            })}
          </div>
        </article>
      </section>

      <section className="management-grid lower-grid">
        <article className="dashboard-panel form-panel">
          <div className="section-heading">
            <div>
              <p className="section-kicker">新增成员</p>
              <h2>创建孩子档案与账号</h2>
            </div>
            <span className="section-icon">
              <UserPlus size={22} />
            </span>
          </div>
          <form
            onSubmit={createManagement}
            className="auth-form form-two-column"
          >
            <label>
              孩子姓名
              <input
                value={profileName}
                onChange={(event) => setProfileName(event.target.value)}
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
            <button className="primary-button form-full" type="submit">
              <Plus size={18} /> 创建孩子档案与账号
            </button>
          </form>
        </article>

        <article className="dashboard-panel">
          <div className="section-heading">
            <div>
              <p className="section-kicker">已创建</p>
              <h2>家长账号</h2>
            </div>
            <span className="quiet-label">{parentAccounts.length} 个账号</span>
          </div>
          <div className="account-list">
            {parentAccounts.map((account) => (
              <div className="account-row" key={account.id}>
                <span className="account-avatar">
                  <UsersThree size={19} />
                </span>
                <div className="task-details">
                  <strong>{account.username}</strong>
                  <span>
                    家长账号 · {account.status === "active" ? "启用" : "已停用"}
                  </span>
                </div>
                <span className="status-pill">
                  {account.must_change_password ? "待改密" : "正常"}
                </span>
              </div>
            ))}
            {parentAccounts.length === 0 ? (
              <p className="muted-copy">暂无家长账号。</p>
            ) : null}
          </div>
        </article>
      </section>
    </AdminShell>
  );
}
