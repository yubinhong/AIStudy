# ADR-0009：PostgreSQL 持久化与版本化迁移依赖

- 状态：`Accepted`
- 日期：`2026-07-13`
- Owner：`TBD（技术负责人）`
- 决策者：`项目 Owner（用户；2026-07-13 对话确认）`
- 关联：`TASK-0005`、`TODO-007`、`ADR-0001`、`ADR-0003`
- 替代/被替代：`无`
- 批准记录：`2026-07-13`，项目 Owner（用户）接受本 ADR 并授权继续本地 Docker/PostgreSQL 环境准备；真实儿童数据与 production 环境仍不在授权范围内。

## Context

TASK-0005 的合成仓储已经验证 Task、StudySession、Attempt 与离线事件语义，但 PostgreSQL 必须成为业务事实源。Python 服务当前没有数据库驱动、ORM 或迁移工具；直接在路由里拼接 SQL 会破坏模块边界、迁移纪律和可测试性。

## Decision Drivers

- Attempt、AuditEvent、幂等记录和任务版本必须在 PostgreSQL 事务中可靠写入。
- 数据库结构必须通过可审查、可升级且可回滚/前滚的版本化迁移演进。
- 新依赖要有明确许可证、维护来源、供应链边界、服务成本与替代方案。

## Considered Options

1. 手写 SQL + 自定义迁移脚本：依赖少，但事务、类型、迁移元数据与测试模式容易分散。
2. SQLAlchemy 2.x + Alembic + Psycopg 3：成熟的 Python ORM/事务与迁移组合；SQLAlchemy/Alembic 为 MIT，Psycopg 为 LGPL-3.0，需纳入项目许可证与供应链审查。
3. SQLAlchemy Core + Alembic + pg8000：避免 LGPL 驱动，但生态、性能经验与本项目现有验证较少，仍需评估维护与连接特性。

## Decision

选择选项 2：服务端引入 SQLAlchemy `2.0.51`、Alembic `1.18.5` 和 Psycopg `3.3.4`，采用同步事务边界实现 PostgreSQL 仓储和版本化迁移。依赖仅在 API 服务端运行，不增加 Flutter/Web 客户端体积；本地 Compose 的 PostgreSQL 16.10 继续只使用 synthetic 数据。版本已写入 `pyproject.toml`/`uv.lock`；CI 接入前以本地迁移和集成测试验证。

## Consequences

### Positive

- 领域仓储可在一次事务中写入 Attempt、审计、幂等记录和任务版本。
- Alembic 迁移脚本为扩展、收缩、回滚/前滚和 schema 审查提供固定入口。

### Negative / Trade-offs

- 增加三个服务端依赖、连接配置和迁移维护成本。
- Psycopg 的 LGPL-3.0 需要在项目许可证、分发方式和 SBOM 策略确定前持续审查。

### Risks and Mitigations

- 风险：迁移与运行应用版本不兼容；缓解：expand/contract、迁移前检查、旧客户端/离线事件测试、优先前向修复。
- 风险：连接池或事务边界造成重复写入；缓解：数据库唯一约束、幂等指纹、事务测试和并发集成测试。
- 风险：本地 Compose 误连接外部服务或留下敏感数据；缓解：只使用当前 local Compose、synthetic fixtures，启动前检查端口/卷/环境变量。

## Compatibility and Migration

- 兼容性：当前 `0.3.0` 合同保持；持久化替换不改变已发布字段，新增字段仅作兼容增量。
- 迁移步骤：建立 Alembic 环境和首个 schema → 在 local PostgreSQL 执行 upgrade/downgrade 演练 → 将学习仓储切换为数据库实现 → 保留合成仓储给 unit tests。
- 回滚：优先停用新写路径或前向修复；不得通过删除 Attempt/AuditEvent、清空离线队列或不可逆 DDL 恢复。

## Validation

- 已使用锁文件安装；许可证与来源记录在本 ADR，已知漏洞/SBOM 扫描仍是发布前门槛。
- 已在 local Compose 上验证首次迁移、downgrade/upgrade、重复请求、并发写入、事件冲突和连接池重连；真实设备离线与 staging forward-fix 仍待后续任务。
- 已审查本地测试仅使用 synthetic 数据；数据库、日志和备份的生产审查仍是发布前门槛。
