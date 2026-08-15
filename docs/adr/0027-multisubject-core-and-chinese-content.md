# ADR-0027：多学科核心与语文内容/评分边界

- 状态：Accepted
- 日期：2026-08-15
- 决策者：项目 Owner（要求按研究报告先做多学科，再增加语文，英语最后）
- 关联：`PLAN-0030`、`TASK-0012`、`docs/deep-research-report.md`

## Context

当前通用任务和会话模型已有 `subject` 字段，但 `Subject`、孩子档案契约和数据库约束只允许 `math`；教材没有显式学科。英语口语是独立受限插件，因此语文将成为首个进入通用学习闭环的第二学科。若直接增加语文页面，会导致教材、任务、报告和复习继续隐式按数学解释。

语文既包含可确定性评分的拼音、字词、排序、填空和证据定位，也包含不宜由首版模型武断打分的开放表达。家庭私有教材的授权、版本、页码和审核边界必须继续复用，但语文篇章和证据不能被压成数学式单题结构。

## Drivers

- 保证历史数学数据与行为兼容。
- 让未来科学等学科复用同一任务/会话骨架。
- 让语文评分可测试、可版本化、可审计，默认不依赖 LLM。
- 保持 Household/Child 授权、教材来源审核、幂等和儿童数据最小化。
- 不提前改变英语 Provider 与实时音频合同。

## Options

1. 为语文复制 `ChineseTask`/`ChineseSession`。实现快，但会制造第三套学习生命周期和长期漂移。
2. 只给现有数学题结构增加若干语文字段。表面统一，但阅读篇章、证据范围和多答案规范会被数学模型限制。
3. 通用生命周期 subject-aware，内容与 scorer 学科专用。迁移面更大，但边界清晰且可继续扩展。

## Decision

采用选项 3：

- `Subject` 首阶段支持 `math`、`chinese`；孩子启用学科、任务和教材显式携带该枚举。
- `StudyTask`/`StudySession` 继续作为通用生命周期；语文内容以不可变 `content_id + revision` 引用，不在任务中复制长篇正文。
- 新建 `ChineseContentItem`、`ChineseAttempt` 和 `ChineseReviewItem`。答案规范使用显式题型联合，首版只允许确定性 scorer；开放表达只提供有界规则反馈，不判定标准答案。
- 教材 Material/Snapshot 保存 subject；旧记录统一回填 `math`。公开教材复用必须额外匹配 subject，避免相同文件元数据被跨学科解释。
- 所有语文端点继续验证 Household、孩子所有者/绑定关系和孩子已启用学科；写操作要求 `Idempotency-Key`。
- 英语保留 ADR-0025 的独立插件与禁用门禁，待语文稳定后另行评估，不在本次迁移中并入通用任务模型。

## Consequences

- 数学 API 只获得向后兼容的枚举扩展；旧客户端发送 `math` 不受影响。
- 语文内容需要独立教研、版权来源台账和 golden scorer 数据，不能把 synthetic starter set 描述为正式课程内容。
- 教材分析 Prompt/Schema 仍需后续按 subject 建立新版本；在完成前，语文教材可导入和审核元数据，但不得静默使用数学分析 Prompt。
- 家长报告、通用跨学科 Review 聚合和语文开放表达 AI 反馈属于后续里程碑。

## Migration And Rollback

使用 additive migration：先新增可空教材 subject、回填 `math`、再设为不可空并更新孩子学科约束；新建语文表和索引，不修改历史 Attempt。应用回滚仅隐藏/拒绝语文入口并保留新增事实；数据库采用前向修复，不删除儿童数据。

## Verification

- Alembic 单 head、离线 SQL 和可用时的 PostgreSQL 前滚。
- 数学 Profile/Learning/Curriculum 回归。
- 语文 scorer golden tests、幂等重放、版本冲突、跨孩子/跨家庭授权测试。
- OpenAPI 解析与引用检查；Web/Flutter 学科设置和紧凑布局测试。
