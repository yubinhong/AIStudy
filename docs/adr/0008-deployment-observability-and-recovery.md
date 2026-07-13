# ADR-0008：部署、可观测性与恢复基线

- 状态：`Accepted`
- 日期：`2026-07-12`
- Owner：`TBD（运维 + 安全负责人）`
- 决策者：`项目 Owner（用户；2026-07-13 对话确认）`
- 关联：`TASK-0004`、`TODO-002`、`TODO-004`
- 替代/被替代：`无`
- 批准记录：`2026-07-13`，项目 Owner（用户）批准执行本 ADR；平台、SLO/RPO/RTO、值班与 Secret Manager 仍须在 staging 前明确。

## Context

当前只存在本地 Compose 配置，尚未启动持久卷或建立 staging/production。儿童数据、离线同步和 AI 成本要求明确环境隔离、最小权限、日志脱敏、部署/回滚和恢复演练；平台、Secret Manager、SLO、RPO/RTO、值班与预算阈值均为 TBD。

## Decision Drivers

- 任何 staging/production 操作必须与 local 数据、凭据和网络隔离。
- 需要发现授权、同步、AI 安全/成本、删除和备份失败，且不记录原始敏感内容。
- 部署和迁移必须可审查、可回滚或可前向修复。

## Considered Options

1. 从开发机手工部署并用应用日志排障。
2. 先建立 production，再补充 staging 和恢复流程。
3. 先建立隔离的 staging、版本化 CI 产物、结构化遥测、演练过的恢复与批准的 production 路径。

## Decision

提议选择选项 3。local、staging、production 使用独立账户、网络、数据库、对象 bucket 与密钥；CI 生成版本化产物并以最小权限部署，生产凭据不进入本地或 PR 作业。应用/Worker 输出允许字段白名单的结构化日志和 OpenTelemetry 指标/追踪，记录不可逆家庭/设备标识、版本、延迟、队列和成本，不记录儿童原文/图片/令牌。发布采用兼容性检查、迁移前置检查、合成烟雾、功能降级和优先前向修复；staging 必须完成授权、离线、AI、删除/导出和恢复演练。具体平台、Secret Manager、告警数值、RPO/RTO 与值班 Owner 待批准。

## Consequences

### Positive

- 环境与数据边界明确，故障能以最小敏感信息诊断。
- 把部署、迁移、告警和恢复纳入发布门槛。

### Negative / Trade-offs

- 需要维护 CI/CD、可观测性、备份和演练成本。
- 生产交付会被未决的平台、SLO/RPO/RTO 和 Owner 阻塞。

### Risks and Mitigations

- 风险：日志或调试追踪泄露儿童数据；缓解：字段 allowlist、脱敏测试、访问最小化与审计。
- 风险：迁移或回滚造成记录损失；缓解：迁移演练、兼容窗口、追加事件不覆盖、优先前向修复。

## Compatibility and Migration

- 兼容性：本地 Compose 仅用于合成数据；不隐含可发布生产环境。
- 迁移步骤：先选择平台和 Secret Manager，建立 staging，再定义 CI 部署、备份恢复、告警和发布审批。
- 回滚：按功能开关/已验证版本回退；数据变更遵循前向修复，保持客户端队列和版本化契约兼容。

## Validation

- 在 staging 演练部署、回滚、迁移、恢复、授权越权、离线重连、AI 降级和删除失败告警。
- 评审日志字段、环境隔离、CI 权限、备份恢复记录和已批准 SLO/RPO/RTO。
