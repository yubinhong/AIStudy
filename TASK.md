# TASK.md — TASK-0006 Capture 与人工校正安全基础

## 任务元数据

- 状态：`IN_PROGRESS`
- 类型：`FEATURE`
- 优先级：`P1`
- Owner：Codex（执行）；项目 Owner（用户，明确要求继续 TODO-008）
- 创建/更新：`2026-07-14`
- 基线分支/提交：`master`；最近提交 `7cfd302`；工作区含既有未提交的 Capture/对象存储增量
- 关联：`TODO-008`、`PLAN-0006`、`ADR-0001`、`ADR-0002`、`ADR-0004`、`ADR-0005`、`ADR-0006`、`ADR-0009`、`ADR-0010`、`ADR-0011`、`ADR-0012`

## 1. 目标与范围

实现 Capture 与低置信度人工校正的安全基础：孩子只能在自己的 Household/StudySession 内登记一份图片采集元数据，服务端不把未验证 OCR 结果当作事实；在没有获准 OCR Provider 时，Capture 必须进入人工校正状态，校正记录以追加写保存。

本任务包含：Capture OpenAPI 增量、API 领域/仓储/迁移、Household/child 授权、版本冲突与幂等、合成 PostgreSQL 集成测试，以及必要的架构/安全/运行记录。

本任务不包含：真实儿童图片、生产对象存储/密钥、商业 OCR Provider、真实设备相机/SQLite UI 或 Tutor。按 ADR-0010～0012，本任务只使用 synthetic 图片接入本地 MinIO 预签名上传与本地 PaddleOCR；S3/OCR 运行时和模型版本已锁定，真实模型实测输出和生产级 Profile/备份删除工作流仍须实现。local/CI 已提供合成孩子档案删除入口、OCR 输入规范化边界和候选结果持久化边界。

## 2. 已知冲突与实施假设

- `ASSUMPTION-01`：直接登记的 Capture 以 `needs_correction` 状态创建；预签名上传 Capture 先处于 `upload_pending`，服务端确认私有对象的声明 MIME/大小后才转为 `needs_correction`。不调用外部服务，也不产生伪造 OCR 内容。
- `ASSUMPTION-02`：本阶段的业务请求仅接收受限媒体声明（类型、大小、不可逆内容哈希），不接收原始图片、对象键或完整题目文本；短期签名 URL 仅出现在上传响应中，永不进入数据库业务模型、审计、错误响应或日志。人工校正内容只进入业务库，永不写入审计事件或错误响应。
- `ASSUMPTION-03`：校正是追加事件；Capture 的派生状态以服务端 `version` 明确合并，不能用最后写入覆盖已有校正。
- `ASSUMPTION-04`：local MinIO 预签名 PUT URL 默认有效期为 300 秒，并通过环境变量配置；生产值须在 staging 前复核。OCR Adapter 只接受预置模型目录，禁止运行时自动下载模型。

## 3. 验收标准

- [ ] OpenAPI 定义 Capture、人工校正、版本化请求/响应、错误与兼容策略；不引入手工漂移的跨端公共模型。
- [ ] 仅绑定孩子可为自己的 Session 创建、读取、校正 Capture；跨 Household、同家庭其他孩子、无绑定主体和枚举 ID 均被拒绝。
- [ ] Capture 初始必须要求校正；校正追加写、幂等重放和版本冲突可验证，审计中无原始题目或校正文本。
- [ ] PostgreSQL 迁移和仓储在同一事务处理 Capture、校正、幂等记录与审计；验证迁移回滚/前滚、重复请求和并发校正。
- [ ] 记录真实媒体、OCR Provider、设备权限/离线 SQLite 与生产生命周期仍未实现的原因、回滚方式和下一步。

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
- `2026-07-14`：已应用本地 `0003`～`0005` 迁移，并使用 `.venv` 执行 Ruff、Mypy、60 项单元与 14 项 PostgreSQL/MinIO 集成测试（合计 74 项）；新增有界对象读取、SHA-256、JPEG/PNG 容器头和尺寸/像素数/EXIF 边界测试。端到端测试只上传后立即删除 synthetic JPEG。对象存储配置不再有代码凭据兜底，未注入环境值时安全地拒绝上传。
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
- `2026-07-14`：新增 `LocalOcrJob` Worker 边界，串联已确认 Capture 的私有对象有界读取、图片规范化、本地 OCR Adapter 和候选结果仓储；未确认上传、非法图片和 Provider 失败均不会持久化结果，真实调度器和真实题型模型基准仍未接入。
- `2026-07-14`：Worker 失败会把未删除的 Capture 标记为 `ocr_failure`，从失败发生时起最多保留 7 天；重复失败不会延长期限，清理器仍可按既有行锁/失败重试机制删除对象，审计只记录稳定事件名和资源 ID。
- `2026-07-14`：最终相关门槛通过：60 项单元、14 项 PostgreSQL/MinIO 集成、Ruff lint/format、Mypy 23 个源文件，以及 `ocr-synthetic-v1` 6/6；仅使用合成数据，未调用外部 Provider。
- 下一步：执行 Ubuntu 24.04 CPU 真实模型实测，补 Tutor/提示层级 eval 和生产级完整删除工作流；不得接入真实儿童图片。迁移 downgrade 仍不对当前含 synthetic 记录的本地库执行。
