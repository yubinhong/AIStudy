import {
  BookOpenText,
  CheckCircle,
  ClockCounterClockwise,
  XCircle,
} from "@phosphor-icons/react/dist/ssr";
import Link from "next/link";

import {
  readArray,
  readNumber,
  readObject,
  readString,
} from "@/lib/household-data";

const skillLabels: Record<string, string> = {
  character: "生字",
  expression: "表达",
  pinyin: "拼音",
  poem: "古诗",
  reading: "阅读",
  recitation: "背诵",
  sentence: "句子",
  vocabulary: "词语",
};

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

function responseLabel(response: unknown) {
  const choice = readString(response, "choice");
  if (choice) return choice;
  const text = readString(response, "text");
  if (text) return text;
  const answer = readString(response, "answer");
  if (answer) return answer;
  const tokens = readArray(response, "tokens");
  if (tokens.length > 0) return tokens.map(String).join(" / ");
  return "未填写答案";
}

function elapsedLabel(value: number | null) {
  if (value === null) return "耗时未记录";
  if (value < 1000) return `${value} 毫秒`;
  return `${Math.round(value / 1000)} 秒`;
}

function readBoolean(record: unknown, key: string) {
  if (typeof record !== "object" || record === null || !(key in record)) {
    return false;
  }
  return (record as Record<string, unknown>)[key] === true;
}

export function ChineseLearningRecordsTable({
  records,
}: {
  records: unknown[];
}) {
  if (records.length === 0) {
    return (
      <div className="empty-dashboard-state learning-history-empty">
        <span className="empty-state-icon" aria-hidden="true">
          <BookOpenText size={28} weight="duotone" />
        </span>
        <div>
          <strong>这个时间范围内没有语文答题记录</strong>
          <p>完成一次古诗抽查或其他语文练习后，这里会显示孩子的答题情况。</p>
          <Link className="empty-state-link" href="/">
            返回家长工作台
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div
      className="activity-table chinese-activity-table"
      role="table"
      aria-label="语文学习记录"
    >
      <div className="activity-table-head" role="row">
        <span role="columnheader">时间</span>
        <span role="columnheader">练习</span>
        <span role="columnheader">孩子的答案</span>
        <span role="columnheader">结果</span>
        <span role="columnheader">复习</span>
      </div>
      {records.map((detail, detailIndex) => {
        const attempt = readObject(detail, "attempt");
        const content = readObject(detail, "content");
        const result = readObject(attempt, "result");
        const review = readObject(detail, "review");
        const attemptId = readString(attempt, "id");
        const correct = readBoolean(result, "correct");
        const contentTitle = readString(content, "title") ?? "语文练习";
        const skill = skillLabels[readString(content, "skill") ?? ""] ?? "语文";
        const response = readObject(attempt, "response");
        const correctAnswer = readString(result, "correct_answer");
        const question = readString(content, "prompt") ?? "题目内容未记录";
        const passage = readString(content, "passage");
        return (
          <details
            className="activity-record"
            id={attemptId ? `chinese-attempt-${attemptId}` : undefined}
            key={attemptId ?? detailIndex}
          >
            <summary role="row">
              <span className="record-time" role="cell">
                {dateTimeLabel(readString(attempt, "created_at"))}
              </span>
              <span className="record-question" role="cell">
                <small>{skill}</small>
                {contentTitle}
              </span>
              <span className="record-answer" role="cell">
                {responseLabel(response)}
              </span>
              <span role="cell">
                <span
                  className={`answer-state ${correct ? "state-worked" : "state-unclear"}`}
                >
                  {correct ? "答对" : "答错"}
                </span>
              </span>
              <span role="cell">
                <span
                  className={`review-state ${review ? "" : "review-state-muted"}`}
                >
                  {review ? "已加入复习" : "无复习项"}
                </span>
              </span>
            </summary>
            <div className="record-expanded chinese-record-expanded">
              <div className="record-question-full">
                <strong>{contentTitle}</strong>
                {passage ? <p>{passage}</p> : null}
                <p>{question}</p>
              </div>
              <div className="chinese-answer-summary">
                <div>
                  <span>孩子的答案</span>
                  <strong>{responseLabel(response)}</strong>
                </div>
                <div>
                  <span>判定结果</span>
                  <strong
                    className={correct ? "answer-correct" : "answer-wrong"}
                  >
                    {correct ? "答对" : "答错"}
                  </strong>
                </div>
                <div>
                  <span>答题用时</span>
                  <strong>
                    {elapsedLabel(readNumber(attempt, "elapsed_ms"))}
                  </strong>
                </div>
              </div>
              {!correct && correctAnswer ? (
                <p className="chinese-correct-answer">
                  <strong>正确答案：</strong>
                  {correctAnswer}
                </p>
              ) : null}
              <div
                className={`chinese-result-callout ${correct ? "is-correct" : "is-wrong"}`}
              >
                {correct ? (
                  <CheckCircle size={20} weight="fill" />
                ) : (
                  <XCircle size={20} weight="fill" />
                )}
                <span>
                  {correct
                    ? "本次练习已答对。"
                    : "本次练习已答错，系统会按照复习安排再次出现。"}
                </span>
              </div>
              {review ? (
                <p className="muted-copy">
                  <ClockCounterClockwise size={16} />
                  下次复习：{dateTimeLabel(readString(review, "due_at"))}
                </p>
              ) : null}
            </div>
          </details>
        );
      })}
    </div>
  );
}
