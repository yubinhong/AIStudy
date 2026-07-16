# ADR-0016：自用部署的 Bearer 家庭令牌与 NewAPI 兼容 Provider

- 状态：`Accepted`
- 日期：`2026-07-15`
- Owner：项目 Owner
- 关联：`TASK-0006`、`TODO-008`、`TODO-009`
- 替代记录：`2026-07-15`，HMAC 家庭 Bearer 认证部分被 ADR-0017 的本地账号密码/可撤销会话替代；NewAPI Provider Adapter、默认关闭和脱敏图片边界继续有效。

## Context

产品当前以家庭自用、自部署为主。需要一个不依赖第三方身份服务的可用认证方式，并为项目 Owner 自行部署的 NewAPI 网关保留 Provider Adapter。该决定不改变 ADR-0015：原图不得外发，只有客户端确认的不可逆脱敏副本可以进入 Provider 边界；题目结构必须人工确认后才能进入 Tutor。

## Decision

1. API 增加 HMAC-SHA256 签名的短期 Bearer 家庭令牌，令牌只包含版本、Household、角色、可选 Child、签发时间和过期时间，不包含姓名、图片、题目或学习记录。`STUDY_AUTH_MODE=bearer` 时拒绝 synthetic demo headers；默认代码测试仍可使用 demo mode。
2. 令牌由本地脚本签发，密钥只通过 `STUDY_AUTH_SECRET` 注入，不进入客户端代码、仓库或日志。该方案是自用部署认证，不宣称替代 OIDC/企业身份平台。
3. NewAPI 通过 Provider-neutral OpenAI-compatible HTTP Adapter 接入，服务端配置 base URL、API key、视觉模型、超时和响应上限。业务代码不依赖 NewAPI 专属 SDK 或响应类型。
4. Adapter 默认关闭；启用后只接受已经确认且哈希绑定的 JPEG/PNG 脱敏副本，要求 Provider 返回 `question-extraction.v1`，失败只产生稳定错误，不记录原始 Provider 响应。当前 ImageAnalysis ledger 仍以人工确认和安全生命周期为准，Provider 不能绕过人工确认。

## Consequences

- 自用部署不需要额外 IdP 或客户端密钥；撤销单个令牌前需要轮换 `STUDY_AUTH_SECRET`，因此该方案不适合多用户生产 SaaS。
- NewAPI 可替换为任何兼容 `/v1/chat/completions` 的自托管网关；模型、URL 和 key 可独立更换。
- 当前代码只实现认证与 Adapter 边界；真实 Provider 调用、脱敏副本生命周期、监控和生产部署仍需在本地 NewAPI 就绪后单独验证。

## Rollback

将 `STUDY_AUTH_MODE=demo` 恢复为 local/CI synthetic headers，并保持 `STUDY_NEWAPI_ENABLED=false`；不需要数据迁移。

认证迁移开始后，回滚边界改由 ADR-0017 管理；不得再把本节的 HMAC Token 作为长期自用目标认证。
