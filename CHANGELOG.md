# Changelog

本文件只记录用户可感知、运维可感知或兼容性相关的已发布变化，格式参考 Keep a Changelog，版本计划遵循 Semantic Versioning。

## [Unreleased]

尚无产品能力、部署或发布。

### Changed

- 项目 Owner 接受 ADR-0010～0012：本地 MinIO 私有对象存储/短期预签名上传、Capture 图片默认保留与级联删除、本地 PaddleOCR 与默认外部 OCR 成本 0 元。真实儿童数据接入仍未完成。
- 锁定 API 服务端 boto3 `1.43.46`、Pillow `12.3.0`、PaddleOCR `3.7.0` 与 CPU PaddlePaddle `3.3.1`；新增私有 MinIO 预签名 Adapter、`0.5.0` Capture 上传签发/服务端确认路径、`0003`/`0004` 保留字段与过期清理器、`0005` OCR 候选结果事务持久化、家长保存/立即删除图片入口、按 Household/Child 边界的 Capture 对象级联删除编排、local/CI 家长删除顺序与幂等入口、构建期模型归档 SHA-256 校验、拒绝自动下载模型的 PaddleOCR Adapter、OCR 前置对象有界读取/图片容器头校验/完整像素解码/无 EXIF 规范化重编码、文本结果纯解析、临时文件执行边界和无网络 synthetic 真实模型烟测。Ubuntu 原生基准/真实题型评测、生产 Profile/派生对象/备份级联仍未完成。
- 新增仅使用仓库合成样本的 `ocr-synthetic-v1` 固定评测入口；6 个 OCR 信任边界 cases 通过，明确不调用 Provider、网络或图片文件。Tutor/提示层级评测仍未实现。
- 新增 `LocalOcrJob` 安全 Worker 边界，串联已确认 Capture 的有界对象读取、图片规范化、本地 OCR Adapter 与结果仓储；失败路径不持久化原始 Provider 响应。真实调度器和 Ubuntu 原生模型基准仍未实现。
- OCR Worker 失败现在将 Capture 转入从失败时起最多 7 天的 `ocr_failure` 保留策略；重复失败不延长期限，清理与审计边界保持不变。

版本号、远程仓库和比较链接将在首次发布流程中建立。
