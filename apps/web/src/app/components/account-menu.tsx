"use client";

import {
  CaretDown,
  IdentificationCard,
  SignOut,
  UserCircle,
} from "@phosphor-icons/react";
import Link from "next/link";
import { useEffect, useState } from "react";

type CurrentAccount = {
  username: string;
  role: "super_admin" | "parent" | "child";
};

function csrfToken() {
  return document.cookie
    .split("; ")
    .find((value) => value.startsWith("study_csrf="))
    ?.split("=")[1];
}

export function accountRoleLabel(role: CurrentAccount["role"]) {
  if (role === "super_admin") return "超级管理员";
  if (role === "parent") return "家长账号";
  return "孩子账号";
}

export function AccountMenu() {
  const [account, setAccount] = useState<CurrentAccount | null>(null);

  useEffect(() => {
    void fetch("/api/auth/session", { cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) return null;
        return (await response.json()) as CurrentAccount;
      })
      .then(setAccount)
      .catch(() => setAccount(null));
  }, []);

  async function logout() {
    const response = await fetch("/api/auth/logout", {
      method: "POST",
      headers: csrfToken()
        ? { "X-CSRF-Token": decodeURIComponent(csrfToken()!) }
        : {},
    });
    if (response.ok) window.location.assign("/login");
  }

  if (!account) return null;

  return (
    <details className="account-menu">
      <summary aria-label={`当前账号：${account.username}`}>
        <span className="account-menu-avatar" aria-hidden="true">
          <UserCircle size={21} weight="fill" />
        </span>
        <span className="account-menu-copy">
          <strong>{account.username}</strong>
          <small>{accountRoleLabel(account.role)}</small>
        </span>
        <CaretDown className="account-menu-caret" size={15} />
      </summary>
      <div className="account-menu-panel">
        <Link href={account.role === "super_admin" ? "/family" : "/accounts"}>
          <IdentificationCard size={17} /> 家庭与账号管理
        </Link>
        <button type="button" onClick={() => void logout()}>
          <SignOut size={17} /> 退出登录
        </button>
      </div>
    </details>
  );
}
