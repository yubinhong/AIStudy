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

建立 Capture 的服务端安全数据流：受限媒体声明 → 必须人工校正 → 追加校正事件；随后按 ADR-0010～0012 接入本地 MinIO 与本地 PaddleOCR。真实儿童图片、生产保留/备份、商业 Provider 仍不在范围内。

## 阶段

- [x] 1. 复核 PRD、架构、安全、测试、已接受 ADR、工作区和现有 Learning 代码，记录文档与代码基线冲突。
- [x] 2. 在 `packages/contracts` 增加向后兼容 Capture/Correction `0.4.0` 合同和结构检查。
- [x] 3. 在 API 建立 Capture 领域模型、child-only 授权路由、内存参考仓储与 PostgreSQL 事务仓储，禁止原始媒体/文本进入审计。
- [x] 4. 新增版本化迁移与 local PostgreSQL 集成测试，覆盖家庭隔离、幂等、校正追加和 downgrade/upgrade；真实多请求并发仍待下一里程碑。
- [ ] 5. 选择并锁定 S3 SDK 与本地 PaddleOCR 运行时/模型版本，实施私有 MinIO 预签名上传、本地 OCR Adapter、人工确认与固定 synthetic eval。
- [ ] 6. 执行相关质量门槛、安全审查和文档同步；记录真实设备、备份/法域和商业 Provider 的未完成项。

## 不变量

- Capture 属于 Household、孩子和 StudySession；跨 Household 或未绑定孩子统一返回 404。
- 新 Capture 在无获准 OCR Provider 时必须为 `needs_correction`；不得伪造可信 OCR 结果。
- 原始媒体、对象键、签名 URL、完整题目和校正文本不得进入审计、错误响应、日志或测试输出。
- Correction 追加写；同键同载荷重放原结果，同键异载荷冲突；派生版本由服务端控制。

## 回滚

保持 OpenAPI 兼容增量。发生安全问题时关闭 Capture 路由或前向修复；不删除校正/审计记录，不把错误恢复建立在清空数据上。
