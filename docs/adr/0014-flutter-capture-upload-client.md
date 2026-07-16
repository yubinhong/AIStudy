# ADR-0014：Flutter Capture 上传客户端使用 HttpClient 与 crypto

- 状态：`Accepted for P1 local/CI implementation`
- 日期：`2026-07-14`
- Owner：`项目 Owner（用户）`
- 关联：`TASK-0006`、`TODO-008`、`ADR-0002`、`ADR-0010`、`ADR-0012（已被替代）`、`ADR-0013`、`ADR-0015`

## Context

Flutter 已能取得本地题目图片，但还没有把图片提交到现有 Capture API 的客户端边界。服务端合同要求客户端提交 JPEG/PNG 的大小和 SHA-256 声明，再使用短期预签名 URL 上传、服务端确认并幂等入队本地 OCR。

## Decision

- 使用 Dart SDK 的 `dart:io HttpClient` 实现 local/CI API 请求和预签名 PUT；不新增 HTTP SDK，避免在客户端重复维护 Provider 或对象存储响应模型。
- 使用 Dart 官方发布者 `dart.dev` 的 `crypto: 3.0.7` 计算 SHA-256；该包只提供哈希/HMAC 实现，BSD-3-Clause，依赖仅为 `typed_data`。
- `CaptureApiClient` 只接受本地 `XFile`，限制 8 MB、识别 JPEG/PNG 容器头，不记录图片、签名 URL、对象键或 OCR 文本。
- 上传、确认和 OCR 入队使用稳定幂等键；预签名 URL 只存在于单次调用内，不写入本地数据库或日志。
- Job 状态和 OCR 候选使用 child-only GET 接口按有限时长轮询；只把候选文本暂存于当前确认页，结果必须由孩子人工确认或纠正后才继续，不写入端侧事实库。
- 候选确认和手工纠正复用服务端 Capture 版本与幂等边界；客户端不接受 Provider 原始响应、对象键或错误详情。
- 当前客户端只在提供 local 调试 `session_id` 时启用；生产认证、任务/会话同步和 SDK 生成仍沿既有 ADR 边界推进。

## Alternatives and risks

- `package:http`：API 更简洁，但新增依赖和流式上传抽象对当前单一客户端边界没有必要。
- 平台原生 CommonCrypto/Java：减少 Dart 包，但引入双平台 MethodChannel 代码和额外安全维护面。
- 风险：预签名 URL 必须是 iPad 可达的 MinIO 地址；若服务端返回 `127.0.0.1`，客户端应失败并提示网络配置问题，不改写或暴露 URL。

## Compatibility and rollback

- 仅新增客户端适配器和 `crypto` 锁定依赖，不改变服务端 Capture 合同。
- ADR-0015 不改变本 ADR 的本地文件校验、SHA-256、预签名上传和幂等边界；后续必须以兼容增量新增脱敏状态、脱敏副本哈希确认、ImageAnalysis Job 和题目确认，不能把现有 OCR Job/结果字段静默解释成云视觉流程。
- 可移除适配器、依赖和调试入口，恢复本地人工确认页；不会影响服务端对象生命周期或 OCR Worker。

## Validation

- SHA-256、JPEG/PNG 边界、请求顺序、签名 PUT、Job 轮询、候选读取、确认/纠正幂等键和服务端错误均由 Flutter 单元测试覆盖。
- 实体 iPad 已使用合成 StudySession 和 iPad 可达的 local MinIO 完成上传/确认/入队 smoke；当前 InMemory OCR 队列尚未为该调试进程产生可读取的 succeeded 结果。
