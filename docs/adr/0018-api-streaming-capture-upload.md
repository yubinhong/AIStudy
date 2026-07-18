# ADR-0018：Capture 图片经 API 流式上传到私有 MinIO

- 状态：`Accepted`
- 日期：`2026-07-17`
- Owner：`项目 Owner（用户）`
- 决策者：`项目 Owner（用户；2026-07-17 对话确认）`
- 关联：`TASK-0009`、`PLAN-0012`、`TODO-014`、`ADR-0006`、`ADR-0011`、`ADR-0015`
- 替代/被替代：替代 `ADR-0010` 和 `ADR-0014` 的客户端预签名直传决策；继承私有 MinIO、S3 兼容 Adapter、随机对象键、生命周期和客户端无存储密钥等仍有效边界

## Context

当前 `0.8.0` 实现由 API 创建 `upload_pending` Capture 并返回 300 秒预签名 PUT URL，Flutter 直接连接家庭局域网暴露的 MinIO `9000` 上传图片，再调用独立确认端点。客户端不持有 MinIO 长期密钥，API 也会在确认时校验对象 MIME、大小和 SHA-256；但是对象存储端口和临时 Bearer URL 仍暴露给客户端，上传阶段绕过应用层会话鉴权、统一限速和请求审计，并额外要求 `OBJECT_STORAGE_PUBLIC_ENDPOINT_URL` 与真机可达的 MinIO 网络配置。

本项目是单家庭、单图最多 8 MB 的自托管应用。项目 Owner 明确要求客户端只连接 API，由 API 在验证可撤销 Session、Household、角色和孩子绑定后，以有界流式方式把图片写入只在服务端网络可达的私有 MinIO。当前代码、OpenAPI 和 Ubuntu 部署仍是预签名直传事实，必须通过后续实现任务迁移，不能因本 ADR 已接受而描述为已经完成。

## Decision Drivers

- MinIO 不应成为移动端或家庭局域网客户端可直接访问的应用入口。
- Restricted 图片上传必须与账号 Session、Household、孩子绑定、限速、幂等和审计处于同一 API 信任边界。
- API 不得把最多 8 MB 图片无界读入内存，也不得在验证失败或客户端断开后遗留不可追踪对象。
- 客户端合同不应包含对象存储 URL、对象键、存储凭据或 MinIO 专属行为。
- 私有 Bucket、S3 兼容 Adapter、随机对象键、生命周期清理和 Provider 不接收 MinIO URL 的既有边界必须保留。

## Considered Options

1. 保留 300 秒预签名 PUT 直传并加强 TLS、CORS 和 MinIO 网络策略：吞吐效率高，但仍要求客户端直接访问对象存储并持有临时上传能力。
2. API 一次性读取完整请求体后调用 MinIO：网络拓扑简单，但会扩大并发内存、请求体炸弹和进程耗尽风险。
3. App 携带 Session 向 API 上传，API 做有界流式校验并通过内部 S3 Adapter 流式写入私有 MinIO：统一信任边界，同时以背压、大小上限和临时对象清理控制资源风险。

## Decision

选择选项 3，并采用以下强制边界。

### 1. 客户端与公开 API

- App 只向 API 基础地址发起上传，请求必须携带当前可撤销 Session、`Idempotency-Key` 和版本化 Capture 元数据。
- 目标 OpenAPI 将现有“申请上传 → 客户端 PUT MinIO → 确认上传”合并为一个受鉴权上传操作。目标请求使用受限 `multipart/form-data` 或等价的单文件流式合同，响应直接返回已经完成对象校验的 `Capture`。
- 目标合同不得返回 `upload_url`、`upload_expires_at`、对象键、MinIO 地址或存储凭据；删除 `CaptureUpload`、`ConfirmCaptureUploadRequest` 以及独立上传确认端点。
- Flutter 不再解析或访问 MinIO URL，只处理 API 的上传进度、已确认 Capture 和稳定错误码；客户端仍可在上传前计算 SHA-256 用于幂等与用户确认绑定，但服务端必须独立增量计算并以自身结果为准。

### 2. API 流式与资源边界

- API 在读取图片字节前验证 Session、Household、角色、ChildProfile、StudySession、幂等键和声明媒体类型。
- API 必须以固定上限的块读取请求，并设置请求总时长、空闲超时、并发上限和背压；禁止 `await request.body()`、无界 `bytes` 聚合或等价的完整内存缓冲。
- 声明 `Content-Length` 时必须在读取前拒绝 0 字节或超过 8 MB；缺失或使用 chunked 传输时仍须按实际累计字节在第一个超限块立即中止。代理层限制不能替代应用层计数。
- API 在流式读取过程中增量计算 SHA-256，并尽早校验 JPEG/PNG 文件头和声明 MIME。完整接收后还必须通过有界解码校验格式、宽高、总像素数和截断/损坏；客户端声明与服务端计算不一致时拒绝。
- 图片流写入随机、不含儿童身份的 staging 对象。校验、持久化 Capture 元数据和对象状态全部成功后才将其视为已确认 Capture；鉴权失败、大小/类型/哈希/像素失败、超时、客户端断开、MinIO 错误或数据库事务失败时必须中止 multipart upload 或删除 staging 对象。
- 实现优先复用已锁定的 FastAPI/Starlette、Pillow 和 boto3/S3 Adapter。若底层 SDK 不能同时满足背压、取消和有界内存，新增依赖前必须按仓库供应链规则单独评审。

### 3. MinIO 与部署拓扑

- MinIO Bucket 保持私有，只允许 API、ImageAnalysis worker、DataLifecycle worker、备份/恢复作业通过 Compose 内部地址访问。
- Compose 目标配置不再向宿主机或家庭局域网发布 MinIO API `9000`；客户端不能解析或连接 `minio:9000`。如运维确需 Console，必须单独限制到服务器本机或受信管理网络，不能由 App 使用。
- 删除 `OBJECT_STORAGE_PUBLIC_ENDPOINT_URL`、`MINIO_API_PORT` 和预签名上传 TTL 等仅服务于客户端直传的运行配置。服务端内部 `OBJECT_STORAGE_ENDPOINT_URL=http://minio:9000` 和 MinIO 凭据继续只存在于服务端配置。

### 4. 幂等、审计与生命周期

- 同一账号、StudySession、操作和 `Idempotency-Key` 的等价重试返回同一已确认 Capture；同键不同服务端 SHA-256、大小或媒体类型返回冲突，不覆盖既有对象。
- 审计只记录稳定事件名、Household/Capture/actor 不可逆标识、声明与实际大小、媒体类型、哈希指纹、耗时和结果码；不记录图片、对象键、MinIO URL、会话或完整题目。
- 既有 ADR-0011 的 24 小时/7 天/30 天保留、家长控制、孩子删除级联以及临时脱敏副本删除规则继续有效。

## Consequences

### Positive

- 移动端只连接 API，MinIO API 不再暴露给局域网，客户端合同不含临时对象存储能力。
- Session、Household、孩子绑定、大小/类型/像素/哈希、限速、幂等和审计统一在服务端执行。
- 部署不再需要维护真机可达的 MinIO 主机名、端口、TLS/CORS 或预签名 URL 生命周期。

### Negative / Trade-offs

- API 承担全部上传带宽、连接时间和背压管理；反向代理、Uvicorn worker 数和超时必须按最大 8 MB 请求进行容量验证。
- S3 流式写入与数据库事务不能形成单一原子事务，需要 staging 对象、失败补偿和生命周期清理保证最终一致性。
- 这是公开 Capture 合同和 Flutter 客户端的破坏性迁移；当前 `0.8.0` App/API 不能与收缩后的合同混用。

### Risks and Mitigations

- 风险：慢速上传或并发请求耗尽 API worker；缓解：连接/空闲超时、并发配额、每账号限速、背压和反向代理请求限制。
- 风险：声明长度缺失或伪造导致超限；缓解：始终按实际块累计，超过 8 MB 立即中止并清理 staging/multipart。
- 风险：伪造 MIME、图片炸弹或截断文件；缓解：文件头、Pillow 有界完整解码、宽高/像素上限和损坏检测全部由服务端执行。
- 风险：客户端断开或 MinIO/数据库部分失败遗留对象；缓解：可取消 multipart、随机 staging 前缀、失败即时删除和 DataLifecycle worker 兜底清理。

## Compatibility and Migration

- 兼容性：这是项目 Owner 批准的破坏性预发布合同收敛。当前 OpenAPI/API `0.8.0`、Flutter 和 Ubuntu Compose 仍使用预签名直传；实现完成前不得移除运行配置或关闭 `9000`，否则当前真机上传会失败。
- 迁移步骤：
  1. 在 OpenAPI 的下一预发布版本定义单一 Session 鉴权流式上传操作和稳定错误响应，并删除公开 `upload_url`/确认合同。
  2. 为对象存储 Adapter 增加可取消的有界流式写入/staging 清理能力，先以 synthetic 流覆盖超限、断连、哈希、解码、MinIO/数据库失败。
  3. API 实现新合同并完成授权、幂等、限速、审计和失败补偿；迁移窗口内只在测试环境保留旧端点，不向新 OpenAPI 暴露。
  4. Flutter 切换为只向 API 上传并通过弱网/重试/进程终止测试；随后删除预签名解析和 MinIO 网络错误分支。
  5. 同步部署 API/App 后删除旧端点、`OBJECT_STORAGE_PUBLIC_ENDPOINT_URL`/`MINIO_API_PORT`/TTL 配置，取消 Compose `9000` 宿主机映射，再执行真机和日志/端口验收。
- 回滚：迁移前保留上一套匹配的 API/App 镜像。新链路异常时可整体回滚到上一版本并在隔离的受信 LAN 临时恢复 `9000` 和旧配置；不得只回滚一端、公开 Bucket、把 MinIO 密钥下发客户端或删除已确认 Capture。修复稳定后重新关闭直传入口。

## Validation

- OpenAPI 解析和差异检查证明响应及 Schema 中不存在 `upload_url`、`upload_expires_at`、`CaptureUpload`、`ConfirmCaptureUploadRequest` 和独立确认端点。
- API 单元/集成覆盖：无/失效 Session、角色/Household/孩子反向越权、0 字节、超过 8 MB、伪造/不一致 MIME、错误文件头、维度/像素炸弹、截断图片、声明/实际 SHA-256 不一致、同键重放/冲突、慢速/中断、MinIO/数据库失败及 staging 清理。
- 资源测试证明在最大允许图片和并发场景下内存使用受块大小/并发上限约束，不随请求体总大小线性无界增长。
- Flutter 测试证明所有图片字节只发送到配置的 API 地址；App 代码、日志、SQLite 和错误中没有 MinIO URL、对象键或存储凭据。
- Compose 展开和端口扫描证明宿主/LAN 未发布 `9000`，配置中不存在 `OBJECT_STORAGE_PUBLIC_ENDPOINT_URL` 和 `MINIO_API_PORT`，API/worker 仍可通过内部网络读写私有 Bucket。
- 使用 synthetic 图片完成 `App/API upload → confirmed Capture → ImageAnalysis → Extraction → VerifiedQuestion`；真实设备最终验收不得读取、输出或留存真实题目内容。
