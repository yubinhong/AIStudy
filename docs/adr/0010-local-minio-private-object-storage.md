# ADR-0010：本地 MinIO 私有对象存储与预签名上传

- 状态：`Accepted`
- 日期：`2026-07-13`
- Owner：`项目 Owner（用户）`
- 决策者：`项目 Owner（用户；2026-07-13 对话确认）`
- 关联：`TASK-0006`、`TODO-008`、`ADR-0006`
- 替代/被替代：`无`
- 批准记录：项目 Owner 明确选择本地 MinIO、S3 兼容 Adapter、私有 Bucket 与短期预签名上传；客户端不得持有存储密钥。

## Context

Capture 的真实图片需要脱离 API 进程保存，同时必须避免客户端长期持有对象存储凭据或公开读取。项目已经有 local-only MinIO Compose 服务，但尚未接入媒体上传。

## Decision Drivers

- 图片是 Restricted 数据，Bucket 必须默认私有且按 Household 隔离。
- Flutter/Web 客户端只应获得一次性、短时、受限对象键的上传能力。
- 本地开发不依赖任何云对象存储或外部图片传输。

## Considered Options

1. 由 API 接收并持久化全部图片字节：实现直接，但扩大 API 的大小、超时和敏感数据暴露面。
2. 公共 Bucket + 客户端静态密钥：接入快，但不可接受地暴露儿童图片与密钥。
3. 本地 MinIO 私有 Bucket + S3 兼容 Adapter + 服务端生成短期预签名 PUT URL：隔离媒体传输与业务元数据，并保持未来 S3 兼容迁移能力。

## Decision

选择选项 3。local 环境使用 MinIO；对象存储通过内部 S3 兼容 Adapter 访问。Bucket 默认私有，对象键为不含儿童身份的随机值并按 Household/Capture 授权校验。

客户端 App 不保存、读取或传递 MinIO/S3 长期密钥。服务端仅从本地安全配置或后续 Secret Manager 读取其最小权限存储凭据，用于生成有界、短期、单对象的预签名上传 URL；精确 TTL、CORS 与对象大小限制在上传实现前写入配置和测试，不在本 ADR 中猜测数值。

S3 SDK 的具体 Python 包尚未加入依赖清单；实现时必须选择并锁定一个维护中的 SDK，记录许可证、替代方案、供应链风险和服务端体积影响，随后更新 `pyproject.toml`、`uv.lock`、测试与本 ADR。

## Consequences

### Positive

- 本地图片默认不离开家庭开发环境；未来可迁移至兼容 S3 的私有存储。
- 客户端不持有长期存储凭据，API 也不承载大文件字节流。

### Negative / Trade-offs

- 需要维护预签名 URL、对象键、上传完成确认、过期清理和 CORS/权限测试。
- 服务端仍需要最小权限凭据；生产 Secret Manager 与轮换尚未确定。

## Compatibility and Migration

- 当前 `0.4.0` Capture 合同不包含上传 URL 或对象键，后续只能以向后兼容字段/端点增量扩展。
- 本地 MinIO 不等同于 staging/production 存储批准；云迁移须保持 S3 Adapter 接口并另行验证。
- 回滚时关闭新的预签名签发入口，保留已存在的 Capture 元数据/删除计划；不得公开 Bucket 或把密钥下发给客户端。

## Validation

- 使用 synthetic 图片验证私有 Bucket、预签名有效期、单对象范围、类型/大小、跨 Household 拒绝和上传失败恢复。
- 验证日志、错误和审计不包含存储密钥、预签名 URL、对象键或原始图片。

