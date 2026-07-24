# ADR-0021：本地 PDF 教材解析与发布流水线

- 状态：`Accepted（2026-07-23；首版实现已落地）`
- 日期：`2026-07-23`
- Owner：项目 Owner + API/Worker/安全负责人
- 决策者：项目 Owner（已确认 PDF-only 范围、依赖和本地自用边界）
- 关联：`PLAN-0016`、`TODO-016`、`TODO-019`、`ADR-0020`、`FR-011`、`FR-020`
- 替代/被替代：不替代 ADR-0020；为其教材解析部分补充可实施的格式、依赖、隔离和发布决策

## Context

首版范围只接受 PDF。历史多格式记录仍保留用于导出/删除审计，但新上传的 Word、PPT、Excel 在 API 边界返回稳定错误。文本 PDF 由本地 worker 解析为页级草稿，扫描 PDF 进入 `needs_ocr`，待家长审核发布后才可被 Tutor/推荐消费。

要让教材真正用于错题解法和推荐任务，系统需要把不可信、可能受版权保护且可能恶意构造的 PDF 转换为带页码来源的草稿，再由家长审核发布。解析器选择会引入新的核心依赖、对象流/附件/危险动作攻击面、镜像体积和许可证约束，因此不能在 API 请求进程中临时拼接实现，也不能把“扩展名已接受”误称为格式已支持。

## Decision Drivers

- 首批上传与解析只稳定处理 PDF，并保留页码来源。
- 原文和草稿只属于当前 Household/Child；只有家长发布的不可变 Snapshot 能被 Tutor/任务引用。
- 解析过程必须无网络、有界、可隔离、可重试和可清理，不能让 PDF 对象流资源炸弹、危险动作/链接、嵌入附件或超大文档拖垮 API。
- 依赖许可证、维护状态、供应链风险和容器体积必须适合自托管开源项目。
- 文本 PDF、扫描 PDF、损坏/加密/危险 PDF 应有明确状态；Word、PPT、Excel 必须在 Web/API 上传边界直接拒绝，不能以“待解析”掩盖不支持。

## Considered Options

1. 把整份原始文档直接交给云模型解析。实现快，但会扩大儿童/版权材料外发、成本、供应商锁定和 Prompt 注入风险，也难以提供稳定来源锚点。
2. 继续维持多格式上传，再使用 `unstructured + LibreOffice` 或多个格式库解析。格式覆盖广，但合同、镜像、系统依赖、漏洞面和转换不确定性明显增加，不符合当前首版范围。
3. 同步把 Web/OpenAPI/API 上传合同收缩为 PDF-only，在隔离 worker 中本地解析文本 PDF；扫描 PDF 进入待 OCR，草稿经家长审核后发布；只把当前题目所需的最小已发布片段交给 Tutor Provider。

## Decision

选择选项 3；依赖、资源上限和运行时边界已接受并进入实现。

1. v1 上传 allowlist 只有 `.pdf` / `application/pdf`，并校验 `%PDF-` 文件头和实际可解析结构；允许同一批次上传多个 PDF。DOC/DOCX、PPT/PPTX、XLS/XLSX 返回稳定 `unsupported_material_format`，Web 文件选择器同步限制，不能只依赖前端。
2. v1 使用 `pdfplumber==0.11.7`（MIT）及其 `pdfminer-six==20250506`（MIT）传递依赖，已写入 `pyproject.toml`/`uv.lock`；不使用 AGPL/商业双许可证的 PyMuPDF，也不引入 `python-docx`、`python-pptx`、`unstructured` 或 LibreOffice。
3. 现有非 PDF 对象和记录只为兼容、导出/删除审计保留，标记 `unsupported_for_learning_content`，不得进入解析、发布、Tutor 或推荐；不自动转换、不静默删除。扫描 PDF 经文本密度/页面信号判定为 `needs_ocr`，不得冒充解析成功。后续文档 OCR 与拍题 PrivacySanitizer OCR 是不同职责和评测集。
4. 材料解析状态机为 `uploaded → queued → parsing → needs_review | needs_ocr | failed/quarantined`；`published` 不是解析 Job 状态，而是家长审核 `needs_review` 草稿并发布不可变 CurriculumSnapshot 的独立业务事实。
5. 独立 worker 产生 `MaterialParseJob`、`CurriculumChunk`、`KnowledgePointEvidence` 和 `ExerciseCandidate`。每个 chunk 记录 Household/Child/Material/Snapshot 范围、PDF 页码锚点、内容哈希、解析器/Schema 版本和置信度。
6. worker 通过 Compose 的 `parser-backend` internal network 只访问 PostgreSQL/MinIO，并限制 PDF 50 MB、400 页和单页 40,000 字符；拒绝/隔离加密文件、危险动作/嵌入附件、异常文件头和超限文件。API 进程不直接同步解析整份 PDF。
7. Tutor grounding 只从当前孩子已发布 Snapshot 检索最小片段，保存来源引用并把片段标记为不可信数据；不得发送整本教材、对象 URL/键或执行材料中的指令。
8. TaskRecommendation 只引用已发布的章节、知识点和家长审核的 ExerciseCandidate，并与到期错题/有证据薄弱点组合。AI 不得从未发布正文静默新编并下发题目，家长审批边界不变。
9. v1 检索先使用 PostgreSQL 全文检索、结构化元数据和强制 Household/Child/Snapshot 过滤；只有固定 eval 证明语义检索提升质量且不扩大越权/成本后，才启用 pgvector 混合检索。

## Consequences

### Positive

- 首批格式和失败状态可预测，家长不会把“上传成功”误解为“教材已用于讲解”。
- 来源锚点、不可变发布和最小片段使错题讲解与推荐可追溯、可撤销新消费且更容易做跨家庭授权测试。
- 格式专用解析器比通用重型栈更小、更容易锁定许可证、资源上限和供应链范围。
- 解析、发布、检索和 Tutor 解耦，解析失败不会破坏既有错题、复习或手工教材范围。

### Negative / Trade-offs

- v1 不支持 Word、PPT、Excel 上传，家长必须先在本地转换为 PDF；扫描 PDF 仍需等待文档 OCR 或改用文本 PDF。
- PDF-only 显著收窄兼容范围，但减少依赖、合同分支、来源锚点差异和解析攻击面。
- 增加 worker、状态机、草稿审核、删除/重试和来源数据会扩大迁移、测试与运维成本。
- 精准知识点/练习候选仍需规则或模型辅助和家长审核，不能仅靠文本提取自动成为学习事实。

### Risks and Mitigations

- 风险：恶意/超大 PDF、对象流资源炸弹或解析器漏洞；缓解：隔离无网络 worker、文件头/结构/对象展开量/资源限制、危险动作/附件拒绝、异常隔离、锁定版本、SBOM 和安全回归。
- 风险：版权材料被过量外发；缓解：家庭私有存储、最小发布片段、单 Provider、禁止整本/对象链接外发和审计片段指纹。
- 风险：Prompt 注入污染讲解；缓解：解析内容只进入结构化数据字段，固定系统 Prompt/Schema，不执行文档指令，低置信或冲突时阻断。
- 风险：来源定位错误；缓解：保留原始 PDF 页码锚点和解析版本，家长发布前预览/校正，Tutor 端展示可追溯引用。
- 风险：解析重试产生重复或不同事实；缓解：Material SHA-256 + parser/schema version 幂等，草稿可重算，已发布 Snapshot 不被覆盖。

## Compatibility and Migration

- 兼容性：这是预发布上传合同收缩。保留现有 LearningMaterial 和私有对象；只有既有 PDF `uploaded` 记录可迁移为 `queued` 候选，非 PDF 记录保持不支持且不能自动变成已发布内容。旧客户端上传非 PDF 会收到稳定错误，Web/API 必须成对部署。
- 迁移步骤：批准依赖/限制 → 收缩 OpenAPI/API/Web allowlist 并增加稳定错误码 → 新增迁移和解析合同 → 部署关闭开关的 worker → 用 synthetic PDF 回填 → 上线家长预览/发布 → 接入 grounding/推荐 → 逐项启用。
- 回滚：关闭解析、grounding 和推荐消费开关，保留对象、授权/哈希、Job 事实和已发布 Snapshot；删除可重算草稿/索引时必须遵循引用和审计策略，禁止破坏性数据库 downgrade。

## Validation

### Implementation evidence (2026-07-23)

- API/Web/OpenAPI 已收缩为 PDF-only；多 PDF 批次上传、文件头校验和稳定 `unsupported_material_format` 已有回归。
- 迁移 `0021_learning_closeout_parse`/`0022_tutor_curriculum_sources`/`0023_tutor_hint_progression` 已建立 ReviewAttempt、解析 Job、页级 CurriculumChunk、Tutor 来源和提示递进字段。
- `material-parse-worker` 已接入 Compose；文本 PDF 解析成功进入 `needs_review`，扫描 PDF 进入 `needs_ocr`，解析失败进入稳定失败/隔离状态。
- 本机 PostgreSQL/MinIO 全量 API 测试、Ruff、Mypy 和 PDF parser synthetic 测试通过；真实 Ubuntu 部署和设备相机回归仍是发布前验证项。

- 格式矩阵：文本/扫描/加密/损坏/超大/带表格 PDF、扩展名与 MIME/文件头伪造，以及 DOC/DOCX/PPT/PPTX/XLS/XLSX 在 Web/API 的拒绝。
- 安全矩阵：PDF 对象/流异常展开、解析超时/内存、危险动作/链接、嵌入附件、解析器网络阻断、Prompt 注入、跨 Household/Child、日志/导出/删除和失败对象清理。
- 来源矩阵：PDF 页码、重复文件/版本更新、家长校正、发布不可变和撤销后停止新检索。
- 消费矩阵：同一道 synthetic 错题在匹配/错版/未发布/低置信教材下的 grounding；推荐任务的来源解释、去重、每日上限、审批/拒绝和跨孩子隔离。
- 运维矩阵：迁移前滚、worker 并发/重试/死信、PostgreSQL/MinIO 一致备份恢复、功能开关和应用回滚。
