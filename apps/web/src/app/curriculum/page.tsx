"use client";

import {
  BookOpenText,
  CheckCircle,
  FileArrowUp,
  Files,
  MagicWand,
  Plus,
  SealCheck,
  Trash,
  UploadSimple,
  XCircle,
} from "@phosphor-icons/react";
import Image from "next/image";
import { FormEvent, useEffect, useState } from "react";

import { AdminShell } from "@/app/components/admin-shell";
import { csrfHeaders } from "../../lib/csrf";
import { idempotencyKey } from "../../lib/idempotency-key";

type Child = { id: string; display_name: string; grade: number };
type Snapshot = {
  id: string;
  status: "draft" | "published" | "rejected";
  textbook_version: string;
  term: string;
  sections: Array<{
    title: string;
    chapter: string;
    learning_objectives: string[];
  }>;
};

const maxCurriculumDocumentBytes = 50 * 1024 * 1024;
type Recommendation = {
  id: string;
  title: string;
  reason: string;
  knowledge_point: string;
  scheduled_for: string;
  estimated_minutes: number;
  source_type:
    | "manual"
    | "mistake_review"
    | "curriculum_exercise"
    | "mixed_plan";
  exercises: Array<{
    question_text: string;
    source_type: "mistake" | "curriculum";
    snapshot_id: string | null;
    source_title: string | null;
    source_page: number | null;
    visual_description: string | null;
    requires_visual_context: boolean;
  }>;
  status: "pending" | "approved" | "rejected";
  task_id: string | null;
};

type ParsedPage = {
  page_number: number;
  title: string;
  text: string;
  confidence: number;
  image_available: boolean;
  image_path: string | null;
};

type KnowledgeExercise = {
  source_key: string;
  page_number: number;
  question_text: string;
  visual_description: string | null;
  requires_visual_context: boolean;
  difficulty: "basic" | "medium" | "advanced";
  confidence: number;
};

type KnowledgePoint = {
  id: string;
  knowledge_key: string;
  chapter_title: string;
  section_title: string;
  title: string;
  summary: string;
  learning_objectives: string[];
  prerequisites: string[];
  page_numbers: number[];
  exercises: KnowledgeExercise[];
  confidence: number;
  status: "draft" | "approved" | "rejected";
};

type KnowledgeMap = {
  id: string;
  snapshot_id: string;
  status: "queued" | "analyzing" | "needs_review" | "approved" | "failed";
  book_summary: string | null;
  page_count: number;
  analyzed_page_count: number;
  error_code: string | null;
  knowledge_points: KnowledgePoint[];
};

function isPendingDocumentParsing(snapshot: Snapshot) {
  return snapshot.sections.some((section) => section.chapter === "待解析文档");
}

function hasParsedDocumentPages(snapshot: Snapshot) {
  return snapshot.sections.some((section) =>
    /^第\s*\d+\s*页$/.test(section.chapter),
  );
}

function readerParagraphs(text: string) {
  const lines = text
    .replace(/\r/g, "")
    .split(/\n+/)
    .map((line) => line.replace(/\s{2,}/g, " ").trim())
    .filter(Boolean);
  if (lines.length > 1) return lines;
  return (text.match(/[^。！？；]+[。！？；]?/gu) ?? [text])
    .map((line) => line.replace(/\s{2,}/g, " ").trim())
    .filter(Boolean);
}

function requestedChildId(children: Child[]) {
  const requested = new URLSearchParams(window.location.search).get("child");
  return children.some((child) => child.id === requested) ? requested : null;
}

export default function CurriculumPage() {
  const [children, setChildren] = useState<Child[]>([]);
  const [childId, setChildId] = useState("");
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [textbookVersion, setTextbookVersion] = useState("数学教材-本地版");
  const [term, setTerm] = useState("上学期");
  const [sectionTitle, setSectionTitle] = useState("");
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [previewSnapshot, setPreviewSnapshot] = useState<Snapshot | null>(null);
  const [previewPages, setPreviewPages] = useState<ParsedPage[]>([]);
  const [previewPageNumber, setPreviewPageNumber] = useState<number | null>(
    null,
  );
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [knowledgeMaps, setKnowledgeMaps] = useState<
    Record<string, KnowledgeMap | undefined>
  >({});
  const [selectedRecommendation, setSelectedRecommendation] =
    useState<Recommendation | null>(null);

  async function loadChildren() {
    const response = await fetch("/api/children/management", {
      cache: "no-store",
    });
    if (!response.ok) return;
    const aggregates = (await response.json()) as Array<{ child: Child }>;
    const values = aggregates.map((item) => item.child);
    setChildren(values);
    setChildId(
      (current) => requestedChildId(values) || current || values[0]?.id || "",
    );
  }

  async function loadData(selected = childId) {
    if (!selected) return;
    const [curriculum, recommendation] = await Promise.all([
      fetch(`/api/curriculum/${selected}`, { cache: "no-store" }),
      fetch(`/api/recommendations/${selected}`, { cache: "no-store" }),
    ]);
    if (curriculum.ok) {
      const values = (await curriculum.json()) as Snapshot[];
      setSnapshots(values);
      const entries = await Promise.all(
        values.map(async (snapshot) => {
          const response = await fetch(
            `/api/curriculum/${selected}/snapshots/${snapshot.id}/analysis`,
            { cache: "no-store" },
          );
          return [
            snapshot.id,
            response.ok ? ((await response.json()) as KnowledgeMap) : undefined,
          ] as const;
        }),
      );
      setKnowledgeMaps(Object.fromEntries(entries));
    }
    if (recommendation.ok) {
      setRecommendations((await recommendation.json()) as Recommendation[]);
    }
  }

  useEffect(() => {
    const timer = window.setTimeout(() => void loadChildren(), 0);
    return () => window.clearTimeout(timer);
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => void loadData(), 0);
    return () => window.clearTimeout(timer);
    // loadData intentionally reads the selected child snapshot at invocation time.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [childId]);

  async function importDraft(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!childId || !sectionTitle.trim()) return;
    const payload = {
      filename: `${textbookVersion}.json`,
      media_type: "application/json",
      byte_size: sectionTitle.length,
      content_sha256: "0".repeat(64),
      authorization_statement:
        "家庭自用教材，已确认来源和使用授权，并确认文件不含儿童姓名、个人批注或其他个人信息",
      grade: children.find((child) => child.id === childId)?.grade ?? 3,
      textbook_version: textbookVersion,
      term,
      sections: [
        {
          title: sectionTitle.trim(),
          chapter: "家长导入",
          learning_objectives: ["理解本节数学概念", "能独立完成基础题"],
        },
      ],
    };
    const response = await fetch(`/api/curriculum/${childId}`, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "Idempotency-Key": idempotencyKey("web-curriculum"),
        ...csrfHeaders(),
      },
      body: JSON.stringify(payload),
    });
    setMessage(
      response.ok
        ? "教材已解析为草稿，请审核后发布"
        : "教材导入失败，请检查内容",
    );
    if (response.ok) {
      setSectionTitle("");
      await loadData();
    }
  }

  async function uploadDocuments(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!childId || selectedFiles.length === 0 || uploading) return;
    const child = children.find((item) => item.id === childId);
    const form = new FormData();
    form.append("grade", String(child?.grade ?? 3));
    form.append("textbook_version", textbookVersion);
    form.append("term", term);
    form.append(
      "authorization_statement",
      "家庭自用教材，已确认来源和使用授权，并确认文件不含儿童姓名、个人批注或其他个人信息",
    );
    selectedFiles.forEach((file) => form.append("files", file, file.name));
    setUploading(true);
    try {
      const response = await fetch(`/api/curriculum/${childId}/upload`, {
        method: "POST",
        headers: {
          "Idempotency-Key": idempotencyKey("web-curriculum-files"),
          ...csrfHeaders(),
        },
        body: form,
      });
      const failure = (await response.json().catch(() => null)) as {
        detail?: string;
        message?: string;
      } | null;
      setMessage(
        response.ok
          ? `已上传 ${selectedFiles.length} 个文件。服务端将保留原页图像、调用 AI 归纳整本教材知识点；家长审核前不会用于讲解或任务。`
          : response.status === 413 || failure?.detail?.includes("too large")
            ? "上传失败：单个 PDF 上限为 50 MiB（52.4 MB），请重新选择不超过该大小的文件。"
            : "文件上传失败，请检查 PDF 格式、大小和登录状态",
      );
      if (response.ok) {
        setSelectedFiles([]);
        await loadData();
      }
    } finally {
      setUploading(false);
    }
  }

  async function publish(snapshotId: string) {
    const response = await fetch(
      `/api/curriculum/${childId}/snapshots/${snapshotId}/publish`,
      {
        method: "POST",
        headers: {
          "Idempotency-Key": idempotencyKey("web-publish"),
          ...csrfHeaders(),
        },
      },
    );
    setMessage(
      response.ok
        ? "教材已发布；完整解析正文现在可用于错题讲解和智能任务推荐"
        : "发布失败：文档正文尚未解析，或服务暂时不可用",
    );
    if (response.ok) await loadData();
  }

  async function deleteSnapshot(snapshot: Snapshot) {
    if (
      !childId ||
      !window.confirm(
        `删除“${snapshot.textbook_version}”及其私有 PDF、解析结果和待审核推荐？此操作不可恢复。`,
      )
    ) {
      return;
    }
    const response = await fetch(
      `/api/curriculum/${childId}/snapshots/${snapshot.id}`,
      {
        method: "DELETE",
        headers: {
          "Idempotency-Key": idempotencyKey("web-curriculum-delete"),
          ...csrfHeaders(),
        },
      },
    );
    setMessage(
      response.ok
        ? "教材、私有源文件和解析结果已删除。"
        : "删除失败：私有源文件或服务暂时不可用，请稍后重试。",
    );
    if (response.ok) await loadData();
  }

  async function openSnapshotPreview(snapshot: Snapshot, initialPage?: number) {
    setPreviewSnapshot(snapshot);
    setPreviewPages([]);
    setPreviewPageNumber(null);
    setPreviewLoading(true);
    setPreviewError(null);
    try {
      const response = await fetch(
        `/api/curriculum/${childId}/snapshots/${snapshot.id}/pages`,
        { cache: "no-store" },
      );
      if (!response.ok) {
        setPreviewError("暂时无法读取解析文档，请稍后重试。");
        return;
      }
      const pages = (await response.json()) as ParsedPage[];
      setPreviewPages(pages);
      setPreviewPageNumber(
        pages.some((page) => page.page_number === initialPage)
          ? (initialPage ?? null)
          : (pages[0]?.page_number ?? null),
      );
    } catch {
      setPreviewError("暂时无法读取解析文档，请检查服务连接后重试。");
    } finally {
      setPreviewLoading(false);
    }
  }

  async function analyzeSnapshot(snapshot: Snapshot) {
    const response = await fetch(
      `/api/curriculum/${childId}/snapshots/${snapshot.id}/analysis`,
      {
        method: "POST",
        headers: {
          "Idempotency-Key": idempotencyKey("web-curriculum-analysis"),
          ...csrfHeaders(),
        },
      },
    );
    setMessage(
      response.ok
        ? "已进入 AI 教材理解队列：将结合每页原图和文字，归纳整本教材知识点。"
        : "无法启动教材理解：请确认 PDF 已完成本地解析且尚未发布。",
    );
    await loadData();
  }

  async function approveKnowledge(snapshot: Snapshot) {
    const response = await fetch(
      `/api/curriculum/${childId}/snapshots/${snapshot.id}/analysis/approve`,
      {
        method: "POST",
        headers: {
          "Idempotency-Key": idempotencyKey("web-curriculum-analysis-approve"),
          ...csrfHeaders(),
        },
      },
    );
    setMessage(
      response.ok
        ? "知识图谱已批准；现在可以发布教材，并据此匹配错题和生成任务。"
        : "知识图谱尚未分析完成，暂时不能批准。",
    );
    await loadData();
  }

  async function generateRecommendations() {
    const response = await fetch(`/api/recommendations/${childId}`, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "Idempotency-Key": idempotencyKey("web-recommend"),
        ...csrfHeaders(),
      },
      body: JSON.stringify({ child_id: childId }),
    });
    if (response.ok) {
      const generated = (await response.json()) as Recommendation[];
      setMessage(
        generated.length > 0
          ? `已根据开放错题、薄弱知识点和已批准教材题目生成 ${generated.length} 条学习计划，请审核`
          : snapshots.some(
                (snapshot) =>
                  snapshot.status === "published" &&
                  hasParsedDocumentPages(snapshot),
              )
            ? "已解析的 PDF 中暂未识别到可下发的练习题，请检查教材页是否包含题干。"
            : "当前发布的是未解析正文的旧教材范围，不能生成具体题；请删除该范围后重新上传 PDF，等待解析完成并审核发布。",
      );
      await loadData();
      return;
    }
    const failure = (await response.json().catch(() => null)) as {
      message?: string;
    } | null;
    setMessage(
      failure?.message ===
        "published curriculum has no approved AI knowledge map"
        ? "请先打开教材，审核并批准 AI 归纳的知识点，再生成推荐。"
        : failure?.message ===
            "intelligent recommendation provider is not configured"
          ? "NewAPI 尚未配置，无法生成智能推荐"
          : "智能推荐生成失败：模型计划未通过来源校验，请稍后重试",
    );
  }

  async function decide(
    recommendationId: string,
    decision: "approve" | "reject",
  ) {
    const response = await fetch(
      `/api/recommendations/${childId}/${recommendationId}/decision`,
      {
        method: "POST",
        headers: {
          "content-type": "application/json",
          "Idempotency-Key": idempotencyKey("web-decision"),
          ...csrfHeaders(),
        },
        body: JSON.stringify({ decision }),
      },
    );
    setMessage(
      response.ok
        ? decision === "approve"
          ? "推荐已按计划日期下发到孩子端"
          : "推荐已忽略"
        : "处理推荐失败",
    );
    if (response.ok) {
      setSelectedRecommendation(null);
      await loadData();
    }
  }

  const currentChild = children.find((child) => child.id === childId);
  const previewPage =
    previewPages.find((page) => page.page_number === previewPageNumber) ??
    previewPages[0] ??
    null;
  const previewPageIndex = previewPage
    ? previewPages.findIndex(
        (page) => page.page_number === previewPage.page_number,
      )
    : -1;
  const previewKnowledge = previewSnapshot
    ? knowledgeMaps[previewSnapshot.id]
    : undefined;

  return (
    <AdminShell
      active="curriculum"
      childOptions={children.map((child) => ({
        id: child.id,
        meta: `小学${child.grade}年级`,
        name: child.display_name,
      }))}
      childMeta={currentChild ? `小学${currentChild.grade}年级` : "教材范围"}
      childName={currentChild?.display_name ?? "家庭空间"}
      childSwitchBaseHref="/curriculum"
      selectedChildId={currentChild?.id}
    >
      <div className="page-header">
        <div>
          <p className="page-eyebrow">教材与任务</p>
          <h1>教材范围管理</h1>
          <p>
            PDF 解析并发布后，系统会结合全部错题选择章节和具体练习，生成未来 7
            天的待审核计划。
          </p>
        </div>
        <span className="header-stat">
          <BookOpenText size={19} />
          {
            snapshots.filter((snapshot) => snapshot.status === "published")
              .length
          }{" "}
          个已发布范围
        </span>
      </div>

      {message ? (
        <div className="notice-banner" role="status">
          {message}
        </div>
      ) : null}

      <section className="curriculum-grid">
        <article className="dashboard-panel upload-panel">
          <div className="section-heading">
            <div>
              <p className="section-kicker">多文档导入</p>
              <h2>上传教材文档</h2>
            </div>
            <span className="section-icon">
              <Files size={22} />
            </span>
          </div>
          <form onSubmit={uploadDocuments} className="auth-form">
            <div className="upload-dropzone">
              <FileArrowUp size={34} weight="duotone" />
              <strong>选择一个或多个教材文件</strong>
              <p>
                首版支持 PDF，单个文件不超过 50 MiB（52.4 MB），可一次选择多个
                PDF。
              </p>
              <p className="upload-boundary-note">
                文件会先私有保存并进入待解析状态；正文解析和家长审核完成后才可发布。
              </p>
              <label className="file-picker">
                <UploadSimple size={18} />
                选择文件
                <input
                  type="file"
                  multiple
                  accept=".pdf,application/pdf"
                  onChange={(event) => {
                    const files = Array.from(event.target.files ?? []);
                    const oversized = files.find(
                      (file) => file.size > maxCurriculumDocumentBytes,
                    );
                    if (oversized) {
                      setSelectedFiles([]);
                      setMessage(
                        `“${oversized.name}”超过单个 PDF 50 MiB（52.4 MB）上限。`,
                      );
                      event.currentTarget.value = "";
                      return;
                    }
                    setMessage(null);
                    setSelectedFiles(files);
                  }}
                  disabled={!childId || uploading}
                />
              </label>
            </div>
            {selectedFiles.length > 0 ? (
              <div className="selected-files" aria-live="polite">
                <strong>已选择 {selectedFiles.length} 个文件</strong>
                {selectedFiles.map((file) => (
                  <span key={`${file.name}-${file.size}`}>{file.name}</span>
                ))}
              </div>
            ) : null}
            <button
              className="primary-button"
              type="submit"
              disabled={!childId || selectedFiles.length === 0 || uploading}
            >
              <UploadSimple size={18} />
              {uploading ? "上传处理中…" : "上传并导入为草稿"}
            </button>
          </form>
        </article>

        <article className="dashboard-panel form-panel">
          <div className="section-heading">
            <div>
              <p className="section-kicker">小范围补充</p>
              <h2>手工导入小节</h2>
            </div>
            <span className="section-icon">
              <BookOpenText size={22} />
            </span>
          </div>
          <form onSubmit={importDraft} className="auth-form">
            <label>
              教材版本
              <input
                value={textbookVersion}
                onChange={(event) => setTextbookVersion(event.target.value)}
                required
              />
            </label>
            <label>
              学期
              <input
                value={term}
                onChange={(event) => setTerm(event.target.value)}
                required
              />
            </label>
            <label>
              本次导入的小节
              <input
                value={sectionTitle}
                onChange={(event) => setSectionTitle(event.target.value)}
                placeholder="例如：分数的初步认识"
                required
              />
            </label>
            <button
              className="secondary-button wide-button"
              type="submit"
              disabled={!childId}
            >
              <Plus size={18} />
              手工导入小节
            </button>
          </form>
        </article>
      </section>

      <section className="curriculum-grid lower-grid">
        <article className="dashboard-panel">
          <div className="section-heading">
            <div>
              <p className="section-kicker">审核发布</p>
              <h2>教材快照</h2>
            </div>
            <span className="quiet-label">{snapshots.length} 个版本</span>
          </div>
          <div className="snapshot-list">
            {snapshots.length === 0 ? (
              <p className="muted-copy">还没有导入教材。</p>
            ) : null}
            {snapshots.map((snapshot) => (
              <article className="snapshot-row" key={snapshot.id}>
                <span className="snapshot-icon">
                  <BookOpenText size={20} />
                </span>
                <div className="task-details">
                  <strong>{snapshot.textbook_version}</strong>
                  <span>
                    {snapshot.term} ·{" "}
                    {knowledgeMaps[snapshot.id]
                      ? knowledgeMaps[snapshot.id]?.status === "approved"
                        ? `知识图谱已批准 · ${knowledgeMaps[snapshot.id]?.knowledge_points.length ?? 0} 个知识点`
                        : knowledgeMaps[snapshot.id]?.status === "needs_review"
                          ? `AI 已理解 ${knowledgeMaps[snapshot.id]?.analyzed_page_count ?? 0} 页 · 待家长审核`
                          : knowledgeMaps[snapshot.id]?.status === "failed"
                            ? "AI 教材理解失败 · 可安全重试"
                            : `AI 正在理解教材 · ${knowledgeMaps[snapshot.id]?.analyzed_page_count ?? 0}/${knowledgeMaps[snapshot.id]?.page_count ?? 0} 页`
                      : isPendingDocumentParsing(snapshot)
                        ? "正在等待 PDF 本地解析"
                        : `已录入 ${snapshot.sections.length} 个小节`}
                  </span>
                </div>
                <div className="inline-actions">
                  {knowledgeMaps[snapshot.id] ? (
                    <button
                      className="secondary-button compact-button"
                      type="button"
                      onClick={() => void openSnapshotPreview(snapshot)}
                    >
                      <BookOpenText size={17} />
                      查看原页与知识点
                    </button>
                  ) : null}
                  {knowledgeMaps[snapshot.id]?.status === "failed" ? (
                    <button
                      className="secondary-button compact-button"
                      type="button"
                      onClick={() => void analyzeSnapshot(snapshot)}
                    >
                      <MagicWand size={17} />
                      重新理解
                    </button>
                  ) : null}
                  {knowledgeMaps[snapshot.id]?.status === "needs_review" ? (
                    <button
                      className="secondary-button compact-button"
                      type="button"
                      onClick={() => void approveKnowledge(snapshot)}
                    >
                      <SealCheck size={17} />
                      批准知识图谱
                    </button>
                  ) : null}
                  {snapshot.status === "draft" &&
                  (!knowledgeMaps[snapshot.id] ||
                    knowledgeMaps[snapshot.id]?.status === "approved") &&
                  !isPendingDocumentParsing(snapshot) ? (
                    <button
                      className="secondary-button compact-button"
                      type="button"
                      onClick={() => void publish(snapshot.id)}
                    >
                      <SealCheck size={17} />
                      审核发布
                    </button>
                  ) : snapshot.status === "draft" ? (
                    <span className="status-pill amber">
                      待理解/审核 · 尚未使用
                    </span>
                  ) : snapshot.status === "published" &&
                    !hasParsedDocumentPages(snapshot) ? (
                    <span className="status-pill amber">
                      已发布 · 未解析正文
                    </span>
                  ) : (
                    <span className="status-pill">
                      <CheckCircle size={15} />
                      {snapshot.status === "published" ? "已发布" : "已替换"}
                    </span>
                  )}
                  <button
                    aria-label={`删除教材 ${snapshot.textbook_version}`}
                    className="icon-text-button danger-button"
                    type="button"
                    onClick={() => void deleteSnapshot(snapshot)}
                  >
                    <Trash size={17} />
                    删除
                  </button>
                </div>
              </article>
            ))}
          </div>
        </article>

        <article className="dashboard-panel">
          <div className="section-heading">
            <div>
              <p className="section-kicker">家长确认</p>
              <h2>任务推荐</h2>
            </div>
            <button
              className="primary-button compact-button"
              type="button"
              onClick={() => void generateRecommendations()}
              disabled={!childId}
            >
              <MagicWand size={17} />
              生成推荐
            </button>
          </div>
          <div className="recommendation-list">
            {recommendations.length === 0 ? (
              <p className="muted-copy">
                暂无推荐。发布已解析的 PDF 或产生错题后，可让 NewAPI
                生成带具体题目和页码的学习计划。
              </p>
            ) : null}
            {recommendations.map((recommendation) => (
              <article className="recommendation-row" key={recommendation.id}>
                <div className="task-details">
                  <strong>{recommendation.title}</strong>
                  <span>
                    {recommendation.scheduled_for} ·{" "}
                    {recommendation.estimated_minutes} 分钟 · 共{" "}
                    {recommendation.exercises.length} 题 ·{" "}
                    {recommendation.knowledge_point}
                  </span>
                  <span>{recommendation.reason}</span>
                </div>
                <div className="inline-actions">
                  <button
                    className="secondary-button compact-button"
                    type="button"
                    onClick={() => setSelectedRecommendation(recommendation)}
                  >
                    <BookOpenText size={17} />
                    查看计划
                  </button>
                  <span className="status-pill">
                    {recommendation.status === "pending"
                      ? "待审核"
                      : recommendation.status === "approved"
                        ? "已安排"
                        : "已忽略"}
                  </span>
                </div>
              </article>
            ))}
          </div>
        </article>
      </section>

      {previewSnapshot ? (
        <div
          aria-labelledby="curriculum-reader-title"
          aria-modal="true"
          className="document-overlay"
          role="dialog"
        >
          <section className="document-reader">
            <header className="document-reader-header">
              <div>
                <p className="section-kicker">家长审核 · 解析文档</p>
                <h2 id="curriculum-reader-title">
                  {previewSnapshot.textbook_version}
                </h2>
                <p>
                  {previewSnapshot.term} · 原页图像通过登录后的服务端接口读取，
                  不会暴露私有 PDF、MinIO 地址或对象键。
                </p>
              </div>
              <button
                aria-label="关闭解析文档"
                className="icon-button"
                type="button"
                onClick={() => setPreviewSnapshot(null)}
              >
                <XCircle size={20} />
              </button>
            </header>

            {previewLoading ? (
              <p className="reader-state">正在载入分页解析结果…</p>
            ) : previewError ? (
              <p className="reader-state error-copy">{previewError}</p>
            ) : previewPage ? (
              <div className="document-reader-layout">
                <aside className="document-reader-nav">
                  <span className="quiet-label">
                    共 {previewPages.length} 页
                  </span>
                  <label>
                    跳转页面
                    <select
                      value={previewPage.page_number}
                      onChange={(event) =>
                        setPreviewPageNumber(Number(event.target.value))
                      }
                    >
                      {previewPages.map((page) => (
                        <option key={page.page_number} value={page.page_number}>
                          第 {page.page_number} 页 · {page.title.slice(0, 24)}
                        </option>
                      ))}
                    </select>
                  </label>
                  <div className="reader-page-actions">
                    <button
                      className="secondary-button compact-button"
                      disabled={previewPageIndex <= 0}
                      type="button"
                      onClick={() =>
                        setPreviewPageNumber(
                          previewPages[previewPageIndex - 1]?.page_number ??
                            null,
                        )
                      }
                    >
                      上一页
                    </button>
                    <button
                      className="secondary-button compact-button"
                      disabled={previewPageIndex >= previewPages.length - 1}
                      type="button"
                      onClick={() =>
                        setPreviewPageNumber(
                          previewPages[previewPageIndex + 1]?.page_number ??
                            null,
                        )
                      }
                    >
                      下一页
                    </button>
                  </div>
                  <p>
                    文字层提取完整度：
                    {Math.round(previewPage.confidence * 100)}%
                  </p>
                </aside>
                <article className="document-reader-page">
                  <p className="section-kicker">
                    第 {previewPage.page_number} 页
                  </p>
                  <h3>{previewPage.title}</h3>
                  {previewPage.image_available ? (
                    <div className="curriculum-page-image">
                      <Image
                        alt={`教材第 ${previewPage.page_number} 页原页`}
                        height={1600}
                        priority
                        src={`/api/curriculum/${childId}/snapshots/${previewSnapshot.id}/pages/${previewPage.page_number}/image`}
                        unoptimized
                        width={1200}
                      />
                    </div>
                  ) : (
                    <p className="reader-state">
                      原页图像仍在生成，当前只提供辅助文字。
                    </p>
                  )}
                  <details className="reader-text-details">
                    <summary>查看辅助文字（可能缺失图片语义）</summary>
                    <div className="reader-prose">
                      {readerParagraphs(previewPage.text).map(
                        (paragraph, index) => (
                          <p key={`${previewPage.page_number}-${index}`}>
                            {paragraph}
                          </p>
                        ),
                      )}
                    </div>
                  </details>
                </article>
              </div>
            ) : (
              <p className="reader-state">
                当前文档还没有可阅读的文字页，可能仍在解析中，或属于需要 OCR
                的扫描件。
              </p>
            )}
            {previewKnowledge ? (
              <section className="knowledge-map-review">
                <div className="section-heading">
                  <div>
                    <p className="section-kicker">整本教材 AI 归纳</p>
                    <h3>知识图谱</h3>
                  </div>
                  <span className="status-pill">
                    {previewKnowledge.status === "approved"
                      ? "家长已批准"
                      : previewKnowledge.status === "needs_review"
                        ? "等待家长审核"
                        : previewKnowledge.status === "failed"
                          ? "分析失败"
                          : "分析中"}
                  </span>
                </div>
                {previewKnowledge.book_summary ? (
                  <p className="knowledge-book-summary">
                    {previewKnowledge.book_summary}
                  </p>
                ) : (
                  <p className="muted-copy">
                    AI 正在结合每页原图和文字归纳章节、知识目标及具体练习。
                  </p>
                )}
                <div className="knowledge-point-grid">
                  {previewKnowledge.knowledge_points.map((point) => (
                    <article className="knowledge-point-card" key={point.id}>
                      <div>
                        <span className="status-pill">
                          {point.chapter_title} · 第{" "}
                          {point.page_numbers.join("、")} 页
                        </span>
                        <h4>{point.title}</h4>
                        <p>{point.summary}</p>
                      </div>
                      <div>
                        <strong>孩子需要会什么</strong>
                        <ul>
                          {point.learning_objectives.map((objective) => (
                            <li key={objective}>{objective}</li>
                          ))}
                        </ul>
                      </div>
                      {point.exercises.length > 0 ? (
                        <div>
                          <strong>识别出的教材练习</strong>
                          {point.exercises.slice(0, 3).map((exercise) => (
                            <button
                              className="knowledge-exercise-link"
                              key={exercise.source_key}
                              type="button"
                              onClick={() =>
                                setPreviewPageNumber(exercise.page_number)
                              }
                            >
                              第 {exercise.page_number} 页 ·{" "}
                              {exercise.question_text}
                              {exercise.requires_visual_context
                                ? "（需结合原页图形）"
                                : ""}
                            </button>
                          ))}
                        </div>
                      ) : null}
                    </article>
                  ))}
                </div>
                {previewKnowledge.status === "needs_review" ? (
                  <div className="document-reader-footer">
                    <button
                      className="primary-button"
                      type="button"
                      onClick={() => void approveKnowledge(previewSnapshot)}
                    >
                      <SealCheck size={18} />
                      确认知识点准确并批准
                    </button>
                  </div>
                ) : null}
              </section>
            ) : null}
          </section>
        </div>
      ) : null}

      {selectedRecommendation ? (
        <div
          aria-labelledby="recommendation-reader-title"
          aria-modal="true"
          className="document-overlay"
          role="dialog"
        >
          <section className="document-reader recommendation-reader">
            <header className="document-reader-header">
              <div>
                <p className="section-kicker">家长确认 · 学习计划</p>
                <h2 id="recommendation-reader-title">
                  {selectedRecommendation.title}
                </h2>
                <p>
                  {selectedRecommendation.scheduled_for} ·{" "}
                  {selectedRecommendation.estimated_minutes} 分钟 ·{" "}
                  {selectedRecommendation.knowledge_point}
                </p>
              </div>
              <button
                aria-label="关闭学习计划"
                className="icon-button"
                type="button"
                onClick={() => setSelectedRecommendation(null)}
              >
                <XCircle size={20} />
              </button>
            </header>
            <div className="recommendation-document">
              <section>
                <p className="section-kicker">为什么推荐</p>
                <p>{selectedRecommendation.reason}</p>
              </section>
              <section>
                <p className="section-kicker">本次练习</p>
                <div className="recommendation-exercise-list">
                  {selectedRecommendation.exercises.map((exercise, index) => (
                    <article
                      className="recommendation-exercise-card"
                      key={`${selectedRecommendation.id}-${exercise.source_type}-${index}`}
                    >
                      <span className="status-pill">
                        {exercise.source_type === "mistake"
                          ? "错题复习"
                          : `${exercise.source_title ?? "教材"}${
                              exercise.source_page
                                ? ` · 第 ${exercise.source_page} 页`
                                : ""
                            }`}
                      </span>
                      <p>{exercise.question_text}</p>
                      {exercise.visual_description ? (
                        <p className="exercise-visual-context">
                          图形信息：{exercise.visual_description}
                        </p>
                      ) : null}
                      {exercise.source_type === "curriculum" &&
                      exercise.snapshot_id &&
                      exercise.source_page ? (
                        <button
                          className="secondary-button compact-button"
                          type="button"
                          onClick={() => {
                            const snapshot = snapshots.find(
                              (item) => item.id === exercise.snapshot_id,
                            );
                            if (snapshot) {
                              setSelectedRecommendation(null);
                              void openSnapshotPreview(
                                snapshot,
                                exercise.source_page ?? undefined,
                              );
                            }
                          }}
                        >
                          <BookOpenText size={16} />
                          查看教材第 {exercise.source_page} 页原图
                        </button>
                      ) : null}
                    </article>
                  ))}
                </div>
              </section>
              {selectedRecommendation.status === "pending" ? (
                <div className="document-reader-footer">
                  <button
                    className="primary-button"
                    type="button"
                    onClick={() =>
                      void decide(selectedRecommendation.id, "approve")
                    }
                  >
                    <CheckCircle size={18} />
                    批准并下发任务
                  </button>
                  <button
                    className="secondary-button danger-button"
                    type="button"
                    onClick={() =>
                      void decide(selectedRecommendation.id, "reject")
                    }
                  >
                    <XCircle size={18} />
                    忽略本条推荐
                  </button>
                </div>
              ) : (
                <span className="status-pill">
                  {selectedRecommendation.status === "approved"
                    ? "此计划已下发到孩子端"
                    : "此计划已被忽略"}
                </span>
              )}
            </div>
          </section>
        </div>
      ) : null}
    </AdminShell>
  );
}
