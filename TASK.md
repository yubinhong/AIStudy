# TASK.md — TASK-0007 认证面收敛与 Flutter 服务端地址配置

## 任务元数据

- 状态：`COMPLETE（代码与本地质量门槛完成；远端部署和真实设备验收保留在 PLAN-0008）`
- 类型：`FEATURE / SECURITY`
- 优先级：`P0`
- Owner：Codex（执行）；项目 Owner（用户，明确要求）
- 创建/更新：`2026-07-16`
- 关联：`PLAN-0008` 阶段 5a、`ADR-0017`、`TODO-012`

## 1. 目标与范围

运行时只保留家长/孩子“用户名+密码”登录，登录成功后分别使用 Web HttpOnly Cookie 或 Flutter Bearer Session 承载同一类可撤销会话。删除 HMAC Token、Demo Header、Web 认证旁路、签发脚本和对应契约/测试/配置。

Flutter 登录界面在用户提交账号密码前提供服务端基础地址编辑和持久化；仅允许无用户信息、查询和片段的 HTTP(S) 地址。服务端地址变更必须清除本地旧会话，防止将旧 Token 发往新服务端。

## 2. 验收标准

- [x] API 不再读取 `STUDY_AUTH_MODE`/`STUDY_AUTH_SECRET`，不接受 HMAC 或 `X-Demo-*` Header，运行时只认可密码登录产生的未撤销会话。
- [x] OpenAPI 业务端点只声明 `SessionCookie`/`BearerSession`，Web 无免登录开关或 Demo Header 回退，Compose 无旧认证配置。
- [x] Flutter 登录前可编辑并保存服务端地址；登录、孩子资料和 Capture 共用该地址，地址变更不复用旧会话。
- [x] API/OpenAPI/Web/Flutter 相关单测、格式、Lint/类型和构建门槛通过；无密钥、真实数据或意外生成物。
- [x] 同步 ADR、架构、安全、测试、运行手册和变更记录，记录该破坏性契约收敛的升级与回滚方案。

## 3. 兼容、回滚与风险

- 这是用户明确批准的破坏性安全收敛；旧 HMAC/Demo 客户端必须升级，不保留运行时兼容开关。
- 已签发的 HMAC Token 在升级后立即失效；现有密码账号和会话表不迁移、不删除。
- 回滚只能回滚到上一应用版本，不保证旧 HMAC/Demo 路径安全；若必须临时回退，需项目 Owner 再次明确批准并限制在隔离环境。
- 自托管 LAN 可使用 HTTP 调试；公网或生产必须由反向代理提供 HTTPS。

## 4. 完成记录

- 删除 API HMAC/Demo 认证器、旧 Token 签发脚本、环境开关和对应契约；业务测试改用真实账号密码创建的可撤销会话，并覆盖旧凭据被拒绝。
- Web 删除 Demo Profile、静态 Token 和免登录回退，工作台、账号管理和首次改密路由统一由 Session Cookie 保护。
- Flutter 新增登录前服务端根地址校验与安全持久化；登录、孩子档案和 Capture 统一读取该地址，更换地址先删除旧会话。
- 验证：API Ruff/Mypy、122 项非集成和 18 项 PostgreSQL/MinIO 集成通过；OpenAPI/JSON Schema 和认证 Scheme 检查通过；Web 格式/Lint/类型/2 项单测/生产构建通过；Flutter 格式/分析/17 项测试通过；Compose 本机配置解析通过；`git diff --check` 通过。
- 未执行：未重新部署远端 Ubuntu，未运行浏览器 E2E、实体 iPad 登录/退出/重启生命周期和备份恢复。Web 本地验证使用 Node 20/pnpm 9，虽全部通过但产生 engine warning；锁定容器仍使用 Node 24.18/pnpm 11.7。
- 回滚：优先前向修复；如必须回退应用版本，保留 `Account`/`AuthSession`/审计数据，不恢复已撤销会话。重新启用 HMAC/Demo 需项目 Owner 另行批准并限制在隔离环境。

---

# 历史任务：TASK-0006 Capture 与人工校正安全基础

## 任务元数据

- 状态：`COMPLETE（代码闭环；真实 Provider/设备/备份验证作为环境验收项保留）`
- 类型：`FEATURE`
- 优先级：`P1`
- Owner：Codex（执行）；项目 Owner（用户，明确要求继续 TODO-008）
- 创建/更新：`2026-07-15`
- 基线分支/提交：`master`；最近提交 `c3a107e`；工作区含本轮 OCR 入队/调度增量
- 关联：`TODO-008`、`PLAN-0006`、`ADR-0001`、`ADR-0002`、`ADR-0004`、`ADR-0005`、`ADR-0006`、`ADR-0009`、`ADR-0010`、`ADR-0011`、`ADR-0012（已被替代）`、`ADR-0013`、`ADR-0014`、`ADR-0015`、`ADR-0016`；后续认证任务 `TODO-012`、`PLAN-0007`、`ADR-0017`

## 1. 目标与范围

实现 Capture 与低置信度人工校正的安全基础：孩子只能在自己的 Household/StudySession 内登记一份图片采集元数据，服务端不把未验证 OCR 结果当作事实；在没有获准 OCR Provider 时，Capture 必须进入人工校正状态，校正记录以追加写保存。

本任务包含：Capture OpenAPI 增量、API 领域/仓储/迁移、Household/child 授权、版本冲突与幂等、合成 PostgreSQL 集成测试，以及必要的架构/安全/运行记录。

本任务不包含：商业化、多地区、第三方 IdP、复杂监护人流程或外部商业 Provider。按 ADR-0010～0016，本地 synthetic 环境已实现相机/相册选择、MinIO 私有上传、服务端确认（含对象实际 SHA-256 核验）、旧 OCR 入队/Job 状态轮询/候选人工确认、Provider-neutral Schema、PrivacySanitizer 核心/规则信号、Flutter 本地脱敏预览确认、ImageAnalysis queued/blocked API、Bearer 认证、NewAPI Adapter、0009 提取结果持久化、可恢复 worker、人工确认生成 VerifiedQuestion 和无 Provider offline Tutor Policy 降级提示；不把真实原图发出，也不把未确认提取伪装成业务事实。S3/OCR 运行时和模型版本已锁定，真实视觉检测器、实际 NewAPI 联调和备份恢复仍属于环境验收项。local/CI 已提供合成孩子档案删除入口、OCR 输入规范化边界、候选结果持久化和 Tutor synthetic eval 边界。

`2026-07-15` 架构调整：项目 Owner 接受 ADR-0015，目标路线改为本地 `PrivacySanitizer` 只用 OCR/规则/轻量视觉检测敏感区域，用户确认不可逆脱敏副本后由单一获批云端视觉 Provider 解析照片。现有 text/formula OCR Job/结果链路是已实现的旧路线和可关闭回滚能力，不再是目标默认解析器。本轮先实现不依赖云 Provider 的脱敏核心、Provider-neutral Schema 和 synthetic eval，不接入云 Provider 或真实图片。

随后项目 Owner 接受 ADR-0016 并明确本产品按自用、自托管 NewAPI 推进；因此当前实现增加了自用 Bearer、显式 NewAPI 开关和 queued worker，但实际 Provider 联调与人工确认仍单独保留为未完成项。

项目 Owner 随后批准用家长/孩子账号密码和可撤销会话替换 HMAC Bearer。该变更已记录为 ADR-0017、PLAN-0007 和 TODO-012；本任务完成后已自动进入 PLAN-0007，认证代码、OpenAPI、数据库和 Compose 切换不再属于本 Capture 任务。

## 2. 已知冲突与实施假设

- `ASSUMPTION-01`：直接登记的 Capture 以 `needs_correction` 状态创建；预签名上传 Capture 先处于 `upload_pending`，服务端确认私有对象的声明 MIME/大小和实际 SHA-256 后才转为 `needs_correction`。不调用外部服务，也不产生伪造 OCR 内容。
- `ASSUMPTION-02`：本阶段的业务请求仅接收受限媒体声明（类型、大小、不可逆内容哈希），不接收原始图片、对象键或完整题目文本；短期签名 URL 仅出现在上传响应中，永不进入数据库业务模型、审计、错误响应或日志。人工校正内容只进入业务库，永不写入审计事件或错误响应。
- `ASSUMPTION-03`：校正是追加事件；Capture 的派生状态以服务端 `version` 明确合并，不能用最后写入覆盖已有校正。
- `ASSUMPTION-04`：local MinIO 预签名 PUT URL 默认有效期为 300 秒，并通过环境变量配置；生产值须在 staging 前复核。OCR Adapter 只接受预置模型目录，禁止运行时自动下载模型。
- `ASSUMPTION-05`：自用 NewAPI 只通过 `STUDY_NEWAPI_ENABLED=true` 显式开启；queued job 仅在本地配置通过、脱敏副本用户确认且 SHA-256 与 Capture 一致时产生。worker 失败只写稳定错误码，QuestionExtraction 必须保持 `needs_confirmation=true`，不得直接进入 Tutor。

## 3. 验收标准

- [x] OpenAPI 定义 Capture、人工校正、版本化请求/响应、错误与兼容策略；不引入手工漂移的跨端公共模型。
- [x] 仅绑定孩子可为自己的 Session 创建、读取、校正 Capture；跨 Household、同家庭其他孩子、无绑定主体和枚举 ID 均被拒绝。
- [x] Capture 初始必须要求校正；校正追加写、幂等重放和版本冲突可验证，审计中无原始题目或校正文本。
- [x] PostgreSQL 迁移和仓储在同一事务处理 Capture、校正、幂等记录与审计；验证迁移回滚/前滚、重复请求和并发校正。
- [x] 已记录真实媒体、OCR Provider、设备权限/离线 SQLite 与生产生命周期仍未实现的原因、回滚方式和下一步。
- [x] 已以 ADR-0015/0016 记录本地脱敏/自托管视觉职责、原图不外发、单 Provider、识别/Tutor 分离、临时副本删除、旧 OCR 兼容迁移与回滚；当前已实现 Adapter、queued worker、未确认提取落库、人工确认生成 VerifiedQuestion 和成功/失败清理分支。真实视觉检测器、NewAPI 实例联调、iPad 回归和备份生命周期演练仍未执行。

## 4. 验证与回滚

- 计划验证：OpenAPI 结构检查、API Ruff/Mypy/单元与 local PostgreSQL 集成测试、Alembic downgrade/upgrade；不运行真实 Provider 或真实图片。
- 回滚：合同仅新增；优先关闭 Capture 路由或前向修复迁移。不得删除 CaptureCorrection/AuditEvent、不得把校正文本写进日志、不得清空客户端队列。

## 5. 当前进度

- `2026-07-13`：项目 Owner 明确授权执行 `TODO-008`；已复核 PRD、架构、安全、测试、ADR 和现有 Learning 持久化边界，建立本任务与计划。
- `2026-07-13`：OpenAPI `0.4.0` 已增加 Capture 元数据、人工校正和显式版本冲突合同。Capture 创建只接收 MIME、大小和 SHA-256 声明，且始终进入 `needs_correction`；不接收原始媒体或调用 OCR Provider。
- `2026-07-13`：API 已实现 child-only Capture 创建/查询和追加校正；`0002_capture_manual_correction` 在 PostgreSQL 中保存 Capture/Correction、幂等记录和无原文审计事件。19 项 API 测试及 migration downgrade/upgrade 演练通过。
- `2026-07-13`：项目 Owner 已接受 ADR-0010（本地 MinIO/私有 Bucket/预签名上传）、ADR-0011（24 小时/7 天/30 天保留、家长控制、级联删除）与 ADR-0012（本地 PaddleOCR、人工确认、外部默认 0 元）。
- `2026-07-13`：项目 Owner 已锁定 `boto3==1.43.46`、`paddleocr[doc-parser]==3.7.0`、`paddlepaddle==3.3.1`、CPU/`paddle_static` 与普通/方向/公式模型清单；macOS Docker 的 linux/amd64 synthetic 真实模型烟测已通过，Ubuntu 24.04 x86_64 原生性能基准和真实题型评测仍未执行。
- `2026-07-13`：依赖已写入 `pyproject.toml`/`uv.lock` 并在本机 API 虚拟环境安装；本地 MinIO healthy。`S3ObjectStorage` 仅签发 300 秒、JPEG/PNG、最多 8 MB、`captures/` 前缀的 PUT URL；集成测试以随机 synthetic JPEG 上传后立即删除。
- `2026-07-13`：`LocalPaddleOcrAdapter` 已要求五个锁定模型目录全部预置后才构建 CPU 引擎，绝不在运行时自动下载；假工厂测试验证普通/方向/公式模型参数。
- `2026-07-13`：临时 uv 可执行路径在本轮清理后不可发现；已使用项目 `.venv` 完成等效静态/测试验证，标准 uv 恢复已记录为范围外 `TODO-011`。
- `2026-07-13`：OpenAPI `0.5.0` 新增私有上传签发与确认端点；`0003_capture_object_upload_state` 仅在 PostgreSQL 内保存不含身份的对象键。确认端会先读取 MinIO 对象 MIME/大小，再把 `upload_pending` 转为 `needs_correction`；跨 Household/同家庭兄弟孩子均返回 404，确认和签发均可幂等重放。
- `2026-07-14`：已应用本地 `0003`～`0006` 迁移，并使用 `.venv` 执行 Ruff、Mypy、60 项单元与 14 项 PostgreSQL/MinIO 集成测试（合计 74 项）；新增有界对象读取、SHA-256、JPEG/PNG 容器头和尺寸/像素数/EXIF 边界测试。端到端测试只上传后立即删除 synthetic JPEG。对象存储配置不再有代码凭据兜底，未注入环境值时安全地拒绝上传。
- `2026-07-13`：Capture 上传写入原图 24 小时到期时间；清理器使用数据库行锁抢占过期对象，删除成功标记 `deleted`，失败标记 `failed` 并允许后续重试，审计仅写稳定事件名和资源 ID。OCR 失败 7 天、裁剪图 30 天策略已统一为固定时间函数；OCR 失败入口随后由 `LocalOcrJob` 接入，裁剪入口仍待实现。
- `2026-07-13`：新增 `model_provisioning.py`、官方五模型清单入口与 API 多阶段 Dockerfile：构建阶段只接受 HTTPS 归档、逐项校验 SHA-256、拒绝路径穿越/软链接并写入构建标记；运行时 Adapter 要求五个预置目录和标记，显式使用 CPU/`paddle_static`，不自动下载或更新。
- `2026-07-13`：按 `linux/amd64` 目标完成 `study-api:local` 镜像构建；依赖层锁定安装成功，五个 PaddleOCR 官方归档均在构建阶段通过清单 SHA-256，模型复制到运行层，运行层无模型下载/更新逻辑。Mac arm64 仅通过 Docker 模拟构建，Ubuntu 24.04 x86_64 是目标部署形态。
- `2026-07-13`：新增 OCR 前置有界对象读取、声明大小/SHA-256、JPEG/PNG 容器头、尺寸/像素数校验、Pillow 完整像素解码和无 EXIF/元数据规范化重编码；新增 PaddleOCR 文本结果纯解析、临时文件执行边界、置信度边界和强制人工确认标记。真实题型模型实测仍未实现。
- `2026-07-13`：修复镜像内 PaddleOCR 真实启动缺少的 `libgl1`/`libglib2.0-0`/`libgomp1`，关闭未锁定的 `UVDoc` 去畸变和模型源检查；五个锁定模型在无网络 linux/amd64 容器中完成 1×1 synthetic PNG CPU 烟测，空结果仍要求人工确认。
- `2026-07-13`：新增按 Household/Child 边界原子认领 Capture 对象的级联删除编排；对象逐项删除，失败标记 `failed` 并可重试，成功/失败均写稳定审计事件且不记录对象键。内存单元与 PostgreSQL 集成回归覆盖成功、重试、幂等和错误 Household。
- `2026-07-13`：新增 local/CI 家长删除孩子档案 API；只有 Capture 级联全部成功后才删除合成 Profile，失败返回 503 且档案保持可见，同一幂等键可重试/重放；OpenAPI 增加向后兼容的 DELETE 路径。生产 Profile 持久化、数据库元数据、派生缓存/向量和备份仍未接入。
- `2026-07-13`：新增 `0005_ocr_result_persistence` 与 PostgreSQL OCR 仓储；只保存 Provider/模型/Schema 版本、置信度和规范化候选文本，空结果也持久化，结果始终要求人工确认。事务内绑定 Capture 的 Household/Child，支持幂等重放并拒绝跨家庭/跨孩子读取；审计不写候选原文。
- `2026-07-13`：新增家长保存/立即删除单张图片入口；保存和删除都要求家长 Household 授权与幂等键，单对象删除先抢占再调用私有存储，失败可重试，成功不删除 Capture 元数据，审计仅记录稳定事件名和资源 ID。
- `2026-07-14`：新增 `evals/ocr_synthetic_v1.json` 与无外部服务的固定 OCR 合同评测入口；6 个 synthetic cases 全部通过，覆盖正常候选、低置信度人工校正、空结果、空行过滤及输入拒绝，评测明确 `provider_calls: false`。
- `2026-07-14`：新增 `LocalOcrJob` Worker 边界，串联已确认 Capture 的私有对象有界读取、图片规范化、本地 OCR Adapter 和候选结果仓储；未确认上传、非法图片和 Provider 失败均不会持久化结果，Redis/持久化 Worker 和真实题型模型基准仍未接入。
- `2026-07-14`：Worker 失败会把未删除的 Capture 标记为 `ocr_failure`，从失败发生时起最多保留 7 天；重复失败不会延长期限，清理器仍可按既有行锁/失败重试机制删除对象，审计只记录稳定事件名和资源 ID。
- `2026-07-14`：此前 OCR 基线门槛通过：60 项单元、14 项 PostgreSQL/MinIO 集成、Ruff lint/format、Mypy 23 个源文件，以及 `ocr-synthetic-v1` 6/6；仅使用合成数据，未调用外部 Provider。
- `2026-07-14`：新增 child-only 幂等 OCR 入队端点和 local/CI `InMemoryOcrJobQueue`；`LocalOcrDispatcher` 一次只领取一个任务，成功写入结果 ID，失败只写稳定错误码并允许用新幂等键重试，不保存 Provider 错误详情。
- `2026-07-14`：入队调度切片定向测试、OpenAPI 结构检查、Ruff、Mypy（24 个源文件）通过；完整 64 项单元与 15 项 PostgreSQL/MinIO 集成门槛通过。
- `2026-07-14`：新增 `0006_ocr_job_ledger`；PostgreSQL 队列按 Household/Capture/幂等键唯一，使用 `FOR UPDATE SKIP LOCKED` 领取任务，失败只保留稳定错误码，超过租约的 running 任务可重新领取；定向迁移/队列集成测试通过。
- `2026-07-14`：新增独立一次性 `run_ocr_worker.py` 入口；启动强制校验本地 MinIO、PostgreSQL 和五个带 SHA-256 构建标记的模型目录，CLI 只输出 idle/succeeded/failed/startup_error/worker_error 稳定状态，不输出 Provider 或配置详情。
- `2026-07-14`：Worker 入口相关全量门槛通过：67 项单元、15 项 PostgreSQL/MinIO 集成、Ruff、格式、Mypy 25 个源文件、`ocr-synthetic-v1` 6/6 和 `git diff --check`。
- `2026-07-14`：新增 child-only OCR 结果读取接口与 `OcrResultWithCandidates` 合同；服务端再次校验 Household/Child/Capture 绑定，兄弟孩子、家长、跨家庭和 Capture 不匹配均拒绝，候选结果仍要求人工确认；定向路由测试 4 项通过。
- `2026-07-14`：结果读取增量全量门槛通过：71 项单元、15 项 PostgreSQL/MinIO 集成、OpenAPI 结构检查、Ruff、格式、Mypy 25 个源文件、`ocr-synthetic-v1` 6/6 与 `git diff --check`；仅使用 synthetic 数据，未调用外部 Provider。
- `2026-07-14`：新增 child-only OCR 候选确认；只提交候选 ID 与 Capture 版本，服务端重新校验结果/候选/绑定关系后复用 CaptureCorrection 追加写，用户幂等键保持 128 字符边界内，OCR 结果仍不可变。
- `2026-07-14`：候选确认增量质量门槛通过：73 项单元、16 项 PostgreSQL/MinIO 集成、OpenAPI 结构检查、Ruff、格式、Mypy 25 个源文件与 `git diff --check`；仅使用 synthetic 数据。
- `2026-07-14`：按顺序继续客户端 UI 实现；Flutter 第 1/2/3 张横屏学习桌、拍题输入、OCR 确认和分数思考提示原型已落地，加入合成头像/分数示意/题目照片资源，拍照/相册选择/示例题目入口可进入人工确认页，iOS 相机和相册权限声明已加入；新增 `CaptureApiClient`，实现 JPEG/PNG 校验、SHA-256、短期签名 PUT、服务端确认、幂等 OCR 入队、Job 轮询和候选人工确认/纠正，Flutter pub get、format、analyze、9 项测试通过；页面已由显式 `STUDY_CAPTURE_SESSION_ID` 调试开关接入，带开关时上传后显示等待状态，不展示合成候选。iOS 已锁定横屏，含原生 `image_picker` 的无签名 `Runner.app` 构建成功并重新安装到实体 iPad，用户已实机确认拍照、权限和“已选择题目照片”页面通过。Flutter 不支持该实体设备截图，目标 landscape QA 仍 blocked。实体上传 smoke test 已完成；下一项是让合成 StudySession 的 OCR Worker 结果可被 iPad 读取。
- `2026-07-14`：实体 iPad local Capture smoke test 通过；API 日志确认预签名上传 201、服务端对象确认 201、OCR 入队 202，且页面未展示合成 OCR 候选。仅使用合成 StudySession 和本地 MinIO，未接入真实儿童图片；OCR Worker 结果状态/轮询仍待实现。
- `2026-07-14`：新增 child-only OCR Job 状态读取接口和 Flutter `getOcrJob` 解析；服务端只返回 queued/running/succeeded/failed、attempt 和 result_id 等稳定字段，跨孩子读取返回 404；定向 API、OpenAPI 和 Flutter 测试通过。
- `2026-07-14`：Flutter 确认页已接入有界 OCR Job 轮询、`result_id` 候选读取、候选确认和手工纠正；候选返回前保持等待，候选返回后仍必须人工确认。客户端测试覆盖 queued/succeeded 读取、候选字段、确认/纠正路径和幂等键；Flutter 总测试数增至 9。
- `2026-07-14`：增加显式 local durable mode：API 的 Learning/Capture、OCR Job 和 OCR 结果仓储可统一切换到 PostgreSQL；Worker 增加可选 `--watch` 轮询模式，默认一次性命令保持不变。Ruff、Mypy、74 项 API 非集成测试和 `git diff --check` 通过。
- `2026-07-14`：新增 PostgreSQL/MinIO synthetic API + Worker 闭环集成测试；真实走私有 MinIO、Job Ledger、`LocalOcrJob`、结果持久化和 child-only 结果读取，Provider 使用 synthetic adapter。完整 API 集成回归 17 项通过，测试结束删除 synthetic 对象。
- `2026-07-14`：新增 `check_ocr_runtime.py` 只读预检和固定门禁测试；严格要求 Ubuntu 24.04、x86_64、Python 3.12、PaddlePaddle 3.3.1、PaddleOCR 3.7.0 及五个带 SHA-256 构建标记的模型目录。当前 macOS 预检稳定返回 `blocked`，未执行真实模型推理。
- `2026-07-14`：新增 `ocr-model-synthetic-v1` 锁定模型 smoke runner；输入由脚本内存生成，调用前强制运行时预检，输出只含每题状态和延迟，不接受图片路径、不保存 OCR 原文。当前 macOS 按预期阻塞，Ubuntu 真实 CPU 推理未执行。
- `2026-07-14`：优化 `LocalPaddleOcrAdapter`：文本与公式引擎在实例内按需初始化并复用，每次使用前仍校验五个预置模型目录和 SHA-256 标记；新增工厂调用次数与实例复用回归测试，避免 Worker 对每张图片重复加载模型。
- `2026-07-15`：补齐按需公式 OCR 执行边界与 `rec_formula` 解析；公式结果没有 Provider 置信度时按 0.0 保守处理，始终保持人工确认；锁定模型 smoke fixture 增加公式 case。81 项 API 非集成测试、Ruff、Mypy 和 `git diff --check` 通过，当前 macOS 真实模型 smoke 仍按预检阻塞。
- `2026-07-15`：将 OCR mode 贯穿 OpenAPI、Flutter `CaptureApiClient`、内存/PostgreSQL Job Ledger 和 Worker：旧请求默认 `text`，显式 `formula` 才调用公式模型；新增 `0007_ocr_job_mode` 前滚迁移、模式幂等冲突保护和 API/Worker/Flutter 回归。83 项 API 非集成、17 项 PostgreSQL/MinIO 集成、Flutter 10 项测试、Mypy/Ruff 均通过。
- `2026-07-15`：完成 `0007_ocr_job_mode` 在本地 synthetic PostgreSQL 的 downgrade/upgrade 往返验证；固定 `ocr-synthetic-v1` 评测 6/6 通过，模型 smoke 在当前 macOS 按平台预检稳定返回 `blocked`，未执行真实推理。
- `2026-07-15`：根据项目 Owner 提供的架构讨论，接受 ADR-0015 并完成文档级路线调整：原图留在家庭边界，本地 OCR 仅参与脱敏，单一获批云视觉 Provider 解析脱敏副本，人工确认后再进入 Tutor。ADR-0012 标记为 Superseded；未修改现有代码、合同或数据库。
- `2026-07-15`：新增 Provider-neutral 的 PrivacySanitization/ImageAnalysisJob/QuestionExtraction/VerifiedQuestion Schema；实现本地 PrivacySanitizer 的元数据清除、检测区域实色覆盖、不可逆重编码、低置信度/大或歧义人脸/缺失区域阻断，并完成 6-case synthetic eval。上传确认同时核验对象实际 SHA-256；新增 0008 receipt-only ImageAnalysis ledger/API，未实现真实视觉检测器、云 Provider 或临时副本生命周期。
- `2026-07-15`：新增无 Provider 的 `offline-tutor-policy.v1`，只消费 `VerifiedQuestion` 的结构字段，提供 1～3 级提示、直接答案为空和 0 元成本的固定响应；新增 synthetic eval。Flutter 思考页同步支持第 3 级提示。该降级策略不代表任何云 Tutor 已获批准。
- `2026-07-15`：接入 `LocalPrivacyDetector` 的敏感标签/规则区域信号，新增 Flutter 本地脱敏预览、手动涂抹、不可逆 PNG 生成与 SHA-256 计算；拍题上传路径只接受确认后的脱敏字节，原图不进入上传客户端。Widget/analyze 已通过；真实 iPad 渲染和手动涂抹仍需设备人工验证。
- `2026-07-15`：项目 Owner 接受 ADR-0016，明确自用单家庭 Bearer 令牌和项目 Owner 自行部署 NewAPI；新增 HMAC token 签发/解析、OpenAI-compatible Adapter、显式开关和 Web/Flutter Bearer 注入边界，默认 Provider 关闭。
- `2026-07-15`：ImageAnalysis 从 receipt-only blocked 扩展为安全条件满足且 NewAPI 开启时 queued；新增 `0009_question_extraction`、未确认提取结果仓储、PostgreSQL 行锁/stale lease worker、提取读取合同和失败稳定状态。110 项 API 非集成、18 项 PostgreSQL/MinIO 集成、OpenAPI 21 paths/34 schemas/6 JSON schemas、Flutter/Web 门槛通过；当时实际 NewAPI 联调和人工确认接口仍待完成，后续已补齐人工确认代码，真实 Provider 联调仍保留为环境验收。
- `2026-07-15`：补齐自用 Docker Compose 部署：API 镜像复制 `migrations/`、`alembic.ini` 和 worker 脚本；Compose 增加 PostgreSQL/Redis/MinIO 持久卷、一次性 `migrate`、API healthcheck、默认 ImageAnalysis worker 和家长 Web；新增 `infra/compose/.env.example` 和自动读取的 `infra/compose/.env` 部署方式。Compose config、`linux/amd64` API/迁移镜像构建、ARM64 Web standalone 镜像、Web 格式/Lint/类型/测试/构建、镜像内容检查和 110 项 API 非集成测试通过；完整容器启动、真实 NewAPI 联调、人工确认接口、脱敏副本清理和备份恢复仍待完成。
- `2026-07-15`：按本机 Apple Silicon 调试需求增加 Flutter 1.2 秒有限启动过渡，首页档案加载与动画并行，减少动态效果时跳过；Compose 的 ImageAnalysis worker 移入默认 profile，NewAPI 关闭时以空闲实现保持健康且不读取图片/连接 Provider。Dockerfile 取消固定 amd64，依赖标记保留 macOS ARM64 和 Linux x86_64 Paddle，同时为缺少 PaddlePaddle 3.3.1 Linux aarch64 wheel 的原生 ARM 调试镜像跳过 Paddle/模型和专用系统库。Compose 静态配置无额外 profile，`linux/arm64` 镜像构建、110 项 API 单元、13 项 Flutter 测试及静态检查通过；当时完整 Compose 启动未执行，后续已在 Ubuntu x86_64 VM 完成基础启动验收。
- `2026-07-15`：项目 Owner 批准下一阶段改用账号密码。已接受 ADR-0017，建立 PLAN-0007/TODO-012，并同步 PRD/架构/安全/测试/运维边界；一次性 `admin/admin123456` 仅允许空库、本机首次登录，改密前阻断家庭数据。当前 HMAC Bearer 仍是运行时事实，本轮未修改代码、合同、迁移或 Compose。
- `2026-07-16`：完成 `0010_verified_question`、人工确认/读取 API、VerifiedQuestion 内存/PostgreSQL 仓储和迁移测试；验证请求带 Capture 版本、Household/Child 绑定和幂等键，未确认提取保持不可变。
- `2026-07-16`：ImageAnalysis worker 成功后立即删除脱敏派生对象，失败路径也尝试删除并保留稳定失败状态；新增清理成功/失败回归测试。TASK-0006 的代码验收完成，真实 NewAPI、真实视觉检测器、iPad 回归和备份恢复仍是环境验收项。
- `2026-07-16`：在 Ubuntu 24.04 x86_64 VM 完成自用 Compose 基础验收：Docker/Compose、PostgreSQL/Redis/MinIO/API/Web/迁移/worker 健康，`0011` 前滚、loopback bootstrap login、重启恢复和内存 synthetic OCR smoke 通过；容器内 OS 预检因 Debian 13 运行层而保持 blocked。NewAPI key 未提供，Provider 保持关闭；首次改密、Cookie/CSRF、孩子账号/iPad 生命周期、真实视觉链路和备份恢复仍未完成。
- `2026-07-16`：修复 OCR 预检与发布镜像运行层的契约：宿主继续要求 Ubuntu 24.04，amd64 镜像通过显式 `STUDY_OCR_CONTAINER_RUNTIME=true` 接受锁定 Debian 13；新增单元覆盖，远端完整 4-case OCR eval 待重建镜像后执行。
- `2026-07-16`：远端重建 x86_64 API 镜像后，OCR 预检输出 `ready`，`ocr-model-synthetic-v1` 4/4（普通文本 3、公式 1）通过；未发送图片到 NewAPI。
- `2026-07-16`：项目 Owner 配置 NewAPI key 后启用远端 Provider；新增可清理的合成 live eval，主机和 API 容器访问 `newapi.iuhui.site` 均收到 HTTP 403，未取得 Extraction。worker 新增稳定 Provider 错误码，失败任务、MinIO 对象和合成数据库记录已清理。
- `2026-07-16`：定位 HTTP 403 为 Cloudflare 1010 对 Python 默认 `urllib` User-Agent 的拦截；Adapter 新增受限 `STUDY_NEWAPI_USER_AGENT`（默认 `study-api/0.5`）、`Accept: application/json` 和完整 `question-extraction.v1` 字段提示。远端重建 API/worker 后，synthetic live eval 成功得到 `needs_confirmation=true` 的 Extraction，脱敏派生对象删除，PostgreSQL synthetic Job 残留为 0；不输出原始 Provider 响应或发送真实图片。远端人工确认生成 VerifiedQuestion 仍待 PLAN-0008 验收。
- 下一步：继续执行 `PLAN-0008` 的远端人工确认、Cookie/CSRF、iPad 会话生命周期和备份恢复验收；真实视觉检测器和固定视觉评测仍作为后续实现项。
