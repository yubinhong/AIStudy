import { ClockCounterClockwise } from "@phosphor-icons/react/dist/ssr";

import {
  readArray,
  readNumber,
  readObject,
  readString,
} from "@/lib/household-data";

function answerStateLabel(state: string) {
  if (state === "worked") return "有作答";
  if (state === "blank") return "确认空白";
  if (state === "answer_area_missing") return "未拍到作答区";
  return "作答不清楚";
}

function dateTimeLabel(value: string | null) {
  if (!value) return "最近";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("zh-CN", {
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    month: "numeric",
    timeZone: "Asia/Shanghai",
  }).format(date);
}

export function LearningRecordsTable({ records }: { records: unknown[] }) {
  if (records.length === 0) {
    return (
      <div className="empty-dashboard-state learning-history-empty">
        <ClockCounterClockwise size={30} weight="duotone" />
        <div>
          <strong>这个时间范围内没有学习记录</strong>
          <p>完成一次拍题和讲解后，这里会显示题目、作答状态和分步讲解。</p>
        </div>
      </div>
    );
  }

  return (
    <div className="activity-table" role="table" aria-label="学习记录">
      <div className="activity-table-head" role="row">
        <span role="columnheader">时间</span>
        <span role="columnheader">题目</span>
        <span role="columnheader">作答</span>
        <span role="columnheader">提示</span>
        <span role="columnheader">状态</span>
      </div>
      {records.map((detail, detailIndex) => {
        const question = readObject(detail, "question");
        const turns = readArray(detail, "tutor_turns");
        const state = readString(question, "answer_state") ?? "unclear";
        const questionId = readString(question, "id");
        return (
          <details
            className="activity-record"
            id={questionId ? `question-${questionId}` : undefined}
            key={questionId ?? detailIndex}
          >
            <summary role="row">
              <span className="record-time" role="cell">
                {dateTimeLabel(readString(question, "verified_at"))}
              </span>
              <span className="record-question" role="cell">
                {readString(question, "question_text") ?? "已确认数学题"}
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
              <div className="record-question-full">
                <strong>题目</strong>
                <p>{readString(question, "question_text") ?? "已确认数学题"}</p>
              </div>
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
                        第 {readNumber(turn, "level") ?? turnIndex + 1} 级讲解
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
                <p className="muted-copy">题目已确认，尚未产生讲解记录。</p>
              )}
            </div>
          </details>
        );
      })}
    </div>
  );
}
