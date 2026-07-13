# ADR-0001：FastAPI 模块化单体与领域边界

- 状态：`Accepted`
- 日期：`2026-07-12`
- Owner：`TBD（技术负责人）`
- 决策者：`项目 Owner（用户；2026-07-13 对话确认）`
- 关联：`TASK-0004`、`TODO-002`、`ARCHITECTURE.md`
- 替代/被替代：`无`
- 批准记录：`2026-07-13`，项目 Owner（用户）批准执行本 ADR；未来拆服务仍须满足本文的证据与新增 ADR 条件。

## Context

P0/P1 需要同时支持身份、任务/会话、拍题、Tutor、错题和报告，但当前规模、团队和负载均未证明应拆分独立服务。现有 API 已是 FastAPI 进程内的合成 Profile/Device 切片；后续实现必须防止领域逻辑混入路由或跨模块直接读写数据。

## Decision Drivers

- 儿童数据与 Household 授权必须可审计且一致。
- P0/P1 需要较低的运维复杂度，同时保留可测试的领域边界。
- 未来只有在明确的扩容、隔离或团队边界证据出现时才拆分服务。

## Considered Options

1. 一个无边界的 FastAPI 应用和共享数据访问层。
2. 从 P0 开始拆为多个独立微服务。
3. 一个部署单元内的模块化单体，按领域定义接口、所有权和依赖方向。

## Decision

提议选择选项 3：以 `services/api` 为单个 FastAPI 部署单元，逐步建立 Identity/Profile、Plan/Task/Session、Capture、Tutor、Mistake/Mastery/Report、Notification 等领域模块。每个模块只通过明确的应用服务接口协作；模块不得直接修改其他模块拥有的表或绕过 Household 授权。PostgreSQL 仍是业务事实源，Worker 作为同一系统的异步执行边界而不是独立业务真相。

## Consequences

### Positive

- 保持事务、授权和审计链路简单，适合 P0/P1 的少量家庭验证。
- 领域接口和数据所有权为后续拆分提供可测边界。

### Negative / Trade-offs

- 需要代码审查持续阻止跨模块耦合；单体无法天然隔离所有资源与故障。
- 未来拆分仍需迁移、契约、可观测性和运行成本评估。

### Risks and Mitigations

- 风险：路由层或共享 ORM 模型形成隐式耦合；缓解：模块目录、依赖规则、模块级测试和架构审查。
- 风险：单个模块成为性能瓶颈；缓解：先记录延迟/队列/资源证据，再以新 ADR 决定独立扩容或拆分。

## Compatibility and Migration

- 兼容性：既有 `/healthz` 和 Profile/Device OpenAPI 路径保持向后兼容；本 ADR 不改变公共 API。
- 迁移步骤：后续领域实现先定义模块边界和仓储接口，再引入数据库迁移与契约测试。
- 回滚：在未拆服务前可回退单体内模块实现；已持久化数据优先向前修复，禁止破坏 Attempt/AuditEvent 追加记录。

## Validation

- 审查 `ARCHITECTURE.md` 的组件所有权与代码目录一致。
- 为跨 Household、跨角色和跨模块访问建立反向测试。
- 在任何拆服务提案前提交负载、隔离或团队边界证据及新的 ADR。
