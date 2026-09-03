"use client";

import {
  BookOpenText,
  CalendarCheck,
  ClockCounterClockwise,
  CaretDown,
  CaretRight,
  Check,
  HouseLine,
  IdentificationCard,
  Leaf,
  ShieldCheck,
} from "@phosphor-icons/react/dist/ssr";
import type { IconProps } from "@phosphor-icons/react";
import Link from "next/link";
import { useEffect, useState, type ComponentType, type ReactNode } from "react";

import { AccountMenu } from "./account-menu";

type ActiveSection =
  | "overview"
  | "learning"
  | "curriculum"
  | "accounts"
  | "family";

type AdminShellProps = {
  active: ActiveSection;
  children: ReactNode;
  childOptions?: ChildOption[];
  childName?: string;
  childMeta?: string;
  childSwitchBaseHref?: string;
  connectionLabel?: string;
  selectedChildId?: string;
};

export type ChildOption = {
  id: string;
  meta: string;
  name: string;
};

type NavigationItem = {
  href: string;
  icon: ComponentType<IconProps>;
  label: string;
  section?: ActiveSection;
};

type CurrentAccount = {
  role: "super_admin" | "parent" | "child";
};

export const adminNavigationGroups: Array<{
  label: string;
  items: NavigationItem[];
}> = [
  {
    label: "概览",
    items: [
      {
        href: "/",
        icon: HouseLine,
        label: "家长工作台",
        section: "overview",
      },
    ],
  },
  {
    label: "学习",
    items: [
      {
        href: "/learning",
        icon: ClockCounterClockwise,
        label: "学习记录",
        section: "learning",
      },
    ],
  },
  {
    label: "教材",
    items: [
      {
        href: "/curriculum",
        icon: BookOpenText,
        label: "教材管理",
        section: "curriculum",
      },
    ],
  },
  {
    label: "孩子与账号",
    items: [
      {
        href: "/accounts",
        icon: IdentificationCard,
        label: "孩子管理",
        section: "accounts",
      },
    ],
  },
];

const familyNavigationGroup: { label: string; items: NavigationItem[] } = {
  label: "家庭权限",
  items: [
    {
      href: "/family",
      icon: ShieldCheck,
      label: "家庭权限",
      section: "family",
    },
  ],
};

export function childScopedHref(baseHref: string, childId?: string) {
  if (!childId) return baseHref;
  return `${baseHref}?child=${encodeURIComponent(childId)}`;
}

function weekRangeLabel() {
  const now = new Date();
  const weekday = now.getDay() || 7;
  const monday = new Date(now);
  monday.setDate(now.getDate() - weekday + 1);
  const sunday = new Date(monday);
  sunday.setDate(monday.getDate() + 6);
  const format = (date: Date) =>
    new Intl.DateTimeFormat("zh-CN", {
      month: "2-digit",
      day: "2-digit",
      timeZone: "Asia/Shanghai",
    }).format(date);
  return `${format(monday)} – ${format(sunday)}`;
}

export function AdminShell({
  active,
  children,
  childOptions = [],
  childName = "家庭空间",
  childMeta = "当前孩子",
  childSwitchBaseHref = "/",
  connectionLabel = "本地服务已连接",
  selectedChildId,
}: AdminShellProps) {
  const [account, setAccount] = useState<CurrentAccount | null>(null);
  const selectedOption =
    childOptions.find((option) => option.id === selectedChildId) ??
    childOptions[0];
  const currentName = selectedOption?.name ?? childName;
  const currentMeta = selectedOption?.meta ?? childMeta;
  const navigationGroups =
    account?.role === "super_admin"
      ? [...adminNavigationGroups, familyNavigationGroup]
      : adminNavigationGroups;

  useEffect(() => {
    void fetch("/api/auth/session", { cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) return null;
        return (await response.json()) as CurrentAccount;
      })
      .then(setAccount)
      .catch(() => setAccount(null));
  }, []);

  return (
    <div className="admin-shell">
      <aside className="admin-sidebar">
        <Link
          className="admin-brand"
          href="/"
          aria-label="家庭 AI 学习助手首页"
        >
          <span className="admin-brand-mark" aria-hidden="true">
            <Leaf size={20} weight="fill" />
          </span>
          <span className="admin-brand-copy">
            <strong>家庭学习助手</strong>
            <small>家长管理后台</small>
          </span>
        </Link>

        <nav className="admin-navigation" aria-label="家长端主导航">
          {navigationGroups.map((group) => (
            <div className="nav-group" key={group.label}>
              <p>{group.label}</p>
              {group.items.map((item) => {
                const Icon = item.icon;
                const selected = item.section === active;
                return (
                  <Link
                    className={selected ? "nav-item active" : "nav-item"}
                    href={childScopedHref(item.href, selectedChildId)}
                    key={`${group.label}-${item.label}`}
                    aria-current={selected ? "page" : undefined}
                  >
                    <Icon size={19} weight={selected ? "fill" : "regular"} />
                    <span>{item.label}</span>
                    {selected ? (
                      <CaretRight className="nav-caret" size={15} />
                    ) : null}
                  </Link>
                );
              })}
            </div>
          ))}
        </nav>
        <div className="admin-sidebar-foot">
          <span aria-hidden="true" />
          家庭私有空间
        </div>
      </aside>

      <div className="admin-workspace">
        <header className="admin-topbar">
          {childOptions.length > 1 ? (
            <details className="child-switcher">
              <summary aria-label={`当前孩子：${currentName}，点击切换`}>
                <span className="child-context-avatar" aria-hidden="true">
                  {currentName.slice(0, 1)}
                </span>
                <span className="child-context-copy">
                  <strong>{currentName}</strong>
                  <small>{currentMeta}</small>
                </span>
                <CaretDown className="child-switcher-caret" size={15} />
              </summary>
              <nav className="child-switcher-menu" aria-label="切换当前孩子">
                <p>切换当前孩子</p>
                {childOptions.map((option) => {
                  const selected = option.id === selectedChildId;
                  return (
                    <Link
                      className={selected ? "active" : ""}
                      href={childScopedHref(childSwitchBaseHref, option.id)}
                      key={option.id}
                    >
                      <span className="child-option-avatar" aria-hidden="true">
                        {option.name.slice(0, 1)}
                      </span>
                      <span>
                        <strong>{option.name}</strong>
                        <small>{option.meta}</small>
                      </span>
                      {selected ? <Check size={16} weight="bold" /> : null}
                    </Link>
                  );
                })}
              </nav>
            </details>
          ) : (
            <Link
              className="child-context"
              href={childScopedHref("/accounts", selectedChildId)}
            >
              <span className="child-context-avatar" aria-hidden="true">
                {currentName.slice(0, 1)}
              </span>
              <span className="child-context-copy">
                <strong>{currentName}</strong>
                <small>{currentMeta}</small>
              </span>
            </Link>
          )}
          <div className="topbar-actions">
            <span className="week-range">
              <CalendarCheck size={18} />
              {weekRangeLabel()}
            </span>
            <span className="service-status">
              <span aria-hidden="true" />
              {connectionLabel}
            </span>
            <AccountMenu />
          </div>
        </header>
        <main className="admin-main">{children}</main>
      </div>
    </div>
  );
}
