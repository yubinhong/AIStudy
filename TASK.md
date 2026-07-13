# TASK.md — TASK-0006 Capture 与人工校正安全基础

## 任务元数据

- 状态：`IN_PROGRESS`
- 类型：`FEATURE`
- 优先级：`P1`
- Owner：Codex（执行）；项目 Owner（用户，明确要求继续 TODO-008）
- 创建/更新：`2026-07-13`
- 基线分支/提交：`master`；无 commit；工作区含既有未提交骨架和 synthetic Learning 持久化切片
- 关联：`TODO-008`、`PLAN-0006`、`ADR-0001`、`ADR-0002`、`ADR-0004`、`ADR-0005`、`ADR-0006`、`ADR-0009`

## 1. 目标与范围

实现 Capture 与低置信度人工校正的安全基础：孩子只能在自己的 Household/StudySession 内登记一份图片采集元数据，服务端不把未验证 OCR 结果当作事实；在没有获准 OCR Provider 时，Capture 必须进入人工校正状态，校正记录以追加写保存。

本任务包含：Capture OpenAPI 增量、API 领域/仓储/迁移、Household/child 授权、版本冲突与幂等、合成 PostgreSQL 集成测试，以及必要的架构/安全/运行记录。

本任务不包含：真实儿童图片、生产对象存储/密钥、商业 OCR Provider、真实设备相机/SQLite UI 或 Tutor。按 ADR-0010～0012，本任务后续可只使用 synthetic 图片接入本地 MinIO 预签名上传与本地 PaddleOCR；S3 SDK、PaddleOCR 运行时/模型版本、EXIF/魔数/尺寸解析仍须先锁定并验证。

## 2. 已知冲突与实施假设

- `CONFLICT-01`：新版 `AGENTS.md` 的“当前仓库阶段”仍称业务实现和数据库迁移不存在；实际代码、`0001_learning_event_foundation` 与 15 项 API 测试已存在。按仓库规则，以可运行代码、锁文件和测试为事实，本任务不回退现有实现。
- `ASSUMPTION-01`：在 OCR Provider、数据处理条款与预算未批准前，所有新 Capture 都以 `needs_correction` 状态创建，不调用外部服务，也不产生伪造 OCR 内容。
- `ASSUMPTION-02`：本阶段仅接收受限的媒体声明（类型、大小、不可逆内容哈希），不接收原始图片、对象键、签名 URL 或完整题目文本；人工校正内容只进入业务库，永不写入审计事件或错误响应。
- `ASSUMPTION-03`：校正是追加事件；Capture 的派生状态以服务端 `version` 明确合并，不能用最后写入覆盖已有校正。

## 3. 验收标准

- [ ] OpenAPI 定义 Capture、人工校正、版本化请求/响应、错误与兼容策略；不引入手工漂移的跨端公共模型。
- [ ] 仅绑定孩子可为自己的 Session 创建、读取、校正 Capture；跨 Household、同家庭其他孩子、无绑定主体和枚举 ID 均被拒绝。
- [ ] Capture 初始必须要求校正；校正追加写、幂等重放和版本冲突可验证，审计中无原始题目或校正文本。
- [ ] PostgreSQL 迁移和仓储在同一事务处理 Capture、校正、幂等记录与审计；验证迁移回滚/前滚、重复请求和并发校正。
- [ ] 记录真实媒体、OCR Provider、设备权限/离线 SQLite 与生产生命周期仍未实现的原因、回滚方式和下一步。

## 4. 验证与回滚

- 计划验证：OpenAPI 结构检查、API Ruff/Mypy/单元与 local PostgreSQL 集成测试、Alembic downgrade/upgrade；不运行真实 Provider 或真实图片。
- 回滚：合同仅新增；优先关闭 Capture 路由或前向修复迁移。不得删除 CaptureCorrection/AuditEvent、不得把校正文本写进日志、不得清空客户端队列。

## 5. 当前进度

- `2026-07-13`：项目 Owner 明确授权执行 `TODO-008`；已复核 PRD、架构、安全、测试、ADR 和现有 Learning 持久化边界，建立本任务与计划。
- `2026-07-13`：OpenAPI `0.4.0` 已增加 Capture 元数据、人工校正和显式版本冲突合同。Capture 创建只接收 MIME、大小和 SHA-256 声明，且始终进入 `needs_correction`；不接收原始媒体或调用 OCR Provider。
- `2026-07-13`：API 已实现 child-only Capture 创建/查询和追加校正；`0002_capture_manual_correction` 在 PostgreSQL 中保存 Capture/Correction、幂等记录和无原文审计事件。19 项 API 测试及 migration downgrade/upgrade 演练通过。
- `2026-07-13`：项目 Owner 已接受 ADR-0010（本地 MinIO/私有 Bucket/预签名上传）、ADR-0011（24 小时/7 天/30 天保留、家长控制、级联删除）与 ADR-0012（本地 PaddleOCR、人工确认、外部默认 0 元）。
- 下一步：选择并锁定 S3 SDK 与 PaddleOCR 运行时/模型版本，实施签名上传和本地 OCR Adapter；本任务保持 `IN_PROGRESS`，且不接入真实儿童图片。
