# DECISIONS.md

> 决策索引。完整决策使用 `docs/adr/NNNN-title.md`；项目 Owner（用户）已于 2026-07-13 批准 ADR-0001～0008 执行。每份 ADR 内保留的真实数据、Provider、法域和生产前置条件仍然有效。

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
| [ADR-0004](docs/adr/0004-ai-provider-adapter-tutor-policy-and-evals.md) | Provider Adapter、Tutor Policy、评测 | Provider、条款、预算和阈值仍是接入前阻塞项 |
| [ADR-0005](docs/adr/0005-parent-child-identity-and-household-authorization.md) | 家长/孩子身份与 Household 授权 | IdP、TTL、MFA/恢复须在真实认证前确定 |
| [ADR-0006](docs/adr/0006-child-data-media-and-backup-lifecycle.md) | 儿童数据、媒体与备份生命周期 | 法域、同意、保留、备份与 Provider 条款仍阻塞真实儿童数据 |
| [ADR-0007](docs/adr/0007-toolchain-and-scaffold-baseline.md) | 工具链与骨架基线 | 变更须同步锁文件、验证和 ADR |
| [ADR-0008](docs/adr/0008-deployment-observability-and-recovery.md) | 部署、可观测性与恢复 | 平台、SLO/RPO/RTO、值班与 Secret Manager 仍阻塞 staging |
| [ADR-0009](docs/adr/0009-postgresql-persistence-and-migrations.md) | PostgreSQL 持久化与版本化迁移依赖 | 仅限 local synthetic 环境；真实数据与 production 前置条件仍有效 |

## Proposed ADR

暂无。

## 已废弃/被替代决策

暂无。

## ADR 创建规则

1. 从 `docs/adr/0000-template.md` 复制为下一个连续编号和英文 kebab-case 文件名。
2. 至少记录 Context、Drivers、三个或明确不足三个的选项、Decision、Consequences、兼容/迁移/回滚和验证。
3. 状态从 Proposed 经具名决策者批准后才能改为 Accepted；同步本索引和受影响主文档。
4. 新 ADR 替代设计稿中的内容时，在本索引和原主文档标明替代关系，不静默覆盖历史。
