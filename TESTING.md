# TESTING.md

## 1. 当前状态与质量目标

当前仓库已有 P0/P1 依赖清单、三类锁文件、核心测试和 CI 草案。API 的 Household/认证/学习/Capture/最小 Tutor/周报/导出/错题复习切片、Web/Flutter 入口、SQLite 离线队列和 Compose 已验证；Android/iOS 构建及 PostgreSQL/MinIO 恢复已有记录。ADR-0020 的教材导入/知识发布、数学三入口、作答四态讲解和任务建议仍未实现，完整错题本 UI/E2E 仍待补齐。浏览器 E2E、实体设备最终回归、契约 SDK 生成和正式依赖/镜像安全扫描仍是后续入口。

- 核心用户路径：家长设置孩子教材范围并审核发布 → 孩子选择数学/学习模式 → 错题安全拍摄题目+答题区 → 确认题目和作答状态 → 有作答时定位错步，确认空白时从头讲解 → MistakeRecord/ReviewSchedule → 到期逐题复习 → 家长安排或批准今日任务 → 周报；现有代码只覆盖其中的任务、拍题、题目确认、最小提示和周报基础。
- 不可接受的失败：跨家庭越权；原图/未确认脱敏图/儿童数据/密钥泄漏；同一图片被静默发送给多个 Provider；学习记录丢失或被最后写入覆盖；AI 在练习/复习或缺少错题门禁时直接代答、错误结论静默入库；删除请求未执行却报告成功；未记录的成本失控。
- 覆盖策略：风险驱动，不设脱离代码基线的统一行覆盖率。家庭权限、幂等/离线合并、Tutor Policy/Schema、数据删除和核心 E2E 必须覆盖成功与失败路径；普通模块在 P0 代码基线后批准覆盖阈值。

## 2. 当前可运行验证

### 文档占位符检查

```bash
rg -n '\{\{|\}\}' AGENTS.md AI_CONTEXT.md ARCHITECTURE.md CHANGELOG.md DECISIONS.md PLANS.md PRD.md PROJECT.md RUNBOOK.md SECURITY.md TASK.md TESTING.md TODO.md
```

预期：无输出。`prompts/` 和 `docs/adr/0000-template.md` 是可复用模板，保留占位符是预期行为。

### 仓库事实检查

```bash
git status --short
git branch --show-current
rg --files -uu -g '!.git/**' -g '!node_modules/**'
```

预期：当前分支 `master`、无提交；P0 骨架文件和三类锁文件已存在，Android/iOS 原生构建均已有本地验证。

## 3. P0 目标标准命令

以下命令同时是脚手架验收契约。实现时如采用不同入口，必须先保证实际可运行，再同步本文件和 `AGENTS.md`。

| 区域/目的 | 目标命令 | 何时运行 | 当前状态 |
| --- | --- | --- | --- |
| Flutter 安装 | `cd apps/child_flutter && flutter pub get` | 锁文件变化/干净环境 | 通过（2026-07-14；Flutter 3.44.6；`image_picker 1.2.3` 已解析并写入 `pubspec.lock`；2026-07-13 交互式 PATH 与 `flutter doctor -v` 全绿） |
| Flutter 格式 | `cd apps/child_flutter && dart format .` | 每次 Flutter 变更 | 通过（2026-07-17；即时拍题会话、ImageAnalysis 轮询与人工确认增量已格式化） |
| Flutter 静态/类型 | `cd apps/child_flutter && flutter analyze` | 每次 Flutter 变更 | 通过（无 issues，2026-07-17） |
| Flutter 单元/Widget | `cd apps/child_flutter && flutter test` | 每次 Flutter 变更 | 通过（29 tests，2026-07-18；新增到期错题加载/复习提交回归） |
| Flutter UI 视觉 QA | 原型目标 viewport `1194 × 834` 的真实设备/截图比较 | 每次客户端 UI 原型变更 | 阻塞（2026-07-14）：实体 iPad 已成功横屏启动 Debug 应用，但 Flutter screenshot 不支持实体设备；iPad mini 模拟器仅完成 portrait smoke screenshot，详见 `design-qa.md` |
| Flutter 构建 | `cd apps/child_flutter && flutter build apk --release`；`flutter build ios --release --no-codesign` | 合并前/平台变更 | 通过（2026-07-17）：Android release APK 53.8 MB，iOS release 无签名 `Runner.app` 20.9 MB；不再要求 `STUDY_CAPTURE_SESSION_ID`。Android 仍为自用 debug key 签名，正式 App ID/签名由 `TODO-013` 跟踪；iOS 提示 `flutter_secure_storage` 尚不支持 Swift Package Manager，当前 CocoaPods 构建不受影响 |
| Flutter Android 实体设备 | 在华为 Nova 9 验证 ADB 识别、登录、相机/相册权限、脱敏预览、弱网与会话重启 | Android/认证/图片输入变更 | 进行中（2026-07-17）：Nova 9 已完成登录、相机/相册选择、脱敏预览、即时拍题会话、3.09 MB MinIO 上传/确认和 ImageAnalysis 入队；首次 Provider 请求返回 `provider_http_413`，现已部署 600 KB 有界压缩并覆盖安装最终 APK，等待第二次拍题确认 Extraction/VerifiedQuestion。弱网和重启仍待验收 |
| Ubuntu API LAN 部署 | 构建并启动匹配的 API 运行目录，验证健康、迁移和 LAN 认证 | API/认证/部署变更 | 通过（2026-07-18）：API `0.8.0`、Web、PostgreSQL、MinIO、Redis healthy，迁移 `0017_mistake_review`；ImageAnalysis 与 DataLifecycle worker 运行，MinIO `9000` 未发布，既有 LAN 登录回归保持有效 |
| Web 孩子账号与档案管理（当前分离流程） | 中文用户名请求头、档案选择绑定、档案 CRUD 代理和生产 Web 构建 | Web/认证或档案变更 | 通过（2026-07-17）：现有账户页可先创建/选择档案再创建账号，请求幂等键为 ASCII 随机值，代理 Content-Type 与 409 错误已覆盖；这只验证旧分离流程，不满足 PLAN-0013 的聚合创建体验 |
| Web 统一孩子管理与多孩子工作台 | 单事务创建 Profile+Account、旧数据审计/唯一约束、聚合卡、当前孩子选择、任务/周报服务端过滤、刷新/删除回退/空状态 | PLAN-0013 的 OpenAPI/API/迁移/Web 变更 | 已实现首版（API/Web/0016/Ubuntu 部署和本地回归通过；双孩子浏览器 E2E、旧数据审计/设备回归待执行） |
| 教材范围与材料知识发布 | CurriculumAssignment、PDF 文件头/大小/页数/哈希/资源上限、版权声明、解析草稿、Prompt 注入、家长审核发布、来源/版本/撤销/删除 | TODO-016 的依赖/OpenAPI/API/worker/Web/迁移变更 | 未实现（当前只有 `curriculum_version` 字符串；首批处理器/依赖和限制评审前不运行真实教材） |
| Flutter 数学三入口与错题详细讲解 | 数学 → 错题讲解/复习错题/今日任务；VerifiedQuestion + 已确认 AttemptEvidence + CurriculumSnapshot 门禁；有作答定位错步、空白从头讲；分模式 Tutor/来源/算术校验/失败恢复 | TODO-017 的 Flutter/API/Tutor/Schema 变更 | 未实现（当前仍是今日任务 + 拍题；固定 eval 必须覆盖 `worked/blank/unclear/answer_area_missing`、浅色铅笔字/擦改、人工修正、错版/超纲、来源缺失和 Provider 失败） |
| 正式错题本与到期复习 | MistakeRecord 幂等/并发/删除导出；ReviewPolicy v1、到期/全部队列、先作答、晋级/重置/重激活、时区/断网重试 | TODO-018 每次错题/复习变更 | 最小闭环已实现（0017、API 幂等/到期/复习、导出级联、Web/Flutter 调用通过；完整错题本 UI、复习 Attempt/E2E 待完成） |
| 可解释任务建议 | parent_assigned/review_due/system_suggested 来源、教材/错题引用、家长批准/拒绝、去重/每日上限、失败回滚和周报解释 | TODO-019 每次任务/推荐变更 | 未实现（首批只选已有错题/已发布练习，不自动下发 AI 新编题） |
| Flutter 实体设备相机/相册权限 | iPad 上依次验证 `拍照`、`从相册选择`、系统权限拒绝/允许和回到人工确认页 | 相机/图片输入变更 | 部分通过（2026-07-14；用户确认实体 iPad 已完成拍照、权限和回到“已选择题目照片”页；相册选择、拒绝权限和错误恢复仍待验证） |
| Flutter legacy Capture 上传 smoke | 使用合成 StudySession 和 iPad 可达 MinIO，验证旧预签名 PUT、服务端确认、OCR 入队 | 历史回归，不再作为目标发布门槛 | 通过（2026-07-14）；ADR-0018 已替代该直传目标，记录只证明 `0.8.0` 历史实现，不代表新架构验收 |
| API 流式 Capture 上传 | Session 鉴权单一上传 API；分块大小/哈希、MIME/文件头/尺寸/像素/完整解码、幂等、慢速/断连、MinIO/DB 失败补偿、staging 清理、内存/并发上限 | PLAN-0012 每次上传/API/Compose 变更 | 未实现（ADR-0018 Accepted；完成后 App 只连接 API，OpenAPI 无 `upload_url`，Compose/LAN 不发布 `9000`） |
| Web 安装 | `cd apps/web && pnpm install --frozen-lockfile` | 锁文件变化/干净环境 | 通过（2026-07-12；构建脚本白名单已审查） |
| Web 格式 | `cd apps/web && pnpm format:check` | 每次 Web 变更 | 通过（2026-07-17） |
| Web Lint | `cd apps/web && pnpm lint` | 每次 Web 变更 | 通过（2026-07-17） |
| Web 类型 | `cd apps/web && pnpm typecheck` | 每次 Web 变更 | 通过（2026-07-17） |
| Web 单元 | `cd apps/web && pnpm test` | 每次 Web 变更 | 通过（9 tests，2026-07-17；当天任务、周报、导出和既有账号/档案代理回归） |
| Web E2E | `cd apps/web && pnpm e2e` | 用户流程变更/P1 门槛 | 不可运行 |
| Web 构建 | `cd apps/web && pnpm build` | 合并前 | 通过（2026-07-17；Next 16.2.10 production build；本机 Node 20/pnpm 9 产生已知 engine warning，Ubuntu 镜像使用锁定 Node 24.18/pnpm 11.7 并构建成功） |
| API 安装 | `cd services/api && uv sync --locked` | 锁文件变化/干净环境 | 通过（2026-07-15；ARM 镜像内 `uv sync --locked --no-dev` 解析 124 个锁定包并安装 35 个适用包；macOS ARM64/Linux x86_64 保留 PaddleOCR 3.7.0、PaddlePaddle 3.3.1，Linux ARM64 按 marker 排除 Paddle；模型只在 amd64 镜像构建阶段下载） |
| API 格式 | `cd services/api && uv run ruff format --check .` | 每次 API 变更 | 通过（2026-07-17） |
| API Lint | `cd services/api && uv run ruff check .` | 每次 API 变更 | 通过（2026-07-17） |
| API 类型 | `cd services/api && uv run mypy src` | 每次 API 变更 | 通过（2026-07-17；43 source files） |
| API 单元 | `cd services/api && uv run pytest -m "not integration"` | 每次 API 变更 | 通过（157 tests，2026-07-18；新增 Mistake/Review 记录、幂等、授权、导出字段和既有高风险回归通过） |
| Compose 配置 | `docker compose -f infra/compose/compose.yml config` | Compose 变更 | 远端通过（2026-07-17，真实 `.env` 不输出）；本机因被忽略的 `.env` 不存在未运行完整展开，`.env.example` 字段已覆盖新增生命周期配置 |
| Compose 完整启动 | `docker compose -f infra/compose/compose.yml up -d --build` | API/数据/跨模块变更 | 通过（2026-07-18，Ubuntu 24.04 x86_64；`0017` 前滚，API `0.8.0`/PostgreSQL/MinIO/Redis/Web 健康，ImageAnalysis/DataLifecycle worker 运行） |
| Web 镜像 | `cd apps/web && docker buildx build --platform=linux/arm64 --load -t study-web:arm64-debug .` | Web/Compose 变更 | 通过（2026-07-15；Next.js standalone 镜像使用 Node 24.18.0、pnpm 11.7.0，包含 `/healthz`） |
| 集成环境 | `docker compose -f infra/compose/compose.yml up -d postgres minio` | API/数据/跨模块变更 | 当前通过（2026-07-13；旧配置发布 5432/9000）。PLAN-0012 目标要求 MinIO 仅在 Compose 内部网络可达，并增加宿主/LAN `9000` 不开放的断言 |
| API 集成 | `cd services/api && uv run pytest -m integration` | 跨模块/数据变更 | 通过（25 tests，2026-07-17；`0015`、TutorTurn、会话完成/周报、导出精确重放/过期清理、孩子级联删除及既有 PostgreSQL/MinIO 回归通过） |
| API 镜像 | `cd services/api && docker buildx build --platform=linux/arm64 --load -t study-api:arm64-debug .`；发布仍构建 `linux/amd64` | 合并/发布前 | ARM 本地通过（2026-07-15）；amd64 Ubuntu 远端通过（2026-07-16，构建期模型目录 26 文件/清单标记、Paddle 3.3.1 + PaddleOCR 3.7.0、容器预检 ready、内存 synthetic OCR 4/4）；运行时无模型下载 |
| AI eval | `cd services/api && ./.venv/bin/python ../../evals/run_ocr_eval.py`；`./.venv/bin/python ../../evals/run_privacy_sanitizer_eval.py`；`./.venv/bin/python ../../evals/run_tutor_policy_eval.py` | OCR/脱敏/Provider/模型路由/Tutor Policy 变更 | 通过（2026-07-17；OCR 6、PrivacySanitizer 6、offline Tutor Policy 3 cases；固定输入不含真实数据） |
| PrivacySanitizer / Tutor eval | `cd services/api && ./.venv/bin/python ../../evals/run_privacy_sanitizer_eval.py && ./.venv/bin/python ../../evals/run_tutor_policy_eval.py` | 脱敏规则/OCR/视觉检测、图片外发、Tutor Policy/Provider/Schema/路由变更 | 通过（2026-07-17）；NewAPI Adapter/live synthetic 已验证，真实自动视觉检测器仍未实现，外发继续要求手动确认 |
| OCR 真实运行时预检 | `cd services/api && ./.venv/bin/python scripts/check_ocr_runtime.py` | Ubuntu/模型镜像或 Paddle 版本变更 | 宿主 Ubuntu 24.04/x86_64 已确认；预检新增显式 `STUDY_OCR_CONTAINER_RUNTIME=true`，仅接受锁定 Debian 13 amd64 容器层，不放宽其他门禁；对应单元测试通过 |
| OCR 锁定模型 synthetic smoke | `cd services/api && ./.venv/bin/python ../../evals/run_ocr_model_eval.py` | Ubuntu/模型/Provider 变更 | 通过（2026-07-16，远端 x86_64 Debian 13 锁定容器，4/4 cases：普通文本 3、公式 1，CPU；只使用内存 synthetic 图片，无外部 Provider）；真实题型评测仍待执行 |
| NewAPI synthetic live eval | `docker compose -f infra/compose/compose.yml exec -T api python scripts/run_newapi_live_eval.py` | NewAPI key/model/网络或 worker 变更 | 上传/网络链路通过，Provider 返回 HTTP `402`（2026-07-18，Ubuntu x86_64）；已验证内部 MinIO、单 Provider 请求到达和可操作失败提示，等待 NewAPI 余额/模型额度恢复后复验 `Extraction → VerifiedQuestion → TutorTurn` |
| 备份/恢复 | `infra/compose/scripts/backup.sh`；`verify-restore.sh <backup-dir>` | 数据/迁移/发布变更 | 通过（2026-07-17，Ubuntu；PostgreSQL custom dump + MinIO 快照 + SHA-256 清单，隔离 PostgreSQL 16.10 恢复完成，18 个 public tables，MinIO 快照 36 个文件） |
| 契约结构/差异 | `ruby -ryaml -rjson -e '...'`（解析 `openapi.yaml` 与 `schemas/*.json`） | OpenAPI/Schema 变更 | 进行中（2026-07-18；OpenAPI `0.8.0` 已改为单一流式上传并移除预签名/独立确认 Schema；需补跑完整差异脚本，SDK 生成器未决定） |
| 安全扫描 | `TBD（按 Flutter/pnpm/uv/镜像工具链建立）` | 合并/发布前 | 阻塞：无依赖/镜像 |

耗时预算必须在命令首次进入 CI 后用实际数据补充，不在无代码阶段猜测。

当前环境备注：本轮用于早期验证的 `/private/tmp/study-uv/bin/uv` 已被临时目录清理；后续格式/Lint/类型/测试以 `services/api/.venv/bin/` 的同等工具入口通过。恢复可发现的 `uv` 命令由 `TODO-011` 跟踪，不应把现有 `.venv` 误报为干净环境安装验证。

## 4. 最小相关验证规则

- 文档变更：运行占位符、交叉引用、Markdown 表格和敏感信息检查；确认目标架构没有写成已实现。
- 纯函数：运行对应单元测试、格式、Lint 和类型检查。
- OpenAPI/JSON Schema：运行生成/差异、兼容性、消费者和授权测试；生成 SDK 后工作区必须无差异。
- API：运行契约、家庭授权正反向、错误映射、幂等和相关集成测试。
- 数据模型：验证扩展/迁移/收缩、旧客户端、离线事件、回滚/前滚、备份恢复、并发和索引路径。
- 离线同步：覆盖断网、进程终止、队列部分成功、重复提交、同键不同载荷、过期令牌、时钟偏差和版本冲突。
- UI：验证职责内设备、横竖屏、弱网、键盘、相机/存储权限、空/错/加载/重试和辅助功能。
- 图片脱敏/AI：固定版本评测敏感标签/手写信息/人脸/二维码/条形码漏检与误遮挡，同时确保普通数学算式/解题笔迹不被当敏感信息删除；覆盖 EXIF/缩略图/原始像素清除、实色遮挡、用户确认哈希绑定、单 Provider、临时副本删除；云视觉/Tutor 覆盖题目/作答分区、`worked/blank/unclear/answer_area_missing`、人工修正、有作答错步讲解、空白从头讲解、模式越权、完整讲解来源/校验、低置信度、Schema、Prompt 注入、敏感内容、超时/限流、降级和成本上限。
- 缺陷：先建立失败复现，再做最小修复和回归测试。

## 5. 测试矩阵（目标）

| 能力 | 单元 | 集成 | E2E/设备 | 安全 | 性能/成本 | Owner |
| --- | --- | --- | --- | --- | --- | --- |
| 家庭/账号/孩子/设备 | 账号规范化、密码策略、会话状态、权限策略、当前孩子选择优先级 | Account/AuthSession/Profile migration、聚合创建原子回滚/幂等/并发唯一、任务/周报 child 过滤、契约 | Web 首次改密、单表单创建孩子、聚合卡、两个孩子切换/刷新/删除回退、Flutter 孩子登录、iPad + Windows 共享档案 | 默认凭据限制、改密前数据阻断、枚举/爆破、Cookie/CSRF、会话撤销、跨 Household/反向孩子绑定、选择 ID 篡改与兄弟姐妹隔离 | Argon2id、聚合写入/首页加载延迟 | `TBD` |
| 教材/知识发布 | Assignment/材料/Job/Snapshot 状态机、来源 Schema | 文件验证/哈希/资源上限、解析草稿、版本/审核发布/撤销/删除、迁移 | 家长导入 synthetic PDF、校正并发布，两个孩子不同教材 | 恶意文件、版权声明、Prompt 注入、未发布/跨家庭检索、整本教材外发 | 页数/内存/处理时长、Provider 成本 | `TBD` |
| 任务/推荐/会话/Attempt | 来源/审批状态机、追加写、每日上限 | 推荐→批准→Task 事务、幂等/冲突、错题/教材引用 | 家长安排/到期复习/系统建议到完成、断网重连 | 越权、载荷篡改、AI 绕过审批/静默下发 | 队列吞吐、每日任务量/推荐成本 | `TBD` |
| Capture/PrivacySanitizer/云视觉 | 脱敏规则、Schema、置信度、哈希绑定 | Session 鉴权流式上传、元数据清除、实色遮挡、单 Provider Adapter、临时副本删除 | 四端权限、裁切、脱敏预览、手动涂抹、题目校正 | 反向越权、流式大小/类型/文件头/尺寸/哈希/断连、恶意内容、敏感信息漏检/误遮挡、原图外发、跨 Provider 广播 | 上传内存/并发、脱敏/云解析延迟和单题成本 | `TBD` |
| Tutor | guided/review/mistake_explanation Policy、提示/完整讲解、来源和确定性校验 Schema | VerifiedQuestion/AttemptEvidence/Snapshot 三重门禁、作答状态人工确认、Provider 失败/降级、审计 | 三入口下练习/复习先作答；错题有作答针对错步、空白从头讲解/变式题 | 未确认状态绕过、未入镜/浅色字迹误判空白、错版/超纲、来源缺失、计算/单位错误、文档提示注入 | token/延迟/每题和家庭预算 | `TBD` |
| 错题/复习/周报 | Mistake 状态、错因来源、ReviewPolicy/到期算法和聚合 | 幂等/并发、迁移、重算、重激活、导出/删除 | 到期/全部逐题过关、家长查看与异常说明 | 家庭隔离、答案提前泄漏、AI 改到期/掌握、删除联动 | 队列加载/周报生成时间 | `TBD` |
| 导出/删除 | 范围计算、状态机 | DB/对象/缓存/备份策略 | 家长发起到完成 | 身份确认、审计、残留扫描 | 完成时间 | `TBD` |
| 通知 | 路由和降级 | HMS/应用内适配器 | 华为/iPhone 回归 | 令牌保护、最小内容 | 发送成功率/成本 | `TBD` |

## 6. 测试数据与环境

- 默认使用合成数据；需要真实分布时只使用经批准、不可回溯且最小化的脱敏数据。
- 禁止把生产凭据、儿童身份、题目图片、家庭内容或数据库转储复制到夹具、快照、评测集和日志。
- 固定随机种子：单元/属性/AI 抽样测试必须可重放；具体种子入口由各模块配置并记录失败种子。
- 时间/时区：服务端存储 UTC；界面按家庭时区显示。测试至少覆盖 UTC、Asia/Shanghai、周界、夏令时边界（即使首版家庭不使用 DST）和客户端时钟偏差。
- 外部服务：CI 默认使用 mock/fake 或本地 MinIO/Redis/PostgreSQL；云视觉测试默认只使用 synthetic 脱敏图片和记录型 fake Adapter。真实 AI/HMS sandbox 仅在 Provider/法域/预算审批后的受控集成阶段使用，凭据、原图和真实儿童内容不进入请求或日志。
- AI eval：样本必须标注来源/授权、年级、题型、期望提示行为和禁止行为；模型输出不得反向污染金标。

## 7. CI 与发布质量门槛

- [x] 依赖按锁文件安装；格式、Lint、类型检查通过。
- [x] 最小相关测试和受影响套件通过，测试失败不能通过无解释重跑掩盖。
- [x] OpenAPI/Schema 结构检查通过，生成物无漂移；SDK 生成器仍未选择。
- [x] 现有 Household/认证/学习/Capture/Tutor/删除边界的家庭授权、幂等/离线和高风险自动测试通过；不包含 ADR-0020 新能力。
- [ ] PrivacySanitizer、用户外发确认、单 Provider、云视觉 Schema/人工确认和临时脱敏副本删除门禁通过；未实现前保持图片外发功能关闭。
- [ ] 无未批准的高危依赖/镜像/密钥扫描问题；SBOM/签名策略在生产前确定。
- [x] Android/iOS/Web/API 构建产物可生成，迁移与 PostgreSQL/MinIO 备份恢复经过验证。
- [ ] ADR-0017 认证门槛全部通过：API 认证回归、认证审计和孩子账号反向越权已通过；Web Cookie/CSRF、Flutter 安全存储真实设备生命周期、PostgreSQL 迁移往返和浏览器 E2E 仍待执行。
- [ ] ADR-0020/PLAN-0014：教材文件/Prompt 注入/草稿发布、题目+作答区解析、四态作答确认、有作答错步/空白从头讲解+知识来源门禁、正式错题/确定性复习、任务建议审批及双孩子 E2E 全部通过；当前四类能力均未实现。
- [ ] P1 核心 E2E 全通过，四类设备完成职责内弱网/横竖屏/权限回归。
- [ ] AI eval、成本告警、周报追溯和儿童数据删除有可审查记录。

## 8. 无法运行测试时

必须在 `TASK.md` 完成记录中写明：未运行的命令、阻塞原因、已完成的替代验证、残余风险和下一位执行者的精确下一步。当前 Android/iOS 本地构建均已通过，但不等同于真实设备安装、签名、权限或四设备回归验证。
