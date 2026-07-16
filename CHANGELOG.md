# Changelog

本文件只记录用户可感知、运维可感知或兼容性相关的已发布变化，格式参考 Keep a Changelog，版本计划遵循 Semantic Versioning。

## [Unreleased]

尚无产品能力、部署或发布。

### Changed

- Flutter 孩子端新增有限启动过渡：真实首页和档案请求从首帧开始在动画后方并行初始化，1.2 秒后平滑进入学习桌；系统启用减少动态效果时直接跳过动画。
- Compose 的 ImageAnalysis worker 进入默认 profile；NewAPI 关闭时 worker 保持空闲，不读取图片或创建 Provider 客户端。API Dockerfile 改为按目标架构原生构建：Linux amd64 继续包含锁定 Paddle OCR 和模型，Linux ARM64 提供不含 Paddle 的 API/NewAPI 调试镜像；macOS ARM64 原生 Python 仍保留 Paddle 依赖。
- 新增单家庭自托管 Docker Compose 部署：PostgreSQL/Redis/MinIO 持久卷、Alembic 一次性迁移、FastAPI API、Next.js 家长 Web 和 NewAPI ImageAnalysis worker；API 镜像现在包含迁移文件和 worker 脚本，Compose 从同目录 `infra/compose/.env` 自动注入变量。部署变量、Web Bearer token、NewAPI 外部地址、启动/升级/回滚步骤见 `infra/compose/README.md`。这不代表题目人工确认、脱敏副本清理、备份恢复或真实 NewAPI 联调已完成。
- 项目 Owner 接受 ADR-0015/0016：Capture 目标路线调整为原图留在家庭边界，本地 PrivacySanitizer 使用 OCR/规则/轻量视觉只做不可逆脱敏，用户确认后由自用 NewAPI 兼容 Provider 结构化解析，题目再次人工确认后才进入 Tutor；自用 Bearer 令牌作为方便认证方式。ADR-0012 的本地完整 OCR 默认路线已被替代并保留为回滚实现。
- 项目 Owner 此前接受 ADR-0010～0012：本地 MinIO 私有对象存储/短期预签名上传、Capture 图片默认保留与级联删除、本地 PaddleOCR 与默认外部 OCR 成本 0 元。其中 ADR-0012 现作为已实现旧路线和迁移历史保留，不再是目标默认解析路由。
- 锁定 API 服务端 boto3 `1.43.46`、Pillow `12.3.0`、PaddleOCR `3.7.0` 与 CPU PaddlePaddle `3.3.1`；新增私有 MinIO 预签名 Adapter、`0.5.0` Capture 上传签发/服务端确认路径、`0003`/`0004` 保留字段与过期清理器、`0005` OCR 候选结果事务持久化、家长保存/立即删除图片入口、按 Household/Child 边界的 Capture 对象级联删除编排、local/CI 家长删除顺序与幂等入口、构建期模型归档 SHA-256 校验、拒绝自动下载模型的 PaddleOCR Adapter、OCR 前置对象有界读取/图片容器头校验/完整像素解码/无 EXIF 规范化重编码、文本结果纯解析、临时文件执行边界和无网络 synthetic 真实模型烟测。Ubuntu 原生基准/真实题型评测、生产 Profile/派生对象/备份级联仍未完成。
- 新增仅使用仓库合成样本的 `ocr-synthetic-v1` 固定评测入口；6 个 OCR 信任边界 cases 通过，明确不调用 Provider、网络或图片文件。Tutor/提示层级评测仍未实现。
- 新增 `LocalOcrJob` 安全 Worker 边界，串联已确认 Capture 的有界对象读取、图片规范化、本地 OCR Adapter 与结果仓储；失败路径不持久化原始 Provider 响应。Redis/外部 Worker 和 Ubuntu 原生模型基准仍未实现。
- OCR Worker 失败现在将 Capture 转入从失败时起最多 7 天的 `ocr_failure` 保留策略；重复失败不延长期限，清理与审计边界保持不变。
- 新增 local/CI child-only 幂等 OCR 入队端点和单次 Dispatcher；任务失败只保留稳定错误码，不保存 Provider 错误详情。
- 新增 `0006_ocr_job_ledger` PostgreSQL 持久化队列；按 Household/Capture/幂等键去重，使用行锁领取任务，stale lease 可恢复，失败仅保存稳定错误码。
- 新增 ADR-0015 的 Provider-neutral PrivacySanitizer 核心与 JSON Schema：本地元数据清除、敏感区域实色覆盖、不可逆重编码、低置信度/无法安全遮挡阻断，以及 6-case synthetic 脱敏评测；新增 OCR/规则敏感区域信号和 Flutter 本地脱敏预览/手动涂抹，确认后只生成并上传脱敏 PNG。
- Capture 上传确认现在会读取私有对象并核验实际 SHA-256 与声明哈希一致，避免确认错误或被替换的脱敏副本。
- 新增 `0008_image_analysis_job`/`0009_question_extraction`、ImageAnalysis queued/blocked API、未确认提取读取合同和 PostgreSQL 可恢复 worker；仅在 NewAPI 显式启用时排队，Provider 失败只保存稳定错误码，提取结果不会自动进入 Tutor。
- Web/Flutter 支持从服务端或 `--dart-define=STUDY_API_TOKEN` 注入自用 Bearer 令牌；默认仍是 local demo headers。
- 新增 Provider-free `offline-tutor-policy.v1` 与 `tutor-hint.v1`：仅消费人工确认题目的结构字段，提供 1～3 级提示，响应强制不含直接答案且成本为 0 元；新增 3-case synthetic eval。云 Tutor Provider 和 TutorTurn 持久化仍未接入。
- Web/PWA 家长工作台从空壳升级为简洁明亮的学习概览，读取现有 Household-scoped children/tasks/devices API，断开 API 时显示安全空状态；认证仍未实现。
- 新增一次性本地 `run_ocr_worker.py` 入口；仅使用带构建期 SHA-256 标记的本地模型、PostgreSQL 和 MinIO，CLI 不输出配置或 Provider 详情。
- 新增 child-only OCR 结果读取合同与路由；服务端再次校验 Household、绑定 Child 和 Capture，候选文本保持人工确认状态，不升级为已验证学习事实。
- 新增 child-only OCR 候选确认接口；服务端只接受候选 ID，按 Household/Child/Capture 重新校验后复用 CaptureCorrection 追加写与版本幂等，原始 OCR 结果保持不可变。
- 新增 Flutter 孩子端第 1/2 张横屏 UI 原型：学习桌、OCR 候选照片/文本查看、编辑和确认流程；仅使用合成视觉资产，真实相机/认证/SQLite 未接入。
- iOS 孩子端锁定横屏方向，已在实体 iPad 上通过 Flutter tooling 构建、安装并启动；截图能力仍待 Xcode 设备查看器或手动截图。
- 新增第 3 张 Flutter 思考提示原型：分数算式、思考阶段、两级提示、“我想到了”和暂时跳过交互；6 项 Flutter 测试通过。
- 新增 Flutter 拍题输入页：通过 `image_picker 1.2.3` 支持一次性拍照、相册选择和合成示例题目入口；iOS 已声明相机/相册权限，所选本地图片进入人工 OCR 确认页，但尚未接入 MinIO 签名上传或真实 OCR 入队。
- 新增 Flutter `CaptureApiClient`：锁定 Dart `crypto 3.0.7`，完成 JPEG/PNG SHA-256、短期预签名 PUT、服务端上传确认和幂等 OCR 入队适配；真实设备接线仍要求有效 StudySession 与 iPad 可达的 MinIO 地址。
- 新增 local-only `STUDY_CAPTURE_SESSION_ID` 调试开关：提供有效合成会话时，拍题页执行真实私有上传和 OCR 入队，并显示等待状态；未提供时继续使用本地人工确认演示流。
- 新增 child-only OCR Job 状态读取接口与 Flutter 客户端状态解析；只返回稳定生命周期字段和 `result_id`，Provider 错误、图片、对象键和 OCR 原文仍不进入状态接口。
- Flutter OCR 确认页新增有界 Job 轮询、候选读取和人工确认/纠正；候选返回前保持等待，候选确认与纠正均沿用服务端版本和幂等边界。Flutter 客户端测试增至 9 项。
- 新增显式 local durable mode：API 的 Learning/Capture、OCR Job 和 OCR 结果仓储可统一切换至 PostgreSQL；本地 OCR Worker 增加可选 `--watch` 轮询模式，默认一次性执行保持不变。
- 新增 PostgreSQL/MinIO synthetic API + Worker 闭环回归，覆盖签名上传、Job Ledger、`LocalOcrJob`、候选结果持久化和 child-only 读取；测试使用 synthetic Provider，结束后删除对象。
- 新增 Ubuntu 24.04 CPU 真实 OCR 运行时只读预检，验证平台、Python/Paddle 版本和构建期模型完整性；当前 macOS 环境只允许返回阻塞状态，不启动真实推理。
- 新增 `ocr-model-synthetic-v1` 锁定模型 smoke runner；只生成内存 synthetic 数学题图并输出状态/延迟聚合，真实模型推理仍要求 Ubuntu 24.04 CPU 预检通过。
- 优化本地 PaddleOCR Adapter：同一 Worker 进程内文本/公式引擎按需初始化并复用，同时在复用前继续校验构建期模型完整性，减少重复加载模型的启动开销。
- 新增按需公式 OCR 执行与安全解析：使用 `PP-FormulaNet_plus-M` 的 `rec_formula` 结果仍以低置信度候选进入人工确认；锁定模型 synthetic smoke fixture 已加入公式 case，但真实推理仍需 Ubuntu 24.04 CPU 预检通过。
- 新增 OCR mode 贯穿入队到 Worker：旧客户端默认普通 text OCR，显式 `formula` 才调用公式模型；PostgreSQL Job Ledger 以 `0007_ocr_job_mode` 持久化模式，并拒绝同一幂等键切换模式。Flutter Capture 客户端同步支持可选 formula 请求。

版本号、远程仓库和比较链接将在首次发布流程中建立。
