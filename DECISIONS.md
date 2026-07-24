# DECISIONS.md

> 决策索引。完整决策使用 `docs/adr/NNNN-title.md`；项目 Owner（用户）已于 2026-07-13 批准 ADR-0001～0012、于 2026-07-14 批准 ADR-0013～0014、于 2026-07-15 批准 ADR-0015～0017、于 2026-07-17 批准 ADR-0018，并于 2026-07-18 批准 ADR-0020、于 2026-07-23 批准 ADR-0021～0023；ADR-0019 仍为 Proposed。ADR-0012 的默认本地完整 OCR 路线已被 ADR-0015 替代；ADR-0017 替代 ADR-0005 的 PIN/设备凭证默认认证方式和 ADR-0016 的 HMAC 家庭认证部分；ADR-0018 替代 ADR-0010/0014 的客户端预签名直传路线并继承其私有 MinIO/S3 Adapter 边界。

## 决策原则

以下情况需要 ADR：

- 跨模块/团队的系统边界变化，或从模块化单体拆服务。
- 核心数据模型、公开 API/OpenAPI/JSON Schema、离线同步或迁移策略变化。
- 身份授权、儿童数据、保留/删除、加密、部署拓扑或安全模型变化。
- 引入核心依赖、AI/OCR Provider、内容来源、推送/云服务或不可轻易撤销的技术选择。
- 接受重大成本、合规、可靠性、兼容性或长期技术债。

小范围、易逆转实现细节可记录在 `PLANS.md`；任何决策都不能把未经批准的目标设计描述为已实现。

## 已接受 ADR

| ADR | 决策 | 仍然有效的实施边界 |
| --- | --- | --- |
| [ADR-0001](docs/adr/0001-modular-monolith-and-domain-boundaries.md) | 模块化单体与领域边界 | 拆服务仍需独立证据与 ADR |
| [ADR-0002](docs/adr/0002-openapi-contract-and-sdk-generation.md) | OpenAPI、AI Schema 与 SDK 生成 | 首次 SDK 生成前须固定工具、输出目录和 CI 验证 |
| [ADR-0003](docs/adr/0003-offline-events-idempotency-and-conflict-merge.md) | 离线事件、幂等与冲突合并 | 实现合同须定义事件字段、兼容窗口和合并 UX |
| [ADR-0004](docs/adr/0004-ai-provider-adapter-tutor-policy-and-evals.md) | Provider Adapter、Tutor Policy、评测 | 默认图片解析路由见 ADR-0015；云 Provider、固定 eval、预算与数据条款仍须实现前审查 |
| [ADR-0005](docs/adr/0005-parent-child-identity-and-household-authorization.md) | 家长/孩子身份与 Household 授权 | Household/角色/逐资源授权继续有效；PIN/设备凭证默认认证已被 ADR-0017 替代 |
| [ADR-0006](docs/adr/0006-child-data-media-and-backup-lifecycle.md) | 儿童数据、媒体与备份生命周期 | 法域、同意、保留、备份与 Provider 条款仍阻塞真实儿童数据 |
| [ADR-0007](docs/adr/0007-toolchain-and-scaffold-baseline.md) | 工具链与骨架基线 | 变更须同步锁文件、验证和 ADR |
| [ADR-0008](docs/adr/0008-deployment-observability-and-recovery.md) | 部署、可观测性与恢复 | 平台、SLO/RPO/RTO、值班与 Secret Manager 仍阻塞 staging |
| [ADR-0009](docs/adr/0009-postgresql-persistence-and-migrations.md) | PostgreSQL 持久化与版本化迁移依赖 | 仅限 local synthetic 环境；真实数据与 production 前置条件仍有效 |
| [ADR-0011](docs/adr/0011-capture-media-retention-and-cascade-deletion.md) | Capture 图片保留、家长控制与级联删除 | 法域、同意、备份擦除和真实数据告知仍阻塞 production |
| [ADR-0013](docs/adr/0013-flutter-capture-input.md) | Flutter 使用官方 `image_picker 1.2.3` 提供一次性相机/相册选择，图片先进入本地人工确认页 | 输入边界继续有效；上传目标已改由 ADR-0018 规定的 API 流式接口，真实设备权限回归仍须完成 |
| [ADR-0015](docs/adr/0015-local-privacy-sanitization-and-cloud-vision-parsing.md) | 原图留在家庭边界，本地 OCR/规则/视觉只生成不可逆脱敏副本；用户确认后由单一获批云端视觉 Provider 结构化解析 | 本地脱敏回执、哈希门禁、Provider-neutral Schema 和可开关 worker 已实现；人工确认持久化、临时副本删除、实际 Provider 联调和固定视觉 eval 仍待完成 |
| [ADR-0016](docs/adr/0016-self-hosted-auth-and-newapi-provider.md) | HMAC 家庭认证与 NewAPI OpenAI-compatible Adapter | HMAC 认证已被 ADR-0017 替代；NewAPI 默认关闭、单 Provider、脱敏副本和 Adapter 边界继续有效 |
| [ADR-0017](docs/adr/0017-self-hosted-password-accounts-and-sessions.md) | 自用 PostgreSQL 账号密码、一次性默认管理员、家长创建孩子账号和可撤销会话 | 已批准并完成 API/Web/Flutter/Compose 代码切换；2026-07-16 批准删除全部 HMAC/Demo 运行时兼容，Flutter 改为登录前配置服务端地址；环境验收仍未全部完成 |
| [ADR-0018](docs/adr/0018-api-streaming-capture-upload.md) | App 只携带 Session 向 API 上传；API 有界流式校验并通过内部地址写入私有 MinIO | 已批准并已在本地/Ubuntu 流式链路实现；MinIO `9000` LAN 暴露已删除，最终断连/超限/真机回归仍待完成 |
| [ADR-0020](docs/adr/0020-curriculum-grounded-mistake-learning-loop.md) | 数学首科采用“教材范围 → 错题讲解 → 错题沉淀 → 到期复习 → 今日任务”主线 | 已批准并完成代码收口；closeout、ReviewAttempt、PDF 解析/grounding 和 Tutor 递进已实现，真实部署与发布门槛仍按 PLAN-0016 验收 |
| [ADR-0021](docs/adr/0021-local-curriculum-document-parsing-pipeline.md) | 首版教材只接受 PDF；本地有界解析 worker 生成页级草稿，家长发布后才用于 Tutor/推荐 | 已接受并实现 `pdfplumber==0.11.7`/`pdfminer-six==20250506`、0021～0023 迁移、解析 worker 和 Tutor 来源/递进字段；真实部署、扫描 PDF 与发布门槛仍有效 |
| [ADR-0022](docs/adr/0022-cloud-tutor-and-source-bound-recommendation-planning.md) | L1/L2 使用受约束云端 Tutor；推荐由本地全教材/错题分析后交给云端做来源受限的 7 日规划 | 只发送已确认题目和有界教材候选；模型只能选择服务端 source key，家长批准后才创建正式 Task |
| [ADR-0023](docs/adr/0023-multimodal-curriculum-knowledge-map.md) | 私有 PDF 渲染原页预览，NewAPI 分批多模态理解并形成可审核知识图谱，再结合错题规划任务 | 原 PDF/预览留在私有 MinIO；Provider 只收有界页批次，知识图谱与任务均须家长批准，模型不能伪造来源页或教材题 |

## Proposed ADR

| ADR | 提议 | 进入实施前条件 |
| --- | --- | --- |
| [ADR-0019](docs/adr/0019-child-management-aggregate-and-dashboard-scope.md) | Web/API 将档案与唯一孩子账号作为管理聚合，保持认证/档案分表；原子创建并按已授权当前孩子过滤工作台 | 项目 Owner 确认分表、事务、一对一约束和旧数据迁移细节；随后同步为 Accepted |

## 已废弃/被替代决策

| ADR | 原决策 | 替代关系与保留事实 |
| --- | --- | --- |
| [ADR-0010](docs/adr/0010-local-minio-private-object-storage.md) | 私有 MinIO + 客户端短期预签名 PUT | `2026-07-17` 被 ADR-0018 替代；私有 Bucket、S3 兼容 Adapter、随机对象键、客户端无长期密钥和历史实现事实继续有效 |
| [ADR-0012](docs/adr/0012-local-paddleocr-provider-and-zero-external-cost.md) | 本地 PaddleOCR 完整解析题目、人工确认、默认不外发图片 | `2026-07-15` 被 ADR-0015 替代；已实现的 OCR Job/结果/公式模式、模型供应链、评测和历史记录保持原义，迁移前不得冒充云端新路线 |
| [ADR-0014](docs/adr/0014-flutter-capture-upload-client.md) | Flutter 解析预签名 URL 并直连 MinIO PUT 后确认 | `2026-07-17` 被 ADR-0018 替代；Dart `HttpClient`/`crypto` 依赖和既有真机 smoke 仅作为历史事实，目标客户端只连接 API |

## ADR 创建规则

1. 从 `docs/adr/0000-template.md` 复制为下一个连续编号和英文 kebab-case 文件名。
2. 至少记录 Context、Drivers、三个或明确不足三个的选项、Decision、Consequences、兼容/迁移/回滚和验证。
3. 状态从 Proposed 经具名决策者批准后才能改为 Accepted；同步本索引和受影响主文档。
4. 新 ADR 替代设计稿中的内容时，在本索引和原主文档标明替代关系，不静默覆盖历史。
