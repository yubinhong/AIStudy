import {
  loadChildren,
  loadDevices,
  loadMistakes,
  loadTasks,
  loadWeeklyReport,
  readArray,
  readDateLabel,
  readNumber,
  readString,
} from "@/lib/household-data";
import Link from "next/link";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

export default async function HomePage({
  searchParams,
}: {
  searchParams?: Promise<{ child?: string }>;
}) {
  const session = (await cookies()).get("study_session");
  if (!session) redirect("/login");
  const children = await loadChildren();
  const requestedChildId = (await searchParams)?.child;
  const selectedChild =
    children.find((child) => readString(child, "id") === requestedChildId) ??
    children[0];
  const selectedChildId = readString(selectedChild, "id");
  const [tasks, devices, weeklyReport, mistakes] = await Promise.all([
    loadTasks(selectedChildId ?? undefined),
    loadDevices(),
    selectedChildId ? loadWeeklyReport(selectedChildId) : Promise.resolve(null),
    selectedChildId ? loadMistakes(selectedChildId, true) : Promise.resolve([]),
  ]);
  const firstTask = tasks[0];
  const childName = readString(selectedChild, "display_name") ?? "合成孩子";
  const taskTitle = readString(firstTask, "title") ?? "今天的数学小任务";
  const taskDate = readDateLabel(firstTask, "scheduled_for");
  const grade = readNumber(selectedChild, "grade");
  const apiConnected =
    children.length > 0 || tasks.length > 0 || devices.length > 0;
  const tasksAssigned = readNumber(weeklyReport, "tasks_assigned") ?? 0;
  const tasksCompleted = readNumber(weeklyReport, "tasks_completed") ?? 0;
  const tasksSkipped = readNumber(weeklyReport, "tasks_skipped") ?? 0;
  const needsReview = readNumber(weeklyReport, "needs_review") ?? 0;
  const tutorTurns = readNumber(weeklyReport, "tutor_turns") ?? 0;
  const completionRate = readNumber(weeklyReport, "completion_rate") ?? 0;
  const reviewItems = readArray(weeklyReport, "review_items");

  return (
    <main className="shell">
      <header className="topbar">
        <Link className="brand" href="/" aria-label="家庭 AI 学习助手首页">
          <span className="brand-mark" aria-hidden="true">
            禾
          </span>
          <span>家庭 AI 学习助手</span>
        </Link>
        <div
          className="connection-status"
          aria-label={apiConnected ? "API 已连接" : "API 未连接"}
        >
          <span className={apiConnected ? "status-dot online" : "status-dot"} />
          {apiConnected ? "本地数据已连接" : "等待本地 API"}
        </div>
      </header>

      <section className="hero" aria-labelledby="welcome-heading">
        <div>
          <p className="eyebrow">家长工作台 · 今天</p>
          <h1 id="welcome-heading">
            陪 {childName}，<br />
            <span>一步一步学会。</span>
          </h1>
          <p className="hero-copy">看见进度，也给孩子留一点自己思考的空间。</p>
        </div>
        <div className="hero-orbit" aria-hidden="true">
          <span className="orbit-sun">☼</span>
          <span className="orbit-leaf">✦</span>
        </div>
      </section>

      <section className="summary-grid" aria-label="学习概览">
        <article className="summary-card accent-green">
          <span className="card-icon">◒</span>
          <div>
            <strong>{children.length || "—"}</strong>
            <span>个孩子档案</span>
          </div>
        </article>
        <article className="summary-card accent-yellow">
          <span className="card-icon">▣</span>
          <div>
            <strong>{tasks.length || "—"}</strong>
            <span>今日学习任务</span>
          </div>
        </article>
        <article className="summary-card accent-blue">
          <span className="card-icon">⌁</span>
          <div>
            <strong>{devices.length || "—"}</strong>
            <span>已连接设备</span>
          </div>
        </article>
      </section>

      <section className="content-grid">
        <article className="panel task-panel" aria-labelledby="task-heading">
          <div className="panel-heading">
            <div>
              <p className="section-kicker">今日安排</p>
              <h2 id="task-heading">学习任务</h2>
            </div>
            <span className="soft-badge">数学</span>
          </div>
          {children.length > 1 ? (
            <nav className="child-switcher" aria-label="切换当前孩子">
              {children.map((child) => {
                const id = readString(child, "id");
                const name = readString(child, "display_name") ?? "孩子";
                return id ? (
                  <Link
                    className={id === selectedChildId ? "active" : ""}
                    href={`/?child=${encodeURIComponent(id)}`}
                    key={id}
                  >
                    {name}
                  </Link>
                ) : null;
              })}
            </nav>
          ) : null}
          {firstTask ? (
            <div className="task-row">
              <div className="task-check" aria-hidden="true">
                ✓
              </div>
              <div className="task-details">
                <strong>{taskTitle}</strong>
                <span>
                  {grade ? `小学${grade}年级` : "数学练习"}
                  {taskDate ? ` · ${taskDate}` : ""}
                </span>
              </div>
              <span className="task-state">待开始</span>
            </div>
          ) : (
            <div className="empty-state">
              <span className="empty-icon">☁</span>
              <p>
                还没有今天的任务
                <br />
                <small>启动 API 后会显示真实家庭数据</small>
              </p>
            </div>
          )}
          <div className="panel-footer">
            <span>完成进度</span>
            <span>{firstTask ? "0%" : "—"}</span>
          </div>
          <div className="progress-track">
            <span style={{ width: firstTask ? "8%" : "0%" }} />
          </div>
        </article>

        <article className="panel child-panel" aria-labelledby="child-heading">
          <div className="panel-heading">
            <div>
              <p className="section-kicker">家庭成员</p>
              <h2 id="child-heading">孩子档案</h2>
            </div>
            <Link className="text-button" href="/accounts">
              管理
            </Link>
          </div>
          {selectedChild ? (
            <Link className="child-row" href="/accounts#profiles">
              <div className="avatar" aria-hidden="true">
                {childName.slice(0, 1)}
              </div>
              <div>
                <strong>{childName}</strong>
                <span>{grade ? `小学${grade}年级` : "数学学习"}</span>
              </div>
              <span className="chevron">›</span>
            </Link>
          ) : (
            <div className="empty-state compact">
              <span className="empty-icon">◎</span>
              <p>暂无档案</p>
            </div>
          )}
          <div className="privacy-note">
            <span aria-hidden="true">⌁</span>
            <p>孩子的学习记录只在家庭空间内使用。</p>
          </div>
        </article>
      </section>

      <section className="panel weekly-panel" aria-labelledby="weekly-heading">
        <div className="panel-heading">
          <div>
            <p className="section-kicker">本周回顾</p>
            <h2 id="weekly-heading">学习周报</h2>
          </div>
          <span className="soft-badge">
            {weeklyReport
              ? `${Math.round(completionRate * 100)}% 完成`
              : "暂无数据"}
          </span>
        </div>
        {weeklyReport ? (
          <>
            <div className="weekly-metrics">
              <div>
                <strong>{tasksCompleted}</strong>
                <span>已完成</span>
              </div>
              <div>
                <strong>{tasksSkipped}</strong>
                <span>已跳过</span>
              </div>
              <div>
                <strong>{needsReview}</strong>
                <span>待复习</span>
              </div>
              <div>
                <strong>{tutorTurns}</strong>
                <span>分步提示</span>
              </div>
            </div>
            <div className="review-list">
              <strong>复习建议</strong>
              {mistakes.length > 0 ? (
                mistakes.map((item, index) => {
                  const mistake =
                    typeof item === "object" &&
                    item !== null &&
                    "mistake" in item
                      ? (item as { mistake?: unknown }).mistake
                      : null;
                  const schedule =
                    typeof item === "object" &&
                    item !== null &&
                    "schedule" in item
                      ? (item as { schedule?: unknown }).schedule
                      : null;
                  return (
                    <p key={readString(mistake, "id") ?? index}>
                      错题待复习 ·{" "}
                      {readString(mistake, "reason") ?? "需要再想一想"}
                      {readDateLabel(schedule, "due_at")
                        ? ` · 到期 ${readDateLabel(schedule, "due_at")}`
                        : ""}
                    </p>
                  );
                })
              ) : reviewItems.length > 0 ? (
                reviewItems.map((item, index) => (
                  <p key={readString(item, "session_id") ?? index}>
                    {readString(item, "task_title") ?? "数学任务"}
                    ：孩子主动标记为还需复习。
                  </p>
                ))
              ) : (
                <p>
                  {tasksAssigned > 0
                    ? "本周暂未标记需复习任务。"
                    : "完成一次学习后，这里会生成可追溯建议。"}
                </p>
              )}
            </div>
          </>
        ) : (
          <div className="empty-state compact">
            <span className="empty-icon">◌</span>
            <p>尚无周报，完成一次真实学习后会自动出现。</p>
          </div>
        )}
      </section>

      <footer className="footer-note">
        <span className="footer-spark">✦</span> 今天也只专注一小步{" "}
        <span className="footer-spark">✦</span>
      </footer>
    </main>
  );
}
