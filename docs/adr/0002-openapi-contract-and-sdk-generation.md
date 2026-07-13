# ADR-0002：OpenAPI、AI Schema 与 SDK 生成

- 状态：`Accepted`
- 日期：`2026-07-12`
- Owner：`TBD（API + 客户端负责人）`
- 决策者：`项目 Owner（用户；2026-07-13 对话确认）`
- 关联：`TASK-0003`、`TASK-0004`、`TODO-002`
- 替代/被替代：`无`
- 批准记录：`2026-07-13`，项目 Owner（用户）批准执行本 ADR；生成器的具体实现选择仍须在首次生成 SDK 前记录并验证。

## Context

家庭/孩子/设备纵向切片已经让 API、Web 和 Flutter 消费同一份 OpenAPI 资源语义，但生成器、AI JSON Schema 的目录、兼容策略和 CI 漂移检查尚未决定。手工维护多套领域类型会在身份、幂等、错误码和空安全方面漂移。

## Decision Drivers

- 公共 HTTP API 与 AI 结构化输出需要单一、版本化的事实来源。
- 客户端必须安全消费契约，不复制核心领域类型。
- 增量演进需要明确破坏性变更、弃用、生成和回滚流程。

## Considered Options

1. API、Web 和 Flutter 各自维护请求/响应类型。
2. 只共享 OpenAPI 文档，客户端仍手写运行时代码。
3. `packages/contracts` 作为 OpenAPI 与 AI JSON Schema 的唯一来源，并从批准的生成器生成客户端 SDK。

## Decision

提议选择选项 3。`packages/contracts/openapi.yaml` 保存公共 HTTP 契约；同目录保存版本化 AI JSON Schema。API 实现和客户端 SDK 从该来源验证/生成，生成物可复现且 CI 检查“生成后无差异”。在选定 TypeScript/Dart 生成器前，客户端只可写最薄的传输适配层，不新增手工领域模型。新增字段优先可选且向后兼容；破坏性变更需新版本、迁移说明、弃用窗口和消费者验证。生成器、输出位置和允许的手工包装层仍待 Owner 批准。

## Consequences

### Positive

- API、Web、Flutter 和 evals 可共享 Schema、错误和版本语义。
- 契约变更能通过生成/差异检查及受影响客户端测试发现。

### Negative / Trade-offs

- 需要维护代码生成工具、模板版本和 CI 可复现性。
- 生成 SDK 可能不完全符合各端人体工程学，包装层必须保持薄且不复制语义。

### Risks and Mitigations

- 风险：生成器产生不安全或不兼容代码；缓解：锁定生成器、审查差异、样例与契约集成测试。
- 风险：破坏性 Schema 静默发布；缓解：CI 差异规则、版本/弃用说明和客户端兼容矩阵。

## Compatibility and Migration

- 兼容性：API `0.2.0` 的 `/healthz`、children/devices 路径保持；新字段默认可选。
- 迁移步骤：批准生成器后，定义 SDK 输出目录与命令，迁移 Web/Flutter 传输适配层，添加“生成后无差异”CI。
- 回滚：生成物可由锁定工具重新生成；若生成器不适合，保留 OpenAPI/Schema 并迁移到替代生成器，不删除已发布兼容路径。

## Validation

- 运行 OpenAPI/JSON Schema 结构检查、API 契约测试和受影响客户端类型/构建检查。
- 在 CI 验证生成后无差异，以及新增/弃用/破坏性变化的兼容规则。
