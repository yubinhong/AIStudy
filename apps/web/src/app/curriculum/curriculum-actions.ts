export type CurriculumSubject = "math" | "chinese";

export function curriculumUploadMessage(
  subject: CurriculumSubject,
  fileCount: number,
) {
  return subject === "chinese"
    ? `已上传 ${fileCount} 个语文文件。服务端将使用语文教材分析 v2，并在家长批准后自动提取古诗抽查内容。`
    : `已上传 ${fileCount} 个文件。服务端将保留原页图像并归纳整本教材知识点；家长审核前不会用于讲解。`;
}

export function curriculumPublishMessage(subject: CurriculumSubject) {
  return subject === "chinese"
    ? "语文教材已发布；已批准知识点可用于教材范围内学习，并自动开放古诗抽查"
    : "教材已发布；已批准知识点现在可用于教材范围内的错题讲解";
}

export function canRetryCurriculumAnalysis(status: string | undefined) {
  return status === "failed";
}

export function canApproveCurriculumAnalysis(status: string | undefined) {
  return status === "needs_review";
}
