import {
  CalendarBlank,
  ChartBar,
  ClockCounterClockwise,
} from "@phosphor-icons/react/dist/ssr";
import Link from "next/link";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { AdminShell } from "@/app/components/admin-shell";
import { ChineseLearningRecordsTable } from "@/app/components/chinese-learning-records-table";
import { LearningRecordsTable } from "@/app/components/learning-records-table";
import {
  loadChildren,
  loadChineseLearningDetails,
  loadLearningDetails,
  readNumber,
  readString,
} from "@/lib/household-data";
import {
  learningHistoryBounds,
  learningHistoryRange,
  selectedLearningDay,
} from "@/lib/learning-history";

export type LearningSubject = "math" | "chinese";

type LearningHistoryPageProps = {
  searchParams?: Promise<{ child?: string; date?: string }>;
  subject: LearningSubject;
};

const subjectCopy: Record<
  LearningSubject,
  { description: string; label: string }
> = {
  math: {
    label: "数学学习记录",
    description: "查看题目、作答状态和分步讲解",
  },
  chinese: {
    label: "语文学习记录",
    description: "查看孩子的答案、对错结果和复习安排",
  },
};

export default async function LearningHistoryPage({
  searchParams,
  subject,
}: LearningHistoryPageProps) {
  const session = (await cookies()).get("study_session");
  if (!session) redirect("/login");

  const parameters = await searchParams;
  const children = await loadChildren();
  const selectedChild =
    children.find((child) => readString(child, "id") === parameters?.child) ??
    children[0];
  const selectedChildId = readString(selectedChild, "id");
  const selectedDate = selectedLearningDay(parameters?.date);
  const range = learningHistoryRange(selectedDate);
  const records = selectedChildId
    ? subject === "math"
      ? await loadLearningDetails(selectedChildId, { ...range, limit: 500 })
      : await loadChineseLearningDetails(selectedChildId, {
          ...range,
          limit: 500,
        })
    : [];
  const { minDate, maxDate } = learningHistoryBounds();
  const childName = readString(selectedChild, "display_name") ?? "家庭空间";
  const grade = readNumber(selectedChild, "grade");
  const childMeta = grade ? `小学${grade}年级` : "当前孩子";
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
  const basePath = `/learning/${subject}`;
  const resetHref = selectedChildId
    ? `${basePath}?child=${encodeURIComponent(selectedChildId)}`
    : basePath;
  const copy = subjectCopy[subject];

  return (
    <AdminShell
      active="learning"
      activeLearningSubject={subject}
      childOptions={childOptions}
      childMeta={childMeta}
      childName={childName}
      childSwitchBaseHref={basePath}
      selectedChildId={selectedChildId ?? undefined}
    >
      <div className="page-header learning-history-header">
        <div>
          <p className="page-eyebrow">
            学习档案 / {subject === "math" ? "数学" : "语文"}
          </p>
          <h1>{copy.label}</h1>
          <p>
            {copy.description}，{childName}的详细记录保留 180 天。
          </p>
        </div>
      </div>

      <section className="dashboard-panel learning-history-panel">
        <div className="learning-history-toolbar">
          <div className="learning-period-copy">
            <p className="section-kicker">时间范围</p>
            <h2>{selectedDate ?? "最近 30 天"}</h2>
          </div>
          <form action={basePath} className="date-filter" method="get">
            {selectedChildId ? (
              <input name="child" type="hidden" value={selectedChildId} />
            ) : null}
            <div className="date-field">
              <label htmlFor={`${subject}-learning-date`}>选择日期</label>
              <input
                defaultValue={selectedDate ?? ""}
                id={`${subject}-learning-date`}
                max={maxDate}
                min={minDate}
                name="date"
                type="date"
              />
            </div>
            <button className="secondary-button" type="submit">
              <CalendarBlank size={17} /> 查看
            </button>
            {selectedDate ? (
              <Link className="row-action date-reset" href={resetHref}>
                <ClockCounterClockwise size={17} /> 返回近 30 天
              </Link>
            ) : null}
          </form>
        </div>
        <div className="learning-history-summary" aria-label="记录汇总">
          <span className="summary-icon" aria-hidden="true">
            <ChartBar size={18} weight="duotone" />
          </span>
          <div>
            <strong>{records.length}</strong>
            <span>{selectedDate ? "当天记录" : "近 30 天记录"}</span>
          </div>
          <span className="retention-note">逐题记录保留 180 天</span>
        </div>
        {subject === "math" ? (
          <LearningRecordsTable records={records} />
        ) : (
          <ChineseLearningRecordsTable records={records} />
        )}
      </section>
    </AdminShell>
  );
}
