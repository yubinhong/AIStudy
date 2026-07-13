# TASK.md — TASK-0005 任务、会话、Attempt 与离线同步基础

> `TASK-0004` / `TODO-002` 已于 2026-07-13 完成：项目 Owner（用户）接受 ADR-0001～0008。本文是当前唯一活动任务，承接 `TODO-007`。

## 任务元数据

- 状态：`COMPLETE`
- 类型：`FEATURE`
- 优先级：`P1`
- Owner：Codex（执行）；项目 Owner（用户，已批准架构方向）
- 创建/更新：`2026-07-13`
- 基线分支/提交：`master`；无 commit；工作区含既有未提交骨架与合成 Profile/Device 切片
- 关联：`TODO-007`、`PLAN-0005`、`ADR-0001`、`ADR-0002`、`ADR-0003`、`ADR-0005`、`ADR-0006`

## 1. 目标与范围

实现 P1 学习过程的第一阶段：家庭内家长可创建/读取数学任务，孩子可开始 StudySession、追加 Attempt，并通过版本化同步批次提交离线事件。服务端为每个事件执行 Household/角色/设备边界、幂等和显式冲突处理；客户端只保存待同步操作，不把本地状态作为业务事实。

本阶段包含：OpenAPI 增量、API 模块边界、领域状态机/事件模型、合成数据测试实现、反向授权/幂等/冲突测试，以及 Flutter 端不含真实数据的队列最小入口。

本阶段不包含：真实 IdP、PIN/设备令牌、真实儿童数据、Capture/Tutor、AI Provider、错题/周报、生产部署。PostgreSQL 迁移与持久仓储已在本任务完成；内存仓储只保留给 local/CI 单元测试，不得描述为业务事实源。

## 2. 安全与实现假设

- `ASSUMPTION-01`：保留现有 demo principal 仅用于 local/CI；所有新增资源继续按 Household 不匹配返回 404，不能用客户端隐藏代替授权。
- `ASSUMPTION-02`：阶段一使用模块化内存仓储验证契约和合并语义；PostgreSQL 与版本化迁移在同一任务后续阶段替换它，且需要迁移/集成验证。
- Attempt/AuditEvent 只追加；任务派生状态通过服务端版本、允许状态机和已应用事件 ID 合并。相同幂等键/等价载荷返回原结果，同键不同载荷拒绝并审计。
- 只使用 `Synthetic` 任务、会话和作答 fixture；日志、响应与测试不包含真实儿童资料、题目全文或设备令牌。

## 3. 验收标准

- [x] `packages/contracts/openapi.yaml` 定义 Task、StudySession、Attempt 与同步批次的版本化请求/响应/错误，且 API 契约结构检查覆盖。
- [x] 家长可创建/读取自身 Household 任务；孩子只可读取分配任务、开始会话并追加 Attempt；跨 Household、角色不足、缺失主体和 ID 枚举均被拒绝。
- [x] Attempt 与审计事件可追加；重复/冲突离线事件符合 ADR-0003，且不会覆盖历史或产生重复副作用。
- [x] Flutter 端有空安全的本地待同步队列边界与单元/Widget 测试，不手写重复的公共 OpenAPI 领域模型。
- [x] PostgreSQL 迁移/持久仓储、连接池重连、并发版本冲突与回滚/前滚演练已完成；真实设备断网和 SQLite 落盘仍属于后续端侧工作。

## 4. 验证记录

- 计划命令：API `ruff format/check`、`mypy`、`pytest`；OpenAPI 结构/契约检查；Flutter format/analyze/test；后续 PostgreSQL 集成、重复请求、并发、断网重连与迁移验证。
- 每个阶段需记录未运行项、替代验证、残余风险和精确下一步；不得以重跑掩盖 flaky 或授权失败。

## 5. 回滚与剩余风险

- 回滚：以向后兼容合同为先；新增事件类型和字段只增不改。持久化阶段优先前向修复，禁止删除 Attempt/AuditEvent 或清空客户端队列。
- 当前风险：demo principal 不是生产认证；Profile/Device 仍是合成内存切片；SDK 生成器、Flutter SQLite 落盘、真实设备断网、staging 迁移恢复与实际多端并发尚未验证。

## 6. 当前进度

- `2026-07-13`：OpenAPI `0.3.0` 已新增 Task、StudySession、Attempt 与 SyncBatch；API 以独立 Learning 模块实现 synthetic 授权、任务版本、Attempt/Audit 追加、幂等和离线批次预检。
- `2026-07-13`：Flutter 新增通用离线队列边界；它仅保留 transport JSON、event ID 和 idempotency key，并在服务端 applied/replayed 后确认删除。
- 验证：OpenAPI 学习路径结构检查通过；API Ruff/Mypy/11 项单元测试通过；Flutter analyze 与 4 项测试通过；交互式 `flutter doctor -v` 全绿。
- `2026-07-13`：ADR-0009 已接受；Docker Desktop 29.2.1 与 local PostgreSQL 16.10 已验证，SQLAlchemy 2.0.51、Alembic 1.18.5、Psycopg 3.3.4 已锁定；首个 learning schema 的 upgrade/downgrade/upgrade 演练通过。
- `2026-07-13`：`PostgresLearningRepository` 已接入 API（设置 `STUDY_API_LEARNING_REPOSITORY=postgres`），对 Task 版本、Attempt/AuditEvent、幂等记录使用同一 PostgreSQL 事务；内存实现保留给未配置数据库的 local/CI 单元测试。
- 验证：OpenAPI 结构检查通过；API Ruff/Mypy 与 15 项测试通过（11 单元、4 PostgreSQL 集成，覆盖持久化、幂等、批次原子性、连接池重连和并发版本冲突）；Alembic 位于 `0001_learning_event_foundation (head)`；Flutter analyze 与 4 项测试通过。

## 7. 完成记录

- 状态：`COMPLETE`（2026-07-13）。
- 未执行项：未运行真实设备断网、Flutter SQLite 落盘/重启恢复、staging 备份恢复或生产迁移；这些不以本地 synthetic PostgreSQL 验证替代。
- 回滚：保持 `0.3.0` 合同兼容；发现持久化问题时优先关闭 `STUDY_API_LEARNING_REPOSITORY=postgres` 写路径或发布前向修复迁移，绝不删除 Attempt/AuditEvent、清空队列或回滚含数据的生产迁移。
