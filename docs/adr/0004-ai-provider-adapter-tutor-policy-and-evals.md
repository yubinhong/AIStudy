# ADR-0004：AI Provider Adapter、Tutor Policy 与固定评测

- 状态：`Accepted`
- 日期：`2026-07-12`
- Owner：`TBD（AI + 安全负责人）`
- 决策者：`项目 Owner（用户；2026-07-13 对话确认）`
- 关联：`TASK-0004`、`TODO-002`、`TODO-008`、`TODO-009`
- 替代/被替代：默认图片解析路线最初由 ADR-0012 细化，现由 ADR-0015 替代
- 批准记录：`2026-07-13`，项目 Owner（用户）批准执行本 ADR；Provider、数据处理条款、预算和评测阈值仍是接入前阻塞项。

## Context

OCR、视觉和推理模型都可能误识别、直接给答案、泄露敏感内容或产生不可控成本。项目需要可替换 Provider，同时保证孩子端只收到经策略和 Schema 验证的分级提示。尚未批准任何 Provider、数据处理条款、预算或评测阈值。

## Decision Drivers

- 业务领域不能依赖某个厂商 SDK 或响应形状。
- AI 输出不是业务事实，必须可校验、可审计、可回滚。
- 需要把“先提问和提示、不抢先代答”变成可测试的策略。

## Considered Options

1. 在业务路由直接调用选定模型并展示自然语言结果。
2. 只依赖单一云厂商的 SDK 和安全能力。
3. Provider Adapter + 版本化 Tutor Policy + 固定 JSON Schema + 离线评测集与成本控制。

## Decision

选择选项 3。Capture/Tutor 只依赖内部 Provider Adapter；每次调用由版本化 Tutor Policy 决定允许的提示层级、最少上下文、模型路由、超时和成本上限。输出必须先通过固定 JSON Schema、敏感内容和直接代答检查；低置信度识别/推理必须请求用户校正。所有调用记录不可逆标识、Provider/模型/Prompt/Policy/Schema 版本、摘要指纹、延迟、token/成本、置信度与结果，不记录原始儿童内容。当前默认图片路线由 ADR-0015 细化为“本地隐私脱敏 + 用户确认 + 单一获批云端视觉 Provider 解析”，ADR-0012 的本地完整 OCR 默认路线已被替代；具体云 Provider、固定评测门槛、预算和数据处理条款仍须在真实数据接入前完成。

## Consequences

### Positive

- 可替换模型并对策略或路由回归进行版本比较和回滚。
- AI 风险被限制在适配、策略、校验和审计边界内。

### Negative / Trade-offs

- 需要维护 Adapter、Schema、评测样本和失败降级路径。
- Schema 或策略失败时可能降低自动化程度，必须保留安全的手工学习路径。

### Risks and Mitigations

- 风险：模型绕过提示层级或输出有害内容；缓解：策略后校验、拒绝/降级、固定安全评测和发布阻断。
- 风险：成本失控或 Provider 不可用；缓解：每请求/家庭预算、超时、有界重试、低成本/暂停 AI 降级。

## Compatibility and Migration

- 兼容性：不改变现有 Profile/Device 合同；Tutor 新增版本化响应 Schema。
- 迁移步骤：先批准 Provider 数据条款和评测指标，再实现 Adapter、Policy、合成评测集与 CI 门槛。
- 回滚：按版本切回已验证的 Policy/模型或关闭 Tutor 功能；任务和手工校正路径保持可用。

## Validation

- 固定评测覆盖分级提示、直接代答拒绝、低置信度校正、Schema 失败、敏感内容、超时与成本上限。
- 记录并比较每次模型/Prompt/Policy/路由变更的质量、安全、延迟和成本。
