# ADR-0013：Flutter 拍题输入使用官方 image_picker

- 状态：`Accepted for P1 local/CI implementation`
- 日期：`2026-07-14`
- Owner：`项目 Owner（用户）`
- 关联：`TASK-0006`、`TODO-008`、`ADR-0010`、`ADR-0011`、`ADR-0012（已被替代）`、`ADR-0015`

## Context

孩子端需要从 iPad/Android 的相机或相册选择题目图片，再进入已有的 OCR 候选人工确认流程。客户端目前只有合成图片 UI，没有平台输入能力；本轮不应直接把平台媒体 API、对象存储或 OCR Provider 形状扩散到页面代码。

## Decision

- 使用 Flutter 官方发布者 `flutter.dev` 的 `image_picker: 1.2.3`，提供单张相机拍摄和相册选择入口。
- 依赖许可证为 Apache-2.0/BSD-3-Clause；实现范围仅覆盖一次选一张图片，不启用视频、多选、编辑器或第三方上传 SDK。
- `CaptureInputScreen` 只负责取得本地 `XFile` 并将路径交给 OCR 确认页面；图片仍是本地临时输入，不写日志、不进入测试夹具、不发送外部 Provider。
- 图片选择回调不直接实现上传或 Provider 业务。历史 `0.8.0` 按 ADR-0010/0014 预签名直传；目标由 ADR-0018 改为 `CaptureApiClient` 携带 Session 只向 API 上传，API 有界流式写入私有 MinIO。OCR/ImageAnalysis 继续通过 API/Provider Adapter 边界接入。
- iOS 声明相机和照片库用途文案；Android 继续使用插件的系统相机/Photo Picker 适配，不新增自定义权限管理。

## Alternatives and risks

- `camera`：支持实时预览和取景框，但会增加相机生命周期、方向、权限、内存和客户端体积复杂度；当前单张拍题不需要。
- 原生 MethodChannel：减少 Dart 依赖但会复制 iOS/Android 平台代码，增加维护和安全边界，不采用。
- 供应链风险控制：锁定版本和 `pubspec.lock`，只使用官方发布者包；升级必须重新检查平台权限、许可证、SDK 支持和真实设备回归。

## Compatibility and rollback

- 现有 OCR 确认页保持可用；用户取消或平台选择失败时返回入口，不生成 Capture、不伪造 OCR 结果。
- ADR-0015 迁移后，图片选择页仍保持本 ADR 的平台边界，但下一页必须改为单题裁剪/脱敏预览、重新裁剪和手动涂抹；现有 OCR 候选页在兼容迁移前继续表示旧路线，不得冒充脱敏确认。
- 回滚方式是移除 `image_picker` 入口和平台用途声明，恢复合成图片确认路径；不影响服务端 Capture 合同和对象生命周期。

## Validation

- Flutter format、analyze、Widget 测试。
- iPad 实体设备相机权限、取消、拍摄后进入人工确认；相册选择和空/失败状态后续补充真实设备回归。
