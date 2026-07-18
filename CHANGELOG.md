# Changelog

本文件只记录用户可感知、运维可感知或兼容性相关的已发布变化，格式参考 Keep a Changelog，版本计划遵循 Semantic Versioning。

## [Unreleased]

尚无产品发布；已完成一次不含真实数据的 Ubuntu 自用 Compose 环境验收，当前运行迁移至 `0016_child_account_uniqueness`。

- 2026-07-18：完成 ADR-0018 流式拍题上传的 Ubuntu 成对部署。API/Flutter 只使用 Session 上传到 API，服务端通过 boto3 multipart 写入内部私有 MinIO，宿主/LAN 不暴露 `9000`；清理远端残留公开对象存储配置。真实 NewAPI synthetic 请求已到达 Provider，但返回 HTTP `402`，客户端现显示余额/模型额度的可操作提示。
- 2026-07-18：完成 PLAN-0013 首版孩子管理聚合。家长一次提交事务创建孩子档案和唯一绑定账号，支持聚合列表/编辑/删除、账号管理以及首页 `?child=` 选择和服务端任务过滤；新增 `0016_child_account_uniqueness`，浏览器 E2E 和双孩子设备回归仍待执行。

- 项目 Owner 接受 ADR-0018：Capture 上传改为 App 携带 Session 只访问 API，API 有界流式校验并通过内部地址写入私有 MinIO；OpenAPI 已删除 `upload_url`/独立确认，Compose 已删除 `OBJECT_STORAGE_PUBLIC_ENDPOINT_URL`/`MINIO_API_PORT` 并取消 LAN `9000`，Ubuntu 已完成成对部署。
- 项目 Owner 批准 PLAN-0013 的 Web 体验方向：创建孩子以一次事务同时创建档案和唯一绑定账号，管理页按每个孩子一张聚合卡呈现；家长首页增加当前孩子选择，并统一过滤问候、任务、档案和周报。`Account`/`ChildProfile` 仍按安全职责分表；首版代码和 Ubuntu 部署已完成，浏览器 E2E 仍待执行。
- 项目 Owner 接受 ADR-0020/PLAN-0014：数学首科主线调整为“家长发布年级/学期/教材知识范围 → 孩子选择错题讲解/复习错题/今日任务 → 错题证据与完整讲解 → 正式错题本/到期复习 → 家长可控任务建议”。拍题目标同时包含题目和孩子解答：有作答时针对首个可验证错步讲解，答题区确认空白时记录“没有思路”并从头讲解；未拍到答题区或不清不得自动当空白。系统建议默认须家长批准。TODO-016～019 已建立，但当前教材导入、三入口、MistakeRecord/ReviewSchedule 和 TaskRecommendation 均未实现或部署。

- P1 非实体设备核心闭环完成：OpenAPI `0.8.0`、迁移 `0013`～`0015` 新增服务端可信 VerifiedQuestion → TutorTurn、学习会话完成/复习状态、家长周报和 24 小时孩子数据导出快照；孩子删除会清理关联学习、Capture/OCR、视觉、Tutor 与导出数据。
- Flutter 首页改为读取真实任务和活动会话，拍题人工确认后进入真实 Tutor；待同步 Attempt 使用按服务端/账号隔离的 SQLite 队列，同日再次拍题不会复用已完成会话。家长 Web 可创建当天任务、查看周报并下载数据导出。
- Compose 新增数据生命周期 worker，以及 PostgreSQL custom dump + MinIO 快照备份和隔离恢复校验脚本。Ubuntu 已部署 API `0.8.0`/迁移 `0016`，新流式上传 synthetic 请求已到达 NewAPI；当前 Provider HTTP `402` 使 Extraction/人工确认/Tutor 的真实联调等待额度恢复，备份恢复校验通过。
- Android release APK 与 iOS release 无签名构建通过。实体设备最终相机/权限/弱网/横竖屏/重启回归和自动视觉检测器仍是明确未完成项；当前自动脱敏不得宣传为绝对匿名。

- TASK-0006 代码闭环完成：新增 QuestionExtraction 人工确认生成/读取 `VerifiedQuestion`、`0010_verified_question` 迁移，以及 ImageAnalysis 派生对象成功/失败清理。
- PLAN-0007 进入实现：新增 Argon2id 账号密码、`0011_account_password_session`、可撤销会话、首次改密、Web Cookie/CSRF、Flutter 安全存储登录、家长孩子账号管理和 Compose password 认证默认配置。
- TASK-0007 收敛认证面：删除 API HMAC/Demo Header、签发脚本、旧配置和 Web 免登录/静态 Token 回退；OpenAPI `0.6.0` 业务端点只允许 Cookie/Bearer Session，Web 受保护页统一要求登录。旧 HMAC/Demo 客户端不再兼容。
- Flutter 登录页新增服务端地址配置与持久化；地址需为受限 HTTP(S) 根 URL，变更地址会先清除旧服务端会话。登录、孩子档案和 Capture 共用该地址。
- 修复孩子初始账号登录后被误显示为“API 尚未连接”：Flutter 现在解析并恢复 `must_change_password`，提供首次设置新密码、会话轮换和安全存储流程；孩子档案列表/详情同时收敛为仅返回账号绑定档案。新 APK 已覆盖安装到华为 Nova 9，实机完成首次改密并读取学习桌；同时修复手机竖屏任务标题溢出。
- 认证生命周期已接入现有 `audit_events`：记录登录成功/失败/锁定/阻断、改密、再认证失败、登出和家长账号管理操作；审计不保存用户名、密码、哈希、令牌或 Cookie。
- 家长创建孩子账号不再将用户名写入 HTTP Header，支持中文用户名；页面自动绑定家庭孩子档案，多个档案可选择，无需手填 UUID。孩子档案现可新增、编辑和删除，Web 代理会以正确的 JSON Content-Type 转发新增与编辑请求，避免 API 返回 422。
- 新增 `0012_profile_persistence` 与 PostgreSQL ProfileRepository：孩子档案和设备登记不再随 API 重启丢失；新增/编辑/删除、设备登记均事务化写入幂等凭据和审计，孩子账号以同 Household 复合外键绑定档案并在档案删除时级联撤销。Ubuntu 已完成迁移前备份、前滚和重启持久化 synthetic smoke。
- 修复 PostgreSQL 孩子账号重复用户名被误报为 HTTP 500：仓储只将 `uq_accounts_household_username` 唯一约束转换为可处理的 409，其他数据库故障继续上抛；家长 Web 会提示管理现有账号或更换用户名。修复已部署 Ubuntu，现有账号和密码未被覆盖。
- 修复真机拍题只进入本地演示而未上传的问题：OpenAPI `0.7.0` 新增孩子绑定的幂等即时拍题会话，Flutter 不再依赖编译期 `STUDY_CAPTURE_SESSION_ID`；识别任务会轮询到 QuestionExtraction，并将人工修改持久化为 VerifiedQuestion。MinIO 内部读写与真机预签名地址已分离，Bucket 仍私有且 App 无密钥。
- 修复较大脱敏 PNG 调用 NewAPI 返回 HTTP 413：Provider Adapter 会对超过 600 KB 的已确认脱敏副本执行内存去元数据、等比缩放和有界 JPEG 重编码，再进行 base64 传输；不恢复遮挡像素、不落盘新副本。Nova 9 首次真实链路已到达 ImageAnalysis，原 3.09 MB 请求的 413 根因已确认并完成服务端前滚。
- NewAPI 早期已完成 synthetic `queued → Extraction`；本轮进一步完成大图压缩、远端人工确认、TutorTurn 和备份恢复。真实视觉检测器、浏览器 E2E 与完整 iPad 生命周期仍未执行。

### Changed

- 在用户提供的 Ubuntu 24.04 x86_64 VM 上完成 Compose 基础验收：Docker 29.1.3/Compose 2.40.3、PostgreSQL/Redis/MinIO/API/Web/migration/worker 健康，`0011` 前滚迁移、loopback bootstrap login、重启恢复和内存 synthetic OCR smoke 通过；NewAPI 保持关闭，未发送真实图片。为适配同步工作区的 macOS 元数据，API `.dockerignore` 现在排除所有层级的 Python 缓存、AppleDouble 和 `.DS_Store`，避免 Alembic 扫描非源码文件。
- OCR 运行时预检增加显式锁定容器模式：宿主仍要求 Ubuntu 24.04，amd64 发布镜像仅在 `STUDY_OCR_CONTAINER_RUNTIME=true` 且运行层为 Debian 13 时通过 OS 检查；Linux、x86_64、Python/Paddle 版本及构建期模型标记门禁不变。
- Ubuntu x86_64 锁定模型 synthetic smoke 已通过 4/4 cases（PP-OCRv6 medium 普通文本 3 cases、PP-FormulaNet_plus-M 公式 1 case），只产生人工确认候选，不调用外部 Provider。
- NewAPI Adapter 现在发送 `Accept: application/json` 和受限、可配置的 `STUDY_NEWAPI_USER_AGENT`（默认 `study-api/0.5`），并拒绝控制字符以防止请求头注入。该修复处理了 Cloudflare 对 Python 默认 `urllib` User-Agent 的 1010 拦截；2026-07-16 远端 synthetic 图片成功完成 `queued → Extraction`，结果保持 `needs_confirmation=true`，临时派生对象和 synthetic 数据库记录均已清理。

- Flutter 孩子端新增有限启动过渡：真实首页和档案请求从首帧开始在动画后方并行初始化，1.2 秒后平滑进入学习桌；系统启用减少动态效果时直接跳过动画。
- Compose 的 ImageAnalysis worker 进入默认 profile；NewAPI 关闭时 worker 保持空闲，不读取图片或创建 Provider 客户端。API Dockerfile 改为按目标架构原生构建：Linux amd64 继续包含锁定 Paddle OCR 和模型，Linux ARM64 提供不含 Paddle 的 API/NewAPI 调试镜像；macOS ARM64 原生 Python 仍保留 Paddle 依赖。
- 新增单家庭自托管 Docker Compose 部署：PostgreSQL/Redis/MinIO 持久卷、Alembic 一次性迁移、FastAPI API、Next.js 家长 Web 和 NewAPI ImageAnalysis worker；API 镜像包含迁移文件和 worker 脚本，Compose 从同目录 `infra/compose/.env` 自动注入变量。部署变量、账号密码首次引导、NewAPI 外部地址、启动/升级/回滚步骤见 `infra/compose/README.md`。这不代表备份恢复或真实 NewAPI 联调已完成。
- 项目 Owner 接受 ADR-0015/0016：Capture 目标路线调整为原图留在家庭边界，本地 PrivacySanitizer 只做不可逆脱敏，用户确认后由自用 NewAPI 兼容 Provider 结构化解析，题目再次人工确认后才进入 Tutor。ADR-0016 最初的 HMAC 认证部分随后被 ADR-0017/TASK-0007 替代并已删除；NewAPI 边界继续有效。
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
- 新增 Provider-free `offline-tutor-policy.v1` 与 `tutor-hint.v1`：仅消费人工确认题目的结构字段，提供 1～3 级提示，响应强制不含直接答案且成本为 0 元；新增 3-case synthetic eval。云 Tutor Provider 和 TutorTurn 持久化仍未接入。
- Web/PWA 家长工作台从空壳升级为简洁明亮的学习概览，读取现有 Household-scoped children/tasks/devices API，断开 API 时显示安全空状态；当前统一使用家长账号密码和 HttpOnly 会话。
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
- 2026-07-18：按 ADR-0018 完成本地及 Ubuntu Capture 上传收敛：Flutter 只向 API 发送带 Session 的原始图片流，API 通过 boto3 S3 兼容 multipart 写入私有 MinIO，并进行有界大小、增量 SHA-256、完整图片解码和失败清理；OpenAPI 删除预签名/独立确认合同，Compose 取消 MinIO 宿主端口。
