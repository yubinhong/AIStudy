"use client";

import {
  BookOpenText,
  CheckCircle,
  FileArrowUp,
  Files,
  MagicWand,
  SealCheck,
  Trash,
  UploadSimple,
  XCircle,
} from "@phosphor-icons/react";
import Image from "next/image";
import { useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useEffect, useRef, useState } from "react";

import { AdminShell } from "@/app/components/admin-shell";
import { resolveSelectedChildId } from "@/lib/child-selection";
import { csrfHeaders } from "../../lib/csrf";
import { idempotencyKey } from "../../lib/idempotency-key";

type Child = {
  id: string;
  display_name: string;
  grade: number;
  subjects: Array<"math" | "chinese">;
};
type Snapshot = {
  id: string;
  subject: "math" | "chinese";
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

function isPreparingCurriculumAnalysis(
  snapshot: Snapshot,
  knowledgeMap: KnowledgeMap | undefined,
) {
  return (
    !knowledgeMap &&
    snapshot.sections.some((section) => section.chapter === "待审核知识图谱")
  );
}

function hasApprovedCurriculumAnalysis(knowledgeMap: KnowledgeMap | undefined) {
  return (
    knowledgeMap?.status === "approved" && knowledgeMap.analyzed_page_count > 0
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

function CurriculumPageContent() {
  const searchParams = useSearchParams();
  const requestedChild = searchParams.get("child");
  const [children, setChildren] = useState<Child[]>([]);
  const childId = resolveSelectedChildId(children, requestedChild);
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [publicReusable, setPublicReusable] = useState(false);
  const [subject, setSubject] = useState<"math" | "chinese">("math");
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
  const loadVersion = useRef(0);

  async function loadChildren() {
    const response = await fetch("/api/children/management", {
      cache: "no-store",
    });
    if (!response.ok) return;
    const aggregates = (await response.json()) as Array<{ child: Child }>;
    const values = aggregates.map((item) => item.child);
    setChildren(values);
  }

  async function loadData(selected: string) {
    if (!selected) return;
    const version = ++loadVersion.current;
    const curriculum = await fetch(`/api/curriculum/${selected}`, {
      cache: "no-store",
    });
    if (version !== loadVersion.current) return;
    if (curriculum.ok) {
      const values = (await curriculum.json()) as Snapshot[];
      if (version !== loadVersion.current) return;
      setSnapshots(values);
      const entries = await Promise.all(
        values
          .filter((snapshot) => !isPendingDocumentParsing(snapshot))
          .map(async (snapshot) => {
            const response = await fetch(
              `/api/curriculum/${selected}/snapshots/${snapshot.id}/analysis`,
              { cache: "no-store" },
            );
            return [
              snapshot.id,
              response.ok
                ? ((await response.json()) as KnowledgeMap)
                : undefined,
            ] as const;
          }),
      );
      if (version !== loadVersion.current) return;
      setKnowledgeMaps(Object.fromEntries(entries));
    }
  }

  useEffect(() => {
    const timer = window.setTimeout(() => void loadChildren(), 0);
    return () => window.clearTimeout(timer);
  }, []);

  useEffect(() => {
    loadVersion.current += 1;
    const timer = window.setTimeout(() => {
      setSnapshots([]);
      setKnowledgeMaps({});
      setPreviewSnapshot(null);
      setPreviewPages([]);
      if (childId) void loadData(childId);
    }, 0);
    return () => window.clearTimeout(timer);
    // Every current-child transition discards the previous child's transient view.
  }, [childId]);

  useEffect(() => {
    const hasActiveAnalysis = Object.values(knowledgeMaps).some(
      (map) => map?.status === "queued" || map?.status === "analyzing",
    );
    const hasPendingDocument = snapshots.some(isPendingDocumentParsing);
    if (!childId || (!hasActiveAnalysis && !hasPendingDocument)) return;
    const timer = window.setInterval(() => void loadData(childId), 8_000);
    return () => window.clearInterval(timer);
    // Poll only while a server-side curriculum job is active.
  }, [childId, knowledgeMaps, snapshots]);

  async function uploadDocuments(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!childId || selectedFiles.length === 0 || uploading) return;
    const child = children.find((item) => item.id === childId);
    const uploadSubject =
      subject === "chinese" && child?.subjects.includes("chinese")
        ? "chinese"
        : "math";
    const form = new FormData();
    form.append("grade", String(child?.grade ?? 3));
    form.append("subject", uploadSubject);
    form.append(
      "authorization_statement",
      "家庭自用教材，已确认来源和使用授权，并确认文件不含儿童姓名、个人批注或其他个人信息",
    );
    form.append("is_public_reusable", String(publicReusable));
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
          ? uploadSubject === "math"
            ? `已上传 ${selectedFiles.length} 个文件。服务端将保留原页图像并归纳整本教材知识点；家长审核前不会用于讲解。`
            : `已上传 ${selectedFiles.length} 个语文文件。当前只建立私有草稿；语文教材分析 Schema 完成前不会进入 AI 理解或孩子练习。`
          : response.status === 413 || failure?.detail?.includes("too large")
            ? "上传失败：单个 PDF 上限为 50 MiB（52.4 MB），请重新选择不超过该大小的文件。"
            : "文件上传失败，请检查 PDF 格式、大小和登录状态",
      );
      if (response.ok) {
        setSelectedFiles([]);
        await loadData(childId);
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
        ? "教材已发布；已批准知识点现在可用于教材范围内的错题讲解"
        : "发布失败：文档正文尚未解析，或服务暂时不可用",
    );
    if (response.ok) await loadData(childId);
  }

  async function deleteSnapshot(snapshot: Snapshot) {
    if (
      !childId ||
      !window.confirm(
        `删除“${snapshot.textbook_version}”及其私有 PDF 和解析结果？此操作不可恢复。`,
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
    if (response.ok) await loadData(childId);
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
    await loadData(childId);
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
        ? "知识图谱已批准；现在可以发布教材，并据此约束错题讲解范围。"
        : "知识图谱尚未分析完成，暂时不能批准。",
    );
    await loadData(childId);
  }

  const currentChild = children.find((child) => child.id === childId);
  const effectiveSubject =
    subject === "chinese" && currentChild?.subjects.includes("chinese")
      ? "chinese"
      : "math";
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
          <p className="page-eyebrow">教材</p>
          <h1>教材范围管理</h1>
          <p>
            PDF
            解析并发布后，错题讲解会优先引用已批准的教材知识点，避免超出当前教材范围。
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
        <article className="dashboard-panel upload-panel full-grid-panel">
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
            <label>
              教材学科
              <select
                value={effectiveSubject}
                onChange={(event) =>
                  setSubject(event.target.value as "math" | "chinese")
                }
                disabled={uploading}
              >
                <option value="math">数学</option>
                {currentChild?.subjects.includes("chinese") ? (
                  <option value="chinese">语文</option>
                ) : null}
              </select>
            </label>
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
            <label className="check-row">
              <input
                type="checkbox"
                checked={publicReusable}
                onChange={(event) => setPublicReusable(event.target.checked)}
                disabled={uploading}
              />
              这是不含个人批注的公开教材，允许按完全一致的文件内容在其他家庭复用原页和已审核知识图谱
            </label>
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
      </section>

      <section className="curriculum-grid lower-grid">
        <article className="dashboard-panel full-grid-panel">
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
                    {snapshot.subject === "chinese" ? "语文" : "数学"} ·{" "}
                    {snapshot.term} ·{" "}
                    {knowledgeMaps[snapshot.id]
                      ? knowledgeMaps[snapshot.id]?.status === "approved"
                        ? `知识图谱已批准 · ${knowledgeMaps[snapshot.id]?.knowledge_points.length ?? 0} 个知识点`
                        : knowledgeMaps[snapshot.id]?.status === "needs_review"
                          ? `AI 已理解 ${knowledgeMaps[snapshot.id]?.analyzed_page_count ?? 0} 页 · 待家长审核`
                          : knowledgeMaps[snapshot.id]?.status === "failed"
                            ? "AI 教材理解失败 · 可安全重试"
                            : `AI 正在理解教材 · 全文处理中（共 ${knowledgeMaps[snapshot.id]?.page_count ?? 0} 页）`
                      : isPendingDocumentParsing(snapshot)
                        ? "正在等待 PDF 本地解析"
                        : isPreparingCurriculumAnalysis(
                              snapshot,
                              knowledgeMaps[snapshot.id],
                            )
                          ? "正在准备 AI 教材理解"
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
                  {snapshot.subject === "math" &&
                  knowledgeMaps[snapshot.id]?.status === "failed" ? (
                    <button
                      className="secondary-button compact-button"
                      type="button"
                      onClick={() => void analyzeSnapshot(snapshot)}
                    >
                      <MagicWand size={17} />
                      重新理解
                    </button>
                  ) : null}
                  {snapshot.subject === "math" &&
                  knowledgeMaps[snapshot.id]?.status === "needs_review" ? (
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
                  !isPendingDocumentParsing(snapshot) &&
                  !isPreparingCurriculumAnalysis(
                    snapshot,
                    knowledgeMaps[snapshot.id],
                  ) ? (
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
                      {knowledgeMaps[snapshot.id]?.status === "failed"
                        ? "AI 理解失败 · 可安全重试"
                        : isPreparingCurriculumAnalysis(
                              snapshot,
                              knowledgeMaps[snapshot.id],
                            )
                          ? "AI 理解准备中 · 尚未使用"
                          : "待理解/审核 · 尚未使用"}
                    </span>
                  ) : snapshot.status === "published" &&
                    !hasApprovedCurriculumAnalysis(
                      knowledgeMaps[snapshot.id],
                    ) ? (
                    <span className="status-pill amber">
                      已发布 · 未解析正文
                    </span>
                  ) : (
                    <span className="status-pill">
                      <CheckCircle size={15} />
                      {snapshot.status === "published"
                        ? "已发布 · 知识图谱已启用"
                        : "未发布"}
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
    </AdminShell>
  );
}

export default function CurriculumPage() {
  return (
    <Suspense fallback={null}>
      <CurriculumPageContent />
    </Suspense>
  );
}
