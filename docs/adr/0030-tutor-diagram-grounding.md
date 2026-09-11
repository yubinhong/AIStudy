# ADR-0030：Tutor 解答携带已确认题图

- 状态：Accepted
- 日期：2026-09-11
- 关联：`PLAN-0051`、`TASK-0012`、`ADR-0018`、`ADR-0022`、`FR-004`、`FR-005`、`FR-018`
- 替代：仅替代 ADR-0022 中“Tutor 不发送图片”的实现约束；不改变其递进提示、来源约束、家长审核和单 Provider 边界

## 背景

数学题的关键数字、数量关系或位置关系可能只出现在题图中。现有 Tutor 请求只发送已确认题干和作答证据，因此模型无法看到这些已知信息，可能生成与题目不符的提示或解答。

## 决策

1. 只有在 `VerifiedQuestion` 已由孩子或家长确认后，Tutor 才可以为 L1/L2/L3 从同一 Household/Child 授权的 Capture 私有对象读取题图。服务端重新校验对象大小、SHA-256、JPEG/PNG 文件头、像素和完整解码，并沿用现有元数据清除/有界规范化流程。
2. NewAPI Adapter 在同一个结构化请求中发送 JSON 题干作为文本片段，并在有可用题图时发送有界 `data:image/jpeg|png;base64,...` 图片片段。Provider 永远不会收到对象存储 URL、对象键、预签名 URL、PDF 或未经确认的 Extraction。
3. 题图中的可见标签、数字、数量、位置和关系是解题的有效证据；Tutor Prompt 必须要求模型结合题干与题图，不得忽略图中事实或凭空补全缺失事实。
4. 当 `has_diagram=true` 且已启用 Provider 但题图对象缺失、校验失败或无法安全读取时，API 返回稳定的 `409` 并要求重新拍题，不得静默退化为文字-only 的云端解答。非含图题或 Provider 未启用时保留既有兼容行为。
5. 题图只在当前 Provider 调用的内存中存在，不写入 TutorTurn、日志、评测夹具或模型仓库；仍遵守单一获批 Provider、成本上限、失败重试和家庭图片保留策略。

## 兼容性、风险与回滚

- OpenAPI 请求仍只携带服务端签发的 `verified_question_id`，不新增客户端图片字段，不需要数据库迁移；无图调用的 Provider 方法保持默认参数兼容。
- 该变更扩大了已确认脱敏题图的 Provider 输入，必须以 synthetic 图片验证多模态载荷、大小上限、单 Provider 和日志脱敏；真实儿童图片/真实 Provider 质量仍需单独审批和验收。
- 紧急回滚可恢复上一 API/Web 镜像，使 Tutor 回到 text-only；不执行数据库 downgrade，不删除 Capture、VerifiedQuestion、TutorTurn 或学习事实。

## 验证

- Provider 单测覆盖有图/无图的 L1/L2/L3 请求结构和有界图片准备。
- Tutor 路由回归覆盖 Household/Child 授权、含图传递和已确认题图缺失时的 409 阻断。
- 发布前执行 API 契约、Ruff、Mypy、定向/全量非集成测试和 Ubuntu 运行时源码/健康检查。
