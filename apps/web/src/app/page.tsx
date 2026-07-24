import {
  ArrowRight,
  BookOpenText,
  CheckCircle,
  ClipboardText,
  ClockCounterClockwise,
  DeviceMobile,
  Flag,
  Lightbulb,
  Target,
  WarningCircle,
} from "@phosphor-icons/react/dist/ssr";
import Link from "next/link";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { AdminShell } from "@/app/components/admin-shell";
import {
  LearningTrendChart,
  type LearningTrendPoint,
} from "@/app/components/learning-trend-chart";
import {
  loadChildren,
  loadDevices,
  loadLearningDetails,
  loadMistakes,
  loadTasks,
  loadWeeklyReport,
  readArray,
  readDateLabel,
  readNumber,
  readString,
} from "@/lib/household-data";

function answerStateLabel(state: string) {
  if (state === "worked") return "有作答";
  if (state === "blank") return "确认空白";
  if (state === "answer_area_missing") return "未拍到作答区";
  return "作答不清楚";
}

function shanghaiDateKey(date: Date) {
  return new Intl.DateTimeFormat("en-CA", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    timeZone: "Asia/Shanghai",
  }).format(date);
}

function buildTrend(learningDetails: unknown[]): LearningTrendPoint[] {
  const today = new Date();
  const points = Array.from({ length: 7 }, (_, index) => {
    const date = new Date(today);
    date.setDate(today.getDate() - (6 - index));
    return {
      key: shanghaiDateKey(date),
      label: new Intl.DateTimeFormat("zh-CN", {
        weekday: "short",
        timeZone: "Asia/Shanghai",
      }).format(date),
      questions: 0,
      hints: 0,
    };
  });
  const pointByDate = new Map(points.map((point) => [point.key, point]));
  for (const detail of learningDetails) {
    const question =
      typeof detail === "object" && detail !== null && "question" in detail
        ? (detail as { question?: unknown }).question
        : null;
    const verifiedAt = readString(question, "verified_at");
    if (!verifiedAt) continue;
    const date = new Date(verifiedAt);
    if (Number.isNaN(date.getTime())) continue;
    const point = pointByDate.get(shanghaiDateKey(date));
    if (!point) continue;
    point.questions += 1;
    point.hints += readArray(detail, "tutor_turns").length;
  }
  return points.map(({ label, questions, hints }) => ({
    label,
    questions,
    hints,
  }));
}

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
  const [tasks, devices, weeklyReport, mistakes, learningDetails] =
    await Promise.all([
      loadTasks(selectedChildId ?? undefined),
      loadDevices(),
      selectedChildId
        ? loadWeeklyReport(selectedChildId)
        : Promise.resolve(null),
      selectedChildId
        ? loadMistakes(selectedChildId, true)
        : Promise.resolve([]),
      selectedChildId
        ? loadLearningDetails(selectedChildId)
        : Promise.resolve([]),
    ]);

  const childName = readString(selectedChild, "display_name") ?? "家庭空间";
  const grade = readNumber(selectedChild, "grade");
  const childMeta = grade ? `小学${grade}年级` : "当前孩子";
  const tasksAssigned =
    readNumber(weeklyReport, "tasks_assigned") ?? tasks.length;
  const tasksCompleted = readNumber(weeklyReport, "tasks_completed") ?? 0;
  const needsReview =
    readNumber(weeklyReport, "needs_review") ?? mistakes.length;
  const tutorTurns = readNumber(weeklyReport, "tutor_turns") ?? 0;
  const completionRate = readNumber(weeklyReport, "completion_rate") ?? 0;
  const trend = buildTrend(learningDetails);
  const firstTask = tasks[0];
  const apiConnected =
    children.length > 0 || tasks.length > 0 || devices.length > 0;
  const childOptions = children.flatMap((child) => {
    const id = readString(child, "id");
    if (!id) return [];
    const childGrade = readNumber(child, "grade");
    return [
      {
        id,
        name: readString(child, "display_name") ?? "孩子",
        meta: childGrade ? `小学${childGrade}年级` : "孩子档案",
      },
    ];
  });

  return (
    <AdminShell
      active="overview"
      childOptions={childOptions}
      childMeta={childMeta}
      childName={childName}
      childSwitchBaseHref="/"
      connectionLabel={apiConnected ? "本地服务已连接" : "等待本地服务"}
      selectedChildId={selectedChildId ?? undefined}
    >
      <div className="page-header">
        <div>
          <p className="page-eyebrow">家长工作台</p>
          <h1>今天，先关注这几件事</h1>
          <p>查看 {childName} 的学习进度，把需要处理的事情放在最前面。</p>
        </div>
      </div>

      <section className="dashboard-panel attention-panel" id="today-focus">
        <div className="section-heading">
          <div>
            <p className="section-kicker">优先事项</p>
            <h2>今日需要关注</h2>
          </div>
          <span className="section-count">
            {mistakes.length + tasks.length + 1} 项
          </span>
        </div>

        <div className="attention-list">
          <div className="attention-row" id="review">
            <span className="attention-icon warning">
              <WarningCircle size={24} weight="duotone" />
            </span>
            <div className="attention-copy">
              <strong>待复习错题</strong>
              <span>
                {mistakes.length > 0
                  ? `${mistakes.length} 道题已到复习时间，建议今天回顾`
                  : "目前没有到期错题，可以按今天的任务继续学习"}
              </span>
            </div>
            <span
              className={
                mistakes.length > 0 ? "status-pill amber" : "status-pill"
              }
            >
              {mistakes.length > 0 ? `${mistakes.length} 题` : "已清空"}
            </span>
            <Link className="row-action" href="#learning-details">
              查看记录 <ArrowRight size={16} />
            </Link>
          </div>

          <div className="attention-row">
            <span className="attention-icon success">
              <ClipboardText size={24} weight="duotone" />
            </span>
            <div className="attention-copy">
              <strong>今日学习任务</strong>
              <span>
                {firstTask
                  ? (readString(firstTask, "title") ?? "今天的数学任务")
                  : "还没有安排今天的学习任务"}
              </span>
            </div>
            <span className="status-pill">{tasks.length} 项</span>
            <Link className="row-action" href="/accounts#tasks">
              安排任务 <ArrowRight size={16} />
            </Link>
          </div>

          <div className="attention-row">
            <span className="attention-icon neutral">
              <Target size={24} weight="duotone" />
            </span>
            <div className="attention-copy">
              <strong>本周学习目标</strong>
              <span>
                已完成 {tasksCompleted} / {tasksAssigned || 0}{" "}
                项任务，继续保持稳定节奏
              </span>
            </div>
            <span
              className={
                completionRate >= 0.8 ? "status-pill" : "status-pill amber"
              }
            >
              {weeklyReport ? `${Math.round(completionRate * 100)}%` : "待积累"}
            </span>
            <Link className="row-action" href="#weekly-report">
              查看周报 <ArrowRight size={16} />
            </Link>
          </div>
        </div>
      </section>

      <section className="dashboard-grid" id="weekly-report">
        <article className="dashboard-panel trend-panel">
          <div className="section-heading">
            <div>
              <p className="section-kicker">本周回顾</p>
              <h2>本周学习趋势</h2>
            </div>
            <span className="quiet-label">过去 7 天</span>
          </div>
          <div className="trend-metrics">
            <div>
              <span className="metric-icon">
                <CheckCircle size={20} />
              </span>
              <p>完成任务</p>
              <strong>{tasksCompleted}</strong>
            </div>
            <div>
              <span className="metric-icon">
                <Lightbulb size={20} />
              </span>
              <p>分步提示</p>
              <strong>{tutorTurns}</strong>
            </div>
            <div>
              <span className="metric-icon">
                <Flag size={20} />
              </span>
              <p>待复习</p>
              <strong>{Math.max(needsReview, mistakes.length)}</strong>
            </div>
          </div>
          <LearningTrendChart data={trend} />
        </article>

        <article
          className="dashboard-panel activity-panel"
          id="learning-details"
        >
          <div className="section-heading">
            <div>
              <p className="section-kicker">逐题记录</p>
              <h2>最近学习记录</h2>
            </div>
            <span className="quiet-label">
              最近 {learningDetails.length} 题
            </span>
          </div>

          {learningDetails.length > 0 ? (
            <div
              className="activity-table"
              role="table"
              aria-label="最近学习记录"
            >
              <div className="activity-table-head" role="row">
                <span role="columnheader">时间</span>
                <span role="columnheader">题目</span>
                <span role="columnheader">作答</span>
                <span role="columnheader">提示</span>
                <span role="columnheader">状态</span>
              </div>
              {learningDetails.slice(0, 7).map((detail, detailIndex) => {
                const question =
                  typeof detail === "object" &&
                  detail !== null &&
                  "question" in detail
                    ? (detail as { question?: unknown }).question
                    : null;
                const turns = readArray(detail, "tutor_turns");
                const state = readString(question, "answer_state") ?? "unclear";
                return (
                  <details
                    className="activity-record"
                    key={readString(question, "id") ?? detailIndex}
                  >
                    <summary role="row">
                      <span className="record-time" role="cell">
                        {readDateLabel(question, "verified_at") ?? "最近"}
                      </span>
                      <span className="record-question" role="cell">
                        {readString(question, "question_text") ??
                          "已确认数学题"}
                      </span>
                      <span role="cell">
                        <span className={`answer-state state-${state}`}>
                          {answerStateLabel(state)}
                        </span>
                      </span>
                      <span role="cell">{turns.length} 次</span>
                      <span role="cell">
                        <span className="review-state">
                          {state === "worked" || state === "blank"
                            ? "已记录"
                            : "需确认"}
                        </span>
                      </span>
                    </summary>
                    <div className="record-expanded">
                      {readString(question, "answer_text") ? (
                        <p>
                          <strong>识别作答：</strong>
                          {readString(question, "answer_text")}
                        </p>
                      ) : null}
                      {turns.length > 0 ? (
                        turns.map((turn, turnIndex) => {
                          const steps = readArray(turn, "solution_steps");
                          return (
                            <div
                              className="tutor-summary"
                              key={readString(turn, "id") ?? turnIndex}
                            >
                              <strong>
                                第 {readNumber(turn, "level") ?? turnIndex + 1}{" "}
                                级讲解
                              </strong>
                              <p>{readString(turn, "prompt")}</p>
                              {steps.length > 0 ? (
                                <ol>
                                  {steps.map((step, stepIndex) => (
                                    <li key={stepIndex}>{String(step)}</li>
                                  ))}
                                </ol>
                              ) : null}
                              {readString(turn, "direct_answer") ? (
                                <p className="final-answer">
                                  答案：{readString(turn, "direct_answer")}
                                </p>
                              ) : null}
                              {readString(turn, "verification") ? (
                                <p className="verification">
                                  验算：{readString(turn, "verification")}
                                </p>
                              ) : null}
                            </div>
                          );
                        })
                      ) : (
                        <p className="muted-copy">
                          题目已确认，尚未产生讲解记录。
                        </p>
                      )}
                    </div>
                  </details>
                );
              })}
            </div>
          ) : (
            <div className="empty-dashboard-state">
              <ClockCounterClockwise size={30} weight="duotone" />
              <div>
                <strong>还没有逐题记录</strong>
                <p>
                  完成一次拍题和讲解后，这里会显示作答状态、提示与完整解答。
                </p>
              </div>
            </div>
          )}

          <div className="panel-note">
            <DeviceMobile size={18} />
            {devices.length > 0
              ? `${devices.length} 台家庭设备已连接，记录会自动同步。`
              : "孩子端连接后，学习记录会自动同步到这里。"}
          </div>
        </article>
      </section>

      <section className="dashboard-panel curriculum-callout">
        <span className="attention-icon success">
          <BookOpenText size={24} weight="duotone" />
        </span>
        <div>
          <strong>教材范围已接入任务推荐</strong>
          <p>
            已发布小节会进入家长审批的任务推荐；文档正文解析和讲解引用尚未启用。
          </p>
        </div>
        <Link className="secondary-button" href="/curriculum">
          教材与任务 <ArrowRight size={16} />
        </Link>
      </section>
    </AdminShell>
  );
}
