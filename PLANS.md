# PLANS.md — PLAN-0001 项目上下文建档

> 当前计划只覆盖 `TASK-0001` 的文档初始化，不创建业务代码或部署资源。

## 计划元数据

- 计划 ID：`PLAN-0001`
- 关联任务：`TASK-0001`
- 状态：`COMPLETE`
- Owner：Codex（执行）；项目 Owner `TBD`
- 基线：`master`，无 commit，全部文件 untracked
- 创建/更新：`2026-07-12 14:36 CST`

## 1. 目标结果

完成后，新会话能在 3 分钟内通过 `AI_CONTEXT.md` 理解家庭 AI 学习助手的当前零实现状态、P0/P1/P2 目标、唯一事实源、硬约束、开放决策、风险和推荐第一项任务。

## 2. 上下文与约束

- 当前行为：只有设计稿和通用上下文模板；无代码、依赖、CI、测试或部署。
- 目标行为：所有根目录上下文主文档具体、交叉一致，未知项有 Owner/截止条件，不虚构实现。
- 不变量：孩子端低干扰、AI 不直接代答、家庭强隔离、数据最小化、离线不丢、契约/模型可替换、内容版权边界。
- 禁止事项：不修改 DOCX/Prompt/ADR 模板；不写业务代码；不安装依赖；不部署、提交或推送；不自行批准许可证/法域/Provider/SLO。
- 关键依赖：`家庭AI学习助手_架构设计_v1.0.docx`、`AGENTS.md`、`PROJECT.md`、`prompts/00-project-bootstrap.md`。

## 3. 相关文件与入口

| 路径 | 作用 | 本计划输出 |
| --- | --- | --- |
| `AI_CONTEXT.md` | 3 分钟项目入口 | 当前事实、导航、约束、下一步 |
| `PRD.md` | P1 产品事实源 | 用户、流程、需求、NFR、验收、开放项 |
| `ARCHITECTURE.md` | 目标系统事实源 | 组件、数据流、接口、数据、NFR、边界 |
| `TESTING.md` | 质量事实源 | 当前可运行检查和 P0/P1 目标命令/门槛 |
| `SECURITY.md` | 安全事实源 | 儿童数据、身份、AI、供应链和生产阻塞 |
| `RUNBOOK.md` | 运维事实源 | NOT_DEPLOYED 状态和生产前契约 |
| `TASK.md`/`TODO.md` | 当前执行与队列 | 关闭建档任务，推荐首个 P0 任务 |
| `DECISIONS.md` | ADR 索引 | 明确无已接受 ADR，列优先候选 |
| `CHANGELOG.md` | 已发布变化 | 明确暂无产品发布 |

## 4. 分阶段计划

### Milestone 1 — 证据扫描

结果：确认仓库、Git、DOCX、依赖/入口/测试/CI/部署现状。

- [x] 按 AGENTS 顺序读取所有主文档和 bootstrap Prompt。
- [x] 使用 `rg/find/git` 验证仓库结构和 Git 状态。
- [x] 提取 DOCX 段落/表格并渲染、检查全部 3 页。
- 验证：31 段落、6 表格、3 页；Git `master` 无提交；无代码/清单/CI/部署。

### Milestone 2 — 主文档项目化

结果：产品、架构、质量、安全和运维事实源可审查。

- [x] 更新 `PROJECT.md` 的 Git 现状和文档状态。
- [x] 完成 `PRD.md`、`ARCHITECTURE.md`、`TESTING.md`、`SECURITY.md`、`RUNBOOK.md`。
- [x] 目标架构全部标记为尚未实现，开放阈值保留 `TBD`。
- 验证：逐文档核对设计稿和唯一事实源职责。

### Milestone 3 — 状态与交接

结果：当前任务、计划、决策、队列和变更状态一致。

- [x] 刷新 `AI_CONTEXT.md`、`TASK.md`、`TODO.md`、`DECISIONS.md`、`CHANGELOG.md`。
- [x] 推荐 `TODO-001` 为首个 P0 任务并限制范围。
- [x] 运行占位符、表格、引用、敏感信息和工作区检查。
- [x] 填写 Closeout，将 TASK/PLAN/AI_CONTEXT 状态改为完成。

## 5. Progress

- `2026-07-12 14:36 CST` — `[done]` 完成仓库与 DOCX 扫描；发现 Git 已初始化但无提交，所有文件未跟踪。
- `2026-07-12` — `[done]` 完成 PRD、架构、测试、安全、Runbook 项目化。
- `2026-07-12` — `[done]` 刷新状态文档；13 份上下文、32 个表格结构检查 0 错误，引用和敏感信息检查通过。

## 6. Surprises & Discoveries

- `2026-07-12` — 发现：相较上一轮，目录现已是 Git 仓库，但 `master` 无 commit；证据：`git status --short` 和 `git log`；影响：更新 `PROJECT.md`，同时强调 Git 无法恢复未跟踪文件。
- `2026-07-12` — 发现：设计稿在当前 LibreOffice 环境渲染中文缺字，但 OOXML 文本/表格完整；证据：DOCX 提取与 3 页 PNG；影响：产品/架构事实可读取，视觉发布需 `TODO-006`。
- `2026-07-12` — 发现：无任何业务代码、依赖、配置、迁移、测试、CI 或部署；证据：全文件扫描；影响：所有工程命令只能作为 P0 验收目标，不能报告通过。

## 7. Decision Log

- `2026-07-12` — 决定：不创建业务脚手架；原因：bootstrap Prompt 明确只建档；替代方案：同时初始化代码会扩大范围；ADR：否。
- `2026-07-12` — 决定：把 v1.0 设计写成 Draft/目标架构，不标为已实现或已接受 ADR；原因：无代码、无具名批准/权衡；ADR：后续需要，见 `DECISIONS.md`。
- `2026-07-12` — 决定：未知性能、合规、保留、Provider 和运维数值保留带 Owner/截止条件的 `TBD`；原因：缺少测量和授权；ADR：部分需要。

## 8. 验证与验收

```bash
rg -n '\{\{|\}\}' AGENTS.md AI_CONTEXT.md ARCHITECTURE.md CHANGELOG.md DECISIONS.md PLANS.md PRD.md PROJECT.md RUNBOOK.md SECURITY.md TASK.md TESTING.md TODO.md
git status --short
git diff --check
```

- [x] 非模板上下文无双花括号模板占位符，Markdown 表格列数和引用正确。
- [x] 常见密钥/凭据模式无命中，工作区无意外生成物。
- [x] `TASK.md`、本计划和 `AI_CONTEXT.md` 完成状态一致。
- [x] 最终汇报列出冲突、未知、风险、建议 ADR/TODO 和首个任务。

## 9. 回滚与恢复

- 可逆步骤：所有变更仅为 Markdown，可按文件回退。
- 不可逆步骤：无；未提交、未部署、未改 DOCX。
- 回滚流程：由于无基线 commit，只能使用编辑器本地历史或会话前内容逐文件恢复；不要用 `git clean` 删除未跟踪文件。
- 数据恢复：不适用；仓库没有业务数据。

## 10. Closeout

- 实际结果：所有根目录上下文主文档已项目化，目标/现状/开放决策分离；`AI_CONTEXT.md` 可作为下一会话入口，`TODO-001` 可转为首个 P0 任务。
- 与原计划的差异：发现 Git 已初始化而非完全无仓库；其余按 bootstrap 范围执行。
- 未解决事项：Owner、远程/许可证、版本/工具链、法域/保留、身份/Provider、SLO/RPO/RTO 和生产平台。
- 经验：在零代码阶段，最重要的是区分已验证现状、目标设计和待批准决策；工程命令不能凭技术栈推断为已可用。

---

# PLANS.md — PLAN-0002 P0 仓库骨架与质量门槛

## 计划元数据

- 计划 ID：`PLAN-0002`
- 关联任务：`TASK-0002`
- 状态：`COMPLETE`
- Owner：Codex（执行）；项目/技术 Owner `TBD`
- 创建/更新：`2026-07-12`

## 目标与边界

建立 `TODO-001` 所需的 contracts、API、Web、Flutter、evals、Compose 和 CI 最小边界，生成唯一锁文件并运行可用的质量命令。只建立健康端点和空壳消费者，不进入家庭业务、身份、迁移、离线同步、AI Provider 或真实数据。

## 阶段

- [x] 1. 读取上下文和设计基线，确认 `TODO-001` 是用户“开始开发”对应的最小首项。
- [x] 2. 写入目标目录、入口、合同、Compose、CI、忽略规则和脱敏环境样例。
- [x] 3. 使用批准/可用的 uv、pnpm、Flutter 工具链生成三类锁文件并修正解析版本。
- [x] 4. 运行 API/Web/Flutter/Compose 验证，补齐 `TESTING.md` 的实际状态；原生平台构建阻塞原因已记录。
- [x] 5. 工作区和安全审查，更新 `TASK.md`、`AI_CONTEXT.md`、`TODO.md`、ADR 与变更记录。

## 关键假设与阻塞

- 版本基线暂记录在 `docs/adr/0007-toolchain-and-scaffold-baseline.md`，状态为 Proposed，不等同于 Owner 批准。
- API/Web/Flutter 依赖已解析；Flutter 原生构建仍依赖本机 Android SDK、完整 Xcode 和 CocoaPods。
- Docker CLI 可用，但 Compose 启动会创建本地服务；在确认配置无外部连接且完成静态检查前不自动启动持久化服务。

## 回滚

本计划只产生未提交的本地文件。回滚时逐文件恢复本轮改动，不使用 `git clean`、强制 checkout 或删除用户未知文件。

## Closeout

- `TASK-0002` 和 `TODO-001` 已完成；P0 代码、锁文件、验证入口和文档状态一致。
- 原生平台构建保留为环境前置项，不扩大任务范围安装 Android Studio、Xcode 或 CocoaPods。

---

# PLANS.md — PLAN-0003 家庭/孩子/设备首个纵向切片

## 计划元数据

- 计划 ID：`PLAN-0003`
- 关联任务：`TASK-0003`
- 状态：`COMPLETE`
- Owner：Codex（执行）；产品/技术 Owner `TBD`
- 创建/更新：`2026-07-12`

## 阶段

- [x] 1. 读取 PRD/架构/安全边界，确认只做合成数据和 local/CI demo 主体。
- [x] 2. 建立 OpenAPI children/devices 增量和 Proposed 契约 ADR。
- [x] 3. 建立 API domain/repository/auth adapter/routes，并覆盖家庭隔离、角色和幂等。
- [x] 4. 补充 Web/Flutter 的契约入口，不复制手工领域模型。
- [x] 5. 运行质量门槛、更新文档并完成回滚/残余风险记录。

## 不变量

- Household 是每个资源的授权边界；跨 Household 访问返回 404。
- Demo principal 仅是测试适配器，不能被描述为真实认证。
- 内存仓储仅用于合成 vertical slice，不替代 PostgreSQL 事实源。
- 所有写接口带 `Idempotency-Key`，重复请求不产生重复副作用。

## Closeout

- `TASK-0003` 和 `TODO-003` 已完成；API、契约、Web/Flutter 合成消费入口和验证记录已同步。
- 真实认证、PostgreSQL 持久化和 SDK 生成器继续由后续 ADR/任务决定。

---

# PLANS.md — PLAN-0004 核心 ADR 起草与审批准备

## 计划元数据

- 计划 ID：`PLAN-0004`
- 关联任务：`TASK-0004` / `TODO-002`
- 状态：`COMPLETE`
- Owner：Codex（起草）；项目/技术/安全/产品/法务/运维 Owner `TBD`（审批）
- 创建/更新：`2026-07-12`

## 目标与边界

为八项核心决策建立可审批 ADR，并同步主文档。ADR 只起草为 `Proposed`；本计划不指定具名 Owner、不批准真实数据/Provider/部署，也不实现后续业务任务。

## 阶段

- [x] 1. 复读项目、架构、产品、安全、测试、Runbook、决策和当前任务，确认 TODO-002 的依赖与审批边界。
- [x] 2. 使用 `/usr/local/flutter/bin/flutter` 复核迁移后的 SDK；记录 iOS/Android 原生构建事实。
- [x] 3. 建立/补齐 ADR-0001 至 ADR-0008，保证模板字段、选项、权衡、迁移与验证完整。
- [x] 4. 同步 DECISIONS、TASK、TODO、AI_CONTEXT、架构/安全/运维/测试事实，运行文档与工作区验证。

## 审批清单

| ADR | 需要的具名审批 |
| --- | --- |
| ADR-0001/0002/0003/0007 | 技术负责人；需要时项目 Owner |
| ADR-0004/0005 | 产品、技术与安全 Owner |
| ADR-0006 | 项目、产品与安全/法务 Owner |
| ADR-0008 | 项目、技术、运维与安全 Owner |

## 回滚

变更仅为 Markdown；逐文件恢复本轮内容即可。不得通过 Git 清理未跟踪文件，也不得把 `Proposed` 自动改为 `Accepted`。

## 当前结果

- 项目 Owner（用户）已于 `2026-07-13` 批准 ADR-0001～0008；所有 ADR 改为 `Accepted`，但其中定义的真实数据、Provider、法域和 staging 前置条件未被解除。
- Flutter 3.44.6 已通过交互式 PATH 验证；Android/iOS 原生构建均已验证，详细结果见 `TESTING.md`。

---

# PLANS.md — PLAN-0005 Task/Session/Attempt 与离线同步基础

## 计划元数据

- 计划 ID：`PLAN-0005`
- 关联任务：`TASK-0005` / `TODO-007`
- 状态：`COMPLETE`
- Owner：Codex（执行）；项目 Owner（用户，ADR 已批准）
- 创建/更新：`2026-07-13`

## 目标与边界

实现数学任务、StudySession、Attempt 和版本化离线同步的第一条安全数据流。先完成契约、领域规则、API 和 Flutter 待同步队列边界；随后在同一任务中接入 PostgreSQL 迁移/持久仓储和集成测试。禁止以进程内状态作为完成声明，禁止接入真实数据、Capture、Tutor 或生产认证。

## 阶段

- [x] 1. 复核 PRD、架构、安全、已接受 ADR、现有 API/合同和工具链，建立活动任务。
- [x] 2. 在 `packages/contracts` 定义 Task/Session/Attempt/SyncBatch 的向后兼容合同与 Schema 版本。
- [x] 3. 在 API 的 Plan/Task/Session 模块实现授权、状态机、追加 Attempt、事件幂等与冲突结果，并写正反向测试。
- [x] 4. 建立 Flutter 待同步队列边界和最小测试；公共模型仍以合同生成策略为目标，避免复制完整领域语义。
- [x] 5. ADR-0009 已 Accepted；Docker Desktop/local PostgreSQL、依赖锁定、首个 migration 与 downgrade/upgrade 演练已完成；PostgreSQL 仓储、连接池重连、并发版本冲突与回滚/前滚验证通过。
- [x] 6. 审查差异和 synthetic 数据边界，更新测试/架构/任务/上下文并填写完成记录。

## 不变量

- Household 授权优先于资源披露；跨 Household 统一 404。
- Attempt/AuditEvent 追加写；客户端事件、时间和版本均不可信。
- 同键同载荷重放同一结果，同键异载荷冲突；任务状态不用最后写入覆盖。
- local/CI 仅使用 synthetic fixtures；Docker 持久卷只有在检查本地配置后才启动。

## 回滚

新增合同只做兼容性增量。迁移阶段先扩展、再迁移、最后收缩；优先前向修复，绝不通过删除 Attempt、AuditEvent 或客户端队列来恢复。

## Closeout

- `TASK-0005` / `TODO-007` 已完成：`0.3.0` Learning 合同、Household/角色边界、追加 Attempt/Audit、幂等同步队列、Alembic schema 和可选 PostgreSQL 仓储均已交付。
- 验证包含 11 项 API 单元测试、4 项本地 PostgreSQL 集成测试、迁移 downgrade/upgrade、OpenAPI 结构检查和 Flutter 4 项测试；只使用 synthetic 数据。
- 未包含真实认证、Flutter SQLite 持久化、真实设备离线或 staging/production 恢复演练；后续必须以新任务处理。

---

# PLANS.md — PLAN-0006 Capture 与人工校正安全基础

## 计划元数据

- 计划 ID：`PLAN-0006`
- 关联任务：`TASK-0006` / `TODO-008`
- 状态：`IN_PROGRESS`
- Owner：Codex（执行）；项目 Owner（用户，明确授权 TODO-008）
- 创建/更新：`2026-07-13`

## 目标与边界

建立 Capture 的服务端安全数据流：受限媒体声明 → 必须人工校正 → 追加校正事件；已按 ADR-0010～0012 完成本地 MinIO 与本地 PaddleOCR 的 synthetic 安全基础。`2026-07-15` 起目标由 ADR-0015 调整为“本地 PrivacySanitizer → 用户确认脱敏副本 → 单一获批云视觉解析 → 题目人工确认”；现有本地完整 OCR 保留为迁移事实/关闭的回滚能力。真实儿童图片、生产保留/备份和具体云 Provider 仍不在范围内。

## 阶段

- [x] 1. 复核 PRD、架构、安全、测试、已接受 ADR、工作区和现有 Learning 代码，记录文档与代码基线冲突。
- [x] 2. 在 `packages/contracts` 增加向后兼容 Capture/Correction `0.4.0` 合同和结构检查。
- [x] 3. 在 API 建立 Capture 领域模型、child-only 授权路由、内存参考仓储与 PostgreSQL 事务仓储，禁止原始媒体/文本进入审计。
- [x] 4. 新增版本化迁移与 local PostgreSQL 集成测试，覆盖家庭隔离、幂等、校正追加和 downgrade/upgrade；真实多请求并发仍待下一里程碑。
- [x] 5. 已锁定并安装 `boto3==1.43.46`、Pillow `12.3.0`、PaddleOCR `3.7.0`、PaddlePaddle CPU `3.3.1` 与模型清单；私有 MinIO 预签名 Adapter、`0.5.0` 上传签发/服务端确认端点、`0003`～`0006` 对象键/生命周期/OCR Job Ledger 迁移、过期清理器、按 Household/Child 的 Capture 对象级联删除编排、local/CI 家长删除顺序与幂等入口、家长保存/立即删除图片、synthetic PostgreSQL/MinIO 测试、预置模型目录的 OCR Adapter、对象有界读取、图片容器头部校验、完整像素解码/无 EXIF 规范化重编码、PaddleOCR 文本结果纯解析、临时文件执行边界、`0005` OCR 候选结果事务持久化、幂等 OCR 入队/PostgreSQL 行锁队列、固定 `ocr-synthetic-v1` 评测和 linux/amd64 synthetic 真实模型烟测已完成。Redis/外部 Worker 适配、Ubuntu 原生基准/真实题型评测与生产 Profile/派生对象/备份级联仍在后续范围。
- [x] 6. 已执行相关质量门槛、安全审查和文档同步；真实设备、备份/法域和商业 Provider 的未完成项已记录。
- [x] 7. 读取项目 Owner 提供的架构讨论，建立并接受 ADR-0015；同步产品、架构、安全、决策、任务、测试和运维边界，明确旧代码与新目标冲突，本轮不修改代码/合同/迁移。
- [x] 8. 兼容实现里程碑已建立：Provider-neutral 脱敏/图片分析 Schema、PrivacySanitizer synthetic eval、本地检测信号、Flutter 脱敏预览/手动涂抹、旧 Capture 对象 SHA-256 核验、ImageAnalysis ledger/API、无 Provider offline Tutor Policy、Tutor hints API 和固定 Tutor synthetic eval 已完成。
- [x] 9. 自用部署边界已实现：ADR-0016 HMAC Bearer 令牌、Web/Flutter token 注入、OpenAI-compatible NewAPI Adapter、显式 enabled gate、0009 QuestionExtraction 持久化、ImageAnalysis queued worker、stale lease/稳定失败状态和提取读取合同已完成；NewAPI 仍默认关闭。
- [x] 10. 自用 Compose 交付边界已补齐：API/迁移镜像包含 Alembic 与 worker 入口，Compose 编排 PostgreSQL/Redis/MinIO/API/迁移、家长 Web 和默认 ImageAnalysis worker，配置样例与启动/升级/回滚文档已建立；完整启动、真实 NewAPI 联调、备份恢复和生产监控仍未验证。
- [x] 11. 优化本地开发体验：Flutter 首帧后提供有限时长启动过渡并与档案加载并行；ImageAnalysis worker 进入 Compose 默认 profile 且 Provider 关闭时安全空闲；API 镜像移除固定 amd64，验证 Linux/arm64 原生调试构建，同时保留 amd64 Paddle OCR 发布能力。

## Progress

- `2026-07-13` — `[done]` 为 OCR 边界增加 `read_object` 有界读取、声明大小/SHA-256 校验，以及 JPEG/PNG 容器头、尺寸、像素数和 JPEG EXIF 拒绝测试；完整像素解码和 EXIF 清理仍未宣称完成。
- `2026-07-13` — `[done]` 增加 PaddleOCR `rec_texts/rec_scores` 结果纯解析器；结果形状、置信度、控制字符和长度经校验，低置信度和空结果均保留人工确认路径。
- `2026-07-13` — `[done]` 增加本地 OCR 执行边界：安全输入仅写入临时文件供 `predict` 使用，调用结束后清理；引擎错误统一脱敏为 `OcrExecutionError`。
- `2026-07-13` — `[done]` 增加 Pillow `12.3.0` 显式锁定依赖；OCR 前对 JPEG/PNG 执行完整像素解码、EXIF 方向归一化和无元数据重编码，截断/无法解码的像素不会进入 PaddleOCR。linux/amd64 最终镜像无网络 synthetic PNG 烟测通过。
- `2026-07-13` — `[done]` 增加 `0005_ocr_result_persistence`、Provider-neutral 候选草稿和 PostgreSQL 事务仓储；保存候选文本及 Provider/模型/Schema 版本，空结果也保存，强制人工确认，支持幂等重放和 Household/Child 读取隔离，审计不保存候选原文。
- `2026-07-14` — `[done]` 增加 `evals/ocr_synthetic_v1.json` 与无 Provider/无网络的固定 OCR 合同评测 runner；6 个 cases 覆盖正常候选、低置信度、空结果、空行和拒绝路径，结果仅输出聚合摘要。
- `2026-07-14` — `[done]` 增加 `LocalOcrJob` Worker：已确认 Capture 才能进入有界对象读取、图片规范化、本地 OCR 和候选结果持久化；未确认上传、非法图片或 Provider 失败均不落库，Redis/外部 Worker 仍保留在后续范围。
- `2026-07-14` — `[done]` 增加 child-only 幂等 OCR 入队端点、`InMemoryOcrJobQueue`、PostgreSQL Job Ledger 和单次 `LocalOcrDispatcher`；成功只关联结果 ID，失败只记录稳定错误码，新的幂等键可重试，stale lease 可恢复。
- `2026-07-14` — `[done]` 将 OCR 失败接入 ADR-0011 生命周期：从失败发生时设置 `ocr_failure` 七天期限，重复失败不延长，到期清理继续复用现有行锁和可重试删除流程。
- `2026-07-14` — `[done]` 新增 `0006_ocr_job_ledger` 并完成 PostgreSQL 迁移/队列集成回归；完整 API 门槛为 64 项单元、15 项 PostgreSQL/MinIO 集成。
- `2026-07-14` — `[done]` 增加独立一次性 `run_ocr_worker.py` 入口；组装 PostgreSQL Queue、MinIO、预置 PaddleOCR 模型和 `LocalOcrJob`，启动/运行错误只输出稳定状态码。
- `2026-07-14` — `[done]` 增加 child-only OCR 结果读取路由与 `OcrResultWithCandidates` 合同；重新校验 Household/Child/Capture 绑定，候选结果只能进入人工确认流程；定向路由测试覆盖兄弟孩子、家长、跨家庭和 Capture 不匹配。
- `2026-07-14` — `[done]` 增加 child-only OCR 候选确认路由；只提交候选 ID 与 Capture 版本，复用 CaptureCorrection 追加写、版本冲突和幂等事务，OCR 结果保持不可变；PostgreSQL 组合回归覆盖候选确认。
- `2026-07-13` — `[done]` 增加按 Household/Child 边界原子认领 Capture 对象的级联删除编排；对象逐项删除，成功标记 `deleted`，失败标记 `failed` 并可重试，内存单元与 PostgreSQL 集成回归覆盖成功、失败重试、重复运行和错误 Household。
- `2026-07-14` — `[done]` 按客户端原型顺序实现 Flutter 第 1/2/3 张横屏 UI：学习桌、拍题输入页、OCR 题目确认页与分数思考提示页；加入 `image_picker 1.2.3` 相机/相册入口、iOS 权限声明、合成图片、候选文本编辑/确认、两级提示和思考状态交互，6 项 Widget 测试与静态分析通过。含原生插件的无签名 iOS `Runner.app` 已构建并重新安装到实体 iPad，用户已实机确认拍照、权限和“已选择题目照片”页通过。Flutter 不支持实体设备截图，目标 landscape QA 仍待 Xcode 设备查看器或手动截图。
- `2026-07-14` — `[done]` 增加 Flutter `CaptureApiClient`：使用 `crypto 3.0.7` 计算 SHA-256，按服务端合同完成预签名 PUT、确认和 OCR 幂等入队；本地 HTTP 合同测试覆盖请求顺序、图片头、上传字节和稳定幂等边界，Flutter 总测试数增至 8。真实设备接线仍等待有效 StudySession 和 iPad 可达的 MinIO 预签名地址。
- `2026-07-14` — `[done]` 将 `CaptureApiClient` 接入显式 `STUDY_CAPTURE_SESSION_ID` 调试开关；真实上传后页面只显示私有上传完成和 OCR 排队状态，不把合成候选当作真实结果。使用合成 StudySession 和 iPad 可达 MinIO 完成实体 smoke test，API 日志确认上传/确认/入队为 201/201/202。
- `2026-07-14` — `[done]` 增加 child-only OCR Job 状态读取路由和 OpenAPI 路径；Flutter 客户端可解析稳定 Job 状态和 `result_id`，跨孩子边界回归通过。
- `2026-07-14` — `[done]` Flutter 确认页接入有界 OCR Job 轮询、`result_id` 候选读取、人工确认和手工纠正；候选返回前保持等待，候选返回后不自动代答。客户端 HTTP 合同测试增至 3 项，Flutter 总测试数增至 9。
- `2026-07-14` — `[done]` 增加显式 local durable mode：API 的 Learning/Capture、OCR Job 和结果仓储可统一使用 PostgreSQL；Worker 增加可选 `--watch` 轮询模式，默认一次性命令保持不变。Ruff、Mypy、74 项 API 非集成测试和 `git diff --check` 通过。
- `2026-07-14` — `[done]` 完成 PostgreSQL/MinIO synthetic API + Worker 闭环回归：真实走签名对象上传、Job Ledger 领取/完成、`LocalOcrJob` 安全读取/规范化、候选结果持久化和 child-only 读取；Provider 使用 synthetic adapter，完整集成回归 17 项通过并清理对象。
- `2026-07-14` — `[done]` 增加 Ubuntu 24.04 CPU 真实模型评测预检；只检查 Linux/Ubuntu 24.04、x86_64、Python 3.12、Paddle 锁定版本和五个 SHA-256 模型目录，不读取图片、不下载模型。macOS 预检按预期阻塞。
- `2026-07-14` — `[done]` 增加 `ocr-model-synthetic-v1` 锁定模型 smoke runner；只在预检通过后生成内存 synthetic 数学题图、调用 PP-OCRv6 medium CPU Adapter，并输出 case 状态/延迟聚合，不接受图片路径或输出 OCR 原文。当前 macOS 预检阻塞，真实推理仍待 Ubuntu 环境。
- `2026-07-14` — `[done]` 优化 `LocalPaddleOcrAdapter` 的实例级引擎缓存：文本/公式引擎按需只初始化一次，重复使用前仍执行模型目录和 SHA-256 标记校验；新增复用回归测试，避免持久化 Worker 按图片重复加载模型。
- `2026-07-15` — `[done]` 补齐 `PP-FormulaNet_plus-M` 按需执行和 `rec_formula` 解析，公式无 Provider 置信度时固定走低置信度人工确认；锁定模型 smoke fixture 增加公式 case，真实推理继续受 Ubuntu 24.04 CPU 预检门禁保护。
- `2026-07-15` — `[done]` 将 OCR mode 以向后兼容的 `text` 默认值贯穿 OpenAPI、Flutter Capture 客户端、内存/PostgreSQL Job Ledger 和 Worker；新增 `0007_ocr_job_mode`、模式幂等冲突保护及普通/公式分流回归，旧客户端不发送请求体时行为不变。
- `2026-07-15` — `[done]` 完成 `0007_ocr_job_mode` 的本地 synthetic PostgreSQL downgrade/upgrade 往返验证；固定 `ocr-synthetic-v1` 评测 6/6 通过，当前 macOS 的真实模型 smoke 按预检稳定阻塞，未执行真实推理。
- `2026-07-15` — `[done]` 项目 Owner 将 OCR 定位改为本地脱敏、云端多模态解析；新增 ADR-0015 并将 ADR-0012 标记为被替代。为避免静默改写已实现行为，旧 OpenAPI/迁移/Worker/Flutter OCR 路线保持兼容。
- `2026-07-15` — `[done]` 新增 Provider-neutral PrivacySanitization/ImageAnalysisJob/QuestionExtraction/VerifiedQuestion Schema；实现本地 PrivacySanitizer 元数据清除、检测区域实色覆盖、不可逆重编码和不安全信号阻断，接入 OCR/规则敏感区域信号，6-case synthetic eval 通过。
- `2026-07-15` — `[done]` Flutter 拍题路径新增本地脱敏预览、手动涂抹、确认后不可逆 PNG 与 SHA-256；上传客户端只接收确认后的脱敏字节。Widget/analyze 通过，真实 iPad 渲染和手动涂抹仍需人工回归。
- `2026-07-15` — `[done]` Capture 上传确认新增私有对象实际 SHA-256 核验；对象存储、上传路由和 MinIO/PostgreSQL 集成回归通过，错误哈希会阻断状态推进。
- `2026-07-15` — `[done]` 新增 0008 receipt-only ImageAnalysis ledger/API；服务端绑定 Capture 版本和脱敏副本哈希，Provider 未启用时返回 `blocked/provider_not_enabled`，Flutter 新上传路径不再误启动旧 OCR。
- `2026-07-15` — `[done]` 完成 0008 receipt/API 到 queued/blocked 双态迁移，并新增 0009 QuestionExtraction 记录、PostgreSQL claim/complete/fail worker、失败稳定错误码和手工 review 读取路径；未确认提取不进入 Tutor。
- `2026-07-15` — `[done]` 新增无 Provider 的 `offline-tutor-policy.v1` 和 `tutor-hint.v1` Schema；固定输出 1～3 级提示、要求孩子回应、`direct_answer: null` 和 0 元成本，3-case synthetic eval 通过；Flutter 思考页同步支持第 3 级提示。
- `2026-07-15` — `[done]` 补齐自用 Compose 全栈部署：新增 `migrate`、API、家长 Web 和默认 ImageAnalysis worker，API 镜像复制迁移/脚本入口并保留构建期模型 SHA-256 门禁；新增 Web standalone Dockerfile、健康端点、`.env.example`、自动读取的 `.env` 与部署/升级/回滚说明。Compose 默认服务展开、Web 镜像构建和 Web 质量门槛通过，完整容器启动仍待本机执行。
- `2026-07-15` — `[done]` 按项目 Owner 的本机调试需求增加 Flutter 1.2 秒启动过渡（首页并行加载、减少动态效果时跳过）、将 ImageAnalysis worker 移入默认 Compose profile 并在 Provider 关闭时安全空闲；API 镜像改为宿主架构原生构建。Linux/arm64 无本地 Paddle OCR/模型/专用系统库的调试镜像已构建，amd64 继续保留锁定模型与旧 OCR 回滚能力。
- `2026-07-16` — `[done]` TASK-0006 代码闭环完成：人工确认接口生成 VerifiedQuestion，worker 成功/失败分支清理派生对象；synthetic NewAPI 联调、iPad 真实脱敏预览回归、备份级联和生产监控转为环境验收项。

## 不变量

- Capture 属于 Household、孩子和 StudySession；跨 Household 或未绑定孩子统一返回 404。
- 新 Capture 在 PrivacySanitizer/云视觉 Provider 未获准或不可用时必须保留重新裁剪、手工涂抹/录入和 `needs_correction` 路径；不得伪造可信解析结果或发送原图。
- 原始媒体、对象键、签名 URL、完整题目和校正文本不得进入审计、错误响应、日志或测试输出。
- 原图、对象键、签名 URL 和敏感 OCR 文本不得发送给云端；未通过安全门禁/用户确认的脱敏副本不得外发，同一图片不得自动广播给多个 Provider。
- Correction 追加写；同键同载荷重放原结果，同键异载荷冲突；派生版本由服务端控制。

## 回滚

保持 OpenAPI 兼容增量。发生安全问题时关闭云视觉/图片外发开关并降级为重新裁剪或手工录入；可显式启用已验证本地 OCR 作为不外发回滚 Provider，但不得重解释历史记录、发送原图、恢复已删除副本或删除校正/审计记录。

---

# PLANS.md — PLAN-0007 自用账号密码与孩子账号管理

## 计划元数据

- 计划 ID：`PLAN-0007`
- 关联任务：`TODO-012` / `ADR-0017`；进入执行时建立 `TASK-0007`
- 状态：`IN_PROGRESS`
- 优先级：`P0（下一优先级）`
- Owner：Codex（执行）；项目 Owner（用户，方案批准）
- 创建/更新：`2026-07-16`

## 目标与边界

用 PostgreSQL 本地账号密码和可撤销不透明会话替换当前自用 HMAC 家庭 Token。家长 Web 提供登录、首次强制改密和孩子账号管理；Flutter 孩子端使用孩子账号登录并把会话保存在系统安全存储。保持单 Household 自用，不接入短信、邮箱、社交登录、OIDC 或 MFA。

本计划涉及 `services/api`、`packages/contracts`、`apps/web`、`apps/child_flutter`、数据库迁移和 `infra/compose`，必须分里程碑验收。`TASK-0006` 的代码闭环已完成，本计划按用户授权自动进入 `IN_PROGRESS`。

## 产品与安全不变量

- `admin/admin123456` 只在账号表为空时创建，是公开的一次性引导凭据，不是长期默认密码。
- 默认凭据有效时只允许本机引导；登录后只能改密/退出，所有家庭数据和管理 API 均返回 `password_change_required`。
- 密码只存 Argon2id 哈希；原始会话只交付客户端一次，服务端只存摘要。密码、哈希、会话、Cookie 不进入日志、错误、审计正文、测试夹具或客户端构建产物。
- Household 和角色授权仍在每个资源上服务端执行；孩子账号只能绑定同 Household 的一个 ChildProfile，跨 Household 继续统一 404。
- Web 使用 HttpOnly Cookie + CSRF；Flutter 使用 Keychain/Android Keystore。不得继续用 `STUDY_API_TOKEN` 或 `--dart-define` 注入长期凭据。
- 禁用账号、改密、管理员重置和退出必须撤销相应会话；恢复命令只能从服务器本机执行并审计。

## 实施阶段

- [x] 1. 契约与依赖评审：OpenAPI 已增加认证与账号管理合同；锁定 `argon2-cffi==25.1.0` 和 Flutter `flutter_secure_storage==9.2.4`，用途、替代和供应链影响已记录。
- [x] 2. 数据库与领域：新增 `0011_account_password_session`（因 `0010` 已用于 VerifiedQuestion），建立 Account/AuthSession、唯一约束、索引、并发空表初始化和兼容迁移边界。
- [x] 3. API 认证核心：已实现 Argon2id、统一登录错误、5 次失败/15 分钟锁定、256 bit 不透明会话摘要、30 天到期、退出/撤销、改密/禁用/重置联动、孩子账号管理的当前密码再验证和 Household/角色/ChildProfile 反向授权；认证生命周期已写入现有 `audit_events`，只保存稳定事件名与资源 UUID。
- [x] 4. 安全初始化：空账号库事务创建 `admin/admin123456`，设置 `must_change_password`；回环限制、改密前数据阻断和改密后会话轮换已实现并测试。
- [x] 5. 家长 Web：已增加 `/login`、首次改密、退出、账号列表、孩子账号创建/启停/重置；使用 HttpOnly/SameSite Cookie、CSRF 和服务端路由保护，孩子账号管理操作要求当前家长密码再验证。
- [x] 6. 孩子 Flutter：已增加用户名/密码登录，并使用 `flutter_secure_storage` 保存会话；Capture API 使用会话 Bearer。真实 iPad 生命周期/重启验证待执行。
- [x] 7. Compose 与迁移切换：Compose 已启用 password/postgres 认证和 Cookie 配置；随 TASK-0007 删除 auth mode、HMAC/Demo 兼容、静态 Web token 和 Web auth-required 开关。
- [ ] 8. 完整质量门槛：API/Web/Flutter 本地质量门槛、OpenAPI/Schema 解析和 18 项 PostgreSQL/MinIO 集成已通过；迁移 downgrade/upgrade 往返、浏览器 E2E、真实设备登录/退出、备份恢复和正式敏感信息扫描仍待执行。

## 验收标准

- [ ] 全新 Compose 在账号表为空时只创建一个 `admin`；使用临时密码登录后，在改密前无法读取任何 Household/孩子/学习/图片数据。
- [ ] 改密后临时密码和所有引导会话失效；数据库、日志和浏览器/客户端产物中没有明文密码或原始会话。
- [ ] 家长可以创建、查看状态、禁用/启用和重置同家庭孩子账号；不能查看既有密码，不能绑定其他家庭 ChildProfile。
- [ ] 孩子可以登录自己的 Flutter 学习桌，只能访问绑定孩子；兄弟孩子、家长 API、跨家庭和枚举 ID 均被拒绝。
- [ ] Web Cookie、CSRF、会话到期/撤销、失败锁定、退出、改密、账号禁用和管理员恢复均有正反向测试。
- [x] Compose 已移除 `STUDY_API_TOKEN`/长期 token 配置，Flutter 已移除长期 token 构建注入；TASK-0007 已删除 HMAC 签发脚本、Demo Header 和所有兼容开关。

## 发布与回滚

发布切换已完成：扩展数据库/合同、切换 Web/Flutter、再删除旧 HMAC/Demo。出现登录或授权问题时优先前向修复；回滚到含旧认证路径的版本需项目 Owner 单独批准并限于隔离环境。账号/会话表和审计保持不删，不得清空家庭数据或重写学习记录。

## 剩余风险

- 公开默认密码存在抢先登录风险，必须依赖回环引导和改密前数据阻断；如果未来要求开箱即用的局域网首次登录，应改为随机一次性密码/安装码并另行批准。
- 无邮箱/短信/MFA 时，家长忘记密码只能使用本机恢复命令；服务器主机权限等同于家庭管理员权限。
- 单家庭方案不解决公网多租户注册、账号恢复和身份合规；范围扩展必须新建 ADR。

## 2026-07-16 执行记录

- `[done]` TASK-0006 已完成代码闭环，PLAN-0007 自动启动。
- `[done]` API/Web/Flutter/Compose 认证主链路已实现；新增账号绑定反向校验和家长重置密码入口。
- `[done]` 认证生命周期审计已接入内存与 PostgreSQL 账号仓储：成功/失败/锁定/阻断登录、改密失败/成功、再认证失败、登出、孩子账号创建、启停和重置均只写稳定事件名、Household/资源 UUID 和时间；认证回归、Ruff、Mypy 通过。
- `[done]` TASK-0007 已完成唯一密码认证和 Flutter 登录前服务端地址配置；API 122 项非集成/18 项 PostgreSQL-MinIO 集成、OpenAPI/Schema、Web 与 Flutter 本地质量门槛通过。
- `[pending]` 仍需在 Compose、浏览器和 iPad 上完成迁移往返、Cookie/CSRF、真实登录退出与设备重启验收；未执行项不能报告为通过。

---

# PLANS.md — PLAN-0008 Ubuntu x86_64 与自托管 NewAPI 环境验收

## 计划元数据

- 计划 ID：`PLAN-0008`
- 关联任务：`TASK-0006`、`PLAN-0007`、`TODO-008`、`TODO-012`、`ADR-0015`、`ADR-0016`、`ADR-0017`
- 状态：`IN_PROGRESS`
- Owner：Codex（执行）；项目 Owner（用户，Ubuntu/NewAPI 已提供）
- 创建/更新：`2026-07-16`

## 范围与安全边界

在用户提供的 Ubuntu VM `192.168.1.4:22`、账号 `syin`、`x86_64` 环境验证自托管 Compose、锁定模型构建和 NewAPI OpenAI-compatible Adapter。只使用 synthetic 图片和 synthetic 题目；真实儿童图片、真实学习记录和原始 Provider 响应不得上传、写入日志或进入仓库。NewAPI 只接受用户确认且哈希绑定的脱敏副本，失败不得切换 Provider。

`2026-07-16` 项目 Owner 进一步明确：运行时只保留“用户名+密码→可撤销会话”一种认证方式，删除 HMAC、Demo Header 和 Web 免登录开关；Flutter 必须在提交登录前允许验证、保存和更换服务端地址，地址变更时不得复用旧服务端会话。该收敛作为继续环境验收的前置增量，不扩大到短信、邮箱、MFA 或设备绑定。

## 阶段

- [x] 1. SSH、架构、Python 3.12、磁盘和 Docker 前置检查。
- [x] 2. 安装 Ubuntu 官方 Docker Engine/Compose v2，启用 daemon，并加入 `syin` 的 docker 用户组。
- [x] 3. 传输脱敏工作区、生成远程 `.env`、运行 Compose config 和 Alembic `0011` 前滚迁移。
- [x] 4. 构建 Linux x86_64 API/Web 镜像，确认五份模型构建期 SHA-256 校验和运行时不自动下载；容器预检已增加显式锁定 Debian 13 运行层选项，其他版本/架构/模型门禁仍保持严格。
- [ ] 5. 启动 PostgreSQL/Redis/MinIO/API/Web/worker，验证健康、账号首次改密、Cookie/CSRF 和孩子账号授权（Compose 健康、迁移、loopback bootstrap login 已通过；首次改密、Cookie/CSRF、孩子账号和 iPad 生命周期待验收）。
- [x] 5a. 在再次部署前收敛认证面：已删除 API HMAC/Demo 路径、旧签发脚本与相关配置，OpenAPI 和 Web/Flutter 只使用密码登录后的 Cookie/Bearer Session；Flutter 登录页已提供持久化服务端地址配置，并覆盖地址验证与跨服务端会话清理测试。
- [ ] 6. 使用 synthetic 脱敏图片配置 NewAPI 视觉模型，执行单 Provider `queued → extraction → VerifiedQuestion` 联调；不发送真实数据。`queued → extraction` 已通过；远端以家长/孩子会话调用人工确认生成 `VerifiedQuestion` 仍待验收。
- [x] 7. 做停止/重启、迁移、worker 失败清理和日志敏感信息审查；新增稳定 Provider 错误码和可清理 live eval，并同步任务/测试/安全/运行文档。

## 当前进度（2026-07-16）

- Ubuntu 宿主确认 `Ubuntu 24.04 LTS`、`x86_64`、Python `3.12.3`；Docker `29.1.3`、Compose `2.40.3` 已安装。按项目 Owner 要求关闭该 VM IPv6，并为 Docker daemon 配置 `socks5://192.168.1.100:7893` 出网代理。
- `/home/syin/study` 只接收排除 `.git`、依赖缓存、构建产物、`.env` 和图片的工作区；远端 `.env` 权限为 `600`，数据库/MinIO 密码由远端随机生成，NewAPI URL、Key 和 `gemini-3.1-flash-lite` 已配置并启用；Key 未写入仓库或输出。
- Compose 已在远端启动并重启恢复：PostgreSQL、Redis、MinIO、API、Web、迁移和 worker 均正常；API/Web `/healthz`、`0011` 迁移、loopback bootstrap login、模型预置目录、无网络运行时模型路径和内存 synthetic OCR smoke 已验证。Cloudflare 曾以 1010 拦截 Python `urllib` 默认 User-Agent；Adapter 改用受控的 `study-api/0.5` 后，synthetic NewAPI live eval 已成功完成 `queued → extraction`，返回 `needs_confirmation=true`，派生副本已删除且数据库残留 Job 为 0。未发送真实图片或输出原始 Provider 响应。
- 本次发现并修复 API Docker 构建上下文的 Python 缓存与 macOS AppleDouble 元数据排除，避免 Alembic 将 `*.pyc`/`._*.py` 当迁移脚本扫描。
- 已修复 OCR 预检无法识别自身锁定 Debian 13 镜像层的问题：宿主仍要求 Ubuntu 24.04，只有镜像声明的 `STUDY_OCR_CONTAINER_RUNTIME=true` 才允许 Debian 13；远端重建后预检 `ready`，完整 4-case synthetic OCR eval 通过。
- TASK-0007 认证收敛已在本地完成：OpenAPI `0.6.0`、API/Web/Flutter/Compose 只保留密码登录后的 Cookie/Bearer Session，Flutter 可在登录前配置服务端地址。API 122 项非集成/18 项 PostgreSQL-MinIO 集成、Web 完整质量命令和 Flutter 17 项测试通过；远端栈尚未用该增量重新部署。

## 回滚

只删除本次在 `/home/syin/study` 创建的部署目录和 Compose 项目（需用户明确授权后执行）；不删除 Docker Engine、系统包、其他容器或远程用户数据。NewAPI 异常时保持 `STUDY_NEWAPI_ENABLED=false` 并停止 worker，数据库迁移优先前向修复；Cloudflare 1010 的应用侧兼容修复只设置受限 User-Agent，不修改或绕过网关安全策略。
