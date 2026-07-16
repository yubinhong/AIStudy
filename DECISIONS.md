# DECISIONS.md

> 决策索引。完整决策使用 `docs/adr/NNNN-title.md`；项目 Owner（用户）已于 2026-07-13 批准 ADR-0001～0012、于 2026-07-14 批准 ADR-0013～0014，并于 2026-07-15 批准 ADR-0015～0017。ADR-0012 的默认本地完整 OCR 路线已被 ADR-0015 替代；ADR-0017 替代 ADR-0005 的 PIN/设备凭证默认认证方式和 ADR-0016 的 HMAC 家庭认证部分，ADR-0016 的 NewAPI 适配边界继续有效；每份 ADR 内保留的真实数据、法域和生产前置条件仍然有效。

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
| [ADR-0010](docs/adr/0010-local-minio-private-object-storage.md) | 本地 MinIO 私有对象存储与预签名上传；boto3 1.43.46、S3 兼容接口、不使用 MinIO 专属 SDK | TTL/CORS/大小限制和生产 Secret Manager 须在实现前锁定 |
| [ADR-0011](docs/adr/0011-capture-media-retention-and-cascade-deletion.md) | Capture 图片保留、家长控制与级联删除 | 法域、同意、备份擦除和真实数据告知仍阻塞 production |
| [ADR-0013](docs/adr/0013-flutter-capture-input.md) | Flutter 使用官方 `image_picker 1.2.3` 提供一次性相机/相册选择，图片先进入本地人工确认页 | 客户端签名上传、OCR 入队、真实设备权限回归仍须完成 |
| [ADR-0014](docs/adr/0014-flutter-capture-upload-client.md) | Flutter 使用 Dart `HttpClient` 和 `crypto 3.0.7` 完成 SHA-256、预签名上传、服务端确认和幂等 OCR 入队 | local MinIO 必须提供 iPad 可达的预签名地址；任务/会话同步与生产认证仍未接线 |
| [ADR-0015](docs/adr/0015-local-privacy-sanitization-and-cloud-vision-parsing.md) | 原图留在家庭边界，本地 OCR/规则/视觉只生成不可逆脱敏副本；用户确认后由单一获批云端视觉 Provider 结构化解析 | 本地脱敏回执、哈希门禁、Provider-neutral Schema 和可开关 worker 已实现；人工确认持久化、临时副本删除、实际 Provider 联调和固定视觉 eval 仍待完成 |
| [ADR-0016](docs/adr/0016-self-hosted-auth-and-newapi-provider.md) | HMAC 家庭认证与 NewAPI OpenAI-compatible Adapter | HMAC 认证已被 ADR-0017 替代；NewAPI 默认关闭、单 Provider、脱敏副本和 Adapter 边界继续有效 |
| [ADR-0017](docs/adr/0017-self-hosted-password-accounts-and-sessions.md) | 自用 PostgreSQL 账号密码、一次性默认管理员、家长创建孩子账号和可撤销会话 | 已批准并完成 API/Web/Flutter/Compose 代码切换；2026-07-16 批准删除全部 HMAC/Demo 运行时兼容，Flutter 改为登录前配置服务端地址；环境验收仍未全部完成 |

## Proposed ADR

暂无。

## 已废弃/被替代决策

| ADR | 原决策 | 替代关系与保留事实 |
| --- | --- | --- |
| [ADR-0012](docs/adr/0012-local-paddleocr-provider-and-zero-external-cost.md) | 本地 PaddleOCR 完整解析题目、人工确认、默认不外发图片 | `2026-07-15` 被 ADR-0015 替代；已实现的 OCR Job/结果/公式模式、模型供应链、评测和历史记录保持原义，迁移前不得冒充云端新路线 |

## ADR 创建规则

1. 从 `docs/adr/0000-template.md` 复制为下一个连续编号和英文 kebab-case 文件名。
2. 至少记录 Context、Drivers、三个或明确不足三个的选项、Decision、Consequences、兼容/迁移/回滚和验证。
3. 状态从 Proposed 经具名决策者批准后才能改为 Accepted；同步本索引和受影响主文档。
4. 新 ADR 替代设计稿中的内容时，在本索引和原主文档标明替代关系，不静默覆盖历史。
