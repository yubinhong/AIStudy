import { describe, expect, it } from "vitest";

import {
  canApproveCurriculumAnalysis,
  canRetryCurriculumAnalysis,
  curriculumPublishMessage,
  curriculumUploadMessage,
} from "./curriculum-actions";

describe("curriculum actions", () => {
  it("keeps Chinese upload and publish messages tied to its actual flow", () => {
    expect(curriculumUploadMessage("chinese", 2)).toContain("语文教材分析 v2");
    expect(curriculumUploadMessage("chinese", 2)).toContain(
      "自动提取古诗抽查内容",
    );
    expect(curriculumPublishMessage("chinese")).toContain("自动开放古诗抽查");
  });

  it("preserves the math copy", () => {
    expect(curriculumUploadMessage("math", 1)).toContain("归纳整本教材知识点");
    expect(curriculumPublishMessage("math")).toContain("错题讲解");
  });

  it("allows retry and approval for either subject", () => {
    expect(canRetryCurriculumAnalysis("failed")).toBe(true);
    expect(canApproveCurriculumAnalysis("needs_review")).toBe(true);
    expect(canRetryCurriculumAnalysis("approved")).toBe(false);
    expect(canApproveCurriculumAnalysis("failed")).toBe(false);
  });
});
