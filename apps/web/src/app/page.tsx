import {
  ArrowRight,
  BookOpenText,
  CheckCircle,
  Lightbulb,
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
  loadChineseSkillReport,
  loadDevices,
  loadLearningDetails,
  loadMistakes,
  readArray,
  readNumber,
  readObject,
  readString,
} from "@/lib/household-data";
import { learningHistoryRange } from "@/lib/learning-history";

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
  const trendRange = learningHistoryRange(null, new Date(), 7);
  const [devices, mistakes, learningDetails, chineseSkillReport] =
    await Promise.all([
      loadDevices(),
      selectedChildId
        ? loadMistakes(selectedChildId, true)
        : Promise.resolve([]),
      selectedChildId
        ? loadLearningDetails(selectedChildId, { ...trendRange, limit: 200 })
        : Promise.resolve([]),
      selectedChildId
        ? loadChineseSkillReport(selectedChildId)
        : Promise.resolve(null),
    ]);

  const childName = readString(selectedChild, "display_name") ?? "家庭空间";
  const grade = readNumber(selectedChild, "grade");
  const childMeta = grade ? `小学${grade}年级` : "当前孩子";
  const trend = buildTrend(learningDetails);
  const tutorTurns = learningDetails.reduce<number>(
    (total, detail) => total + readArray(detail, "tutor_turns").length,
    0,
  );
  const chineseSkills = readArray(chineseSkillReport, "skills");
  const apiConnected = children.length > 0 || devices.length > 0;
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
          <span className="section-count">{mistakes.length} 项</span>
        </div>

        <div className="attention-list">
          <div className="attention-row" id="review">
            <span className="attention-icon warning">
              <WarningCircle size={24} weight="duotone" />
            </span>
            <div className="attention-copy due-question-copy">
              <strong>待复习错题</strong>
              <span>
                {mistakes.length > 0
                  ? `${mistakes.length} 道题已到复习时间，建议今天回顾`
                  : "目前没有到期错题，后续拍题讲解会在这里形成复习记录"}
              </span>
              {mistakes.length > 0 ? (
                <ol className="due-question-list">
                  {mistakes.map((item, index) => {
                    const question = readObject(item, "question");
                    const schedule = readObject(item, "schedule");
                    return (
                      <li key={readString(item, "id") ?? index}>
                        <span>
                          {readString(question, "question_text") ??
                            "已确认数学题"}
                        </span>
                        <small>
                          {readString(schedule, "due_at")
                            ? `到期：${new Intl.DateTimeFormat("zh-CN", {
                                day: "numeric",
                                month: "numeric",
                                timeZone: "Asia/Shanghai",
                              }).format(
                                new Date(readString(schedule, "due_at")!),
                              )}`
                            : "已到复习时间"}
                        </small>
                      </li>
                    );
                  })}
                </ol>
              ) : null}
            </div>
            <span
              className={
                mistakes.length > 0 ? "status-pill amber" : "status-pill"
              }
            >
              {mistakes.length > 0 ? `${mistakes.length} 题` : "已清空"}
            </span>
            <Link
              className="row-action"
              href={
                selectedChildId
                  ? `/learning?child=${encodeURIComponent(selectedChildId)}`
                  : "/learning"
              }
            >
              学习记录 <ArrowRight size={16} />
            </Link>
          </div>
        </div>
      </section>

      <section className="dashboard-grid" id="weekly-report">
        <article className="dashboard-panel trend-panel full-grid-panel">
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
              <p>拍题讲解</p>
              <strong>{learningDetails.length}</strong>
            </div>
            <div>
              <span className="metric-icon">
                <Lightbulb size={20} />
              </span>
              <p>分步提示</p>
              <strong>{tutorTurns}</strong>
            </div>
            <div>
              <p>待复习</p>
              <strong>{mistakes.length}</strong>
            </div>
          </div>
          <LearningTrendChart data={trend} />
        </article>
      </section>

      <section className="dashboard-panel" id="chinese-skill-report">
        <div className="section-heading">
          <div>
            <p className="section-kicker">语文技能报告</p>
            <h2>按技能查看作答与复习</h2>
          </div>
          <span className="quiet-label">仅汇总已追加学习事实</span>
        </div>
        {chineseSkills.length === 0 ? (
          <div className="empty-dashboard-state">
            <div>
              <strong>还没有语文技能记录</strong>
              <p>
                完成语文练习后，这里会显示按拼音、字词、阅读和古诗文汇总的作答与到期复习。
              </p>
            </div>
          </div>
        ) : (
          <div className="attention-list" role="list" aria-label="语文技能报告">
            {chineseSkills.map((skill, index) => {
              const attempts = readNumber(skill, "attempts") ?? 0;
              const correctAttempts =
                readNumber(skill, "correct_attempts") ?? 0;
              const dueReviews = readNumber(skill, "due_reviews") ?? 0;
              return (
                <div
                  className="attention-row"
                  key={readString(skill, "skill") ?? index}
                  role="listitem"
                >
                  <span className="attention-icon success">
                    <BookOpenText size={24} weight="duotone" />
                  </span>
                  <div className="attention-copy">
                    <strong>
                      {chineseSkillLabel(readString(skill, "skill"))}
                    </strong>
                    <span>{`已作答 ${attempts} 次，正确 ${correctAttempts} 次`}</span>
                  </div>
                  <span
                    className={
                      dueReviews > 0 ? "status-pill amber" : "status-pill"
                    }
                  >
                    {dueReviews > 0 ? `${dueReviews} 项待复习` : "暂无到期复习"}
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </section>

      <section className="dashboard-panel curriculum-callout">
        <span className="attention-icon success">
          <BookOpenText size={24} weight="duotone" />
        </span>
        <div>
          <strong>教材范围已接入拍题讲解</strong>
          <p>
            已发布且审核通过的知识图谱会约束错题讲解，避免超出当前教材范围。
          </p>
        </div>
        <Link className="secondary-button" href="/curriculum">
          教材管理 <ArrowRight size={16} />
        </Link>
      </section>
    </AdminShell>
  );
}

function chineseSkillLabel(skill: string | null) {
  const labels: Record<string, string> = {
    character: "生字",
    pinyin: "拼音",
    reading: "阅读",
    recitation: "古诗文",
    sentence: "句子",
    vocabulary: "词语",
  };
  return skill ? (labels[skill] ?? "语文表达") : "语文表达";
}
