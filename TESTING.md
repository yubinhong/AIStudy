# TESTING.md

## 1. 当前状态与质量目标

当前仓库已有 P0 依赖清单、最小测试、CI 草案和三类锁文件。API 的 Household 边界/幂等切片、Web/Flutter 合同消费入口、Compose 配置以及 Flutter 格式/分析/单元测试已有本地验证；Android 调试 APK 和 iOS 无签名 Runner.app 均已构建通过。E2E/AI/契约 SDK 生成/安全扫描仍是后续入口。

- 核心用户路径：家长创建任务 → 孩子端同步 → 作答/拍题 → 本地脱敏预览与用户确认 → 单一云视觉 Provider 解析 → 题目人工校正 → 1～3 级提示 → 错题沉淀 → 离线重连 → 家长周报。
- 不可接受的失败：跨家庭越权；原图/未确认脱敏图/儿童数据/密钥泄漏；同一图片被静默发送给多个 Provider；学习记录丢失或被最后写入覆盖；AI 直接代答或错误结论静默入库；删除请求未执行却报告成功；未记录的成本失控。
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
| Flutter 格式 | `cd apps/child_flutter && dart format .` | 每次 Flutter 变更 | 通过（2026-07-15；启动过渡增量已按当前 Dart formatter 写回） |
| Flutter 静态/类型 | `cd apps/child_flutter && flutter analyze` | 每次 Flutter 变更 | 通过（无 issues，2026-07-15） |
| Flutter 单元/Widget | `cd apps/child_flutter && flutter test` | 每次 Flutter 变更 | 通过（13 tests，2026-07-15；含有限启动过渡/首页并行加载、减少动态效果跳过动画、离线队列、学习桌 UI、拍题输入示例路径、OCR 确认流程、分数思考提示流程、本地脱敏预览确认，以及 Capture 客户端 text/formula 上传、Job 轮询、候选确认/纠正链路） |
| Flutter UI 视觉 QA | 原型目标 viewport `1194 × 834` 的真实设备/截图比较 | 每次客户端 UI 原型变更 | 阻塞（2026-07-14）：实体 iPad 已成功横屏启动 Debug 应用，但 Flutter screenshot 不支持实体设备；iPad mini 模拟器仅完成 portrait smoke screenshot，详见 `design-qa.md` |
| Flutter 构建 | `cd apps/child_flutter && flutter build ios --no-codesign` 或 `flutter build apk` | 合并前/平台变更 | 通过（2026-07-14）：Flutter 3.44.6、Xcode 26.6 + iOS 26.5 runtime 生成含 `image_picker` 原生插件的无签名 `Runner.app`（20.1 MB），并已通过 Flutter tooling 重新安装到实体 iPad；此前 Android 调试 APK 为 139 MB。2026-07-13 已接受 Android 许可证，交互式 `flutter doctor -v` 全绿 |
| Flutter 实体设备相机/相册权限 | iPad 上依次验证 `拍照`、`从相册选择`、系统权限拒绝/允许和回到人工确认页 | 相机/图片输入变更 | 部分通过（2026-07-14；用户确认实体 iPad 已完成拍照、权限和回到“已选择题目照片”页；相册选择、拒绝权限和错误恢复仍待验证） |
| Flutter local Capture 上传 smoke | 使用合成 StudySession 和 iPad 可达 MinIO，验证预签名 PUT、服务端确认、OCR 入队和不展示合成候选 | Capture 客户端接线 | 通过上传/确认/入队（2026-07-14；实体 iPad API 日志为 201、201、202；Worker 结果未在当前 InMemory 队列进程中产生） |
| Web 安装 | `cd apps/web && pnpm install --frozen-lockfile` | 锁文件变化/干净环境 | 通过（2026-07-12；构建脚本白名单已审查） |
| Web 格式 | `cd apps/web && pnpm format:check` | 每次 Web 变更 | 通过（2026-07-12） |
| Web Lint | `cd apps/web && pnpm lint` | 每次 Web 变更 | 通过（2026-07-12） |
| Web 类型 | `cd apps/web && pnpm typecheck` | 每次 Web 变更 | 通过（2026-07-12） |
| Web 单元 | `cd apps/web && pnpm test` | 每次 Web 变更 | 通过（2 tests，2026-07-15） |
| Web E2E | `cd apps/web && pnpm e2e` | 用户流程变更/P1 门槛 | 不可运行 |
| Web 构建 | `cd apps/web && pnpm build` | 合并前 | 通过（2026-07-15；Next 16.2.10 production build） |
| API 安装 | `cd services/api && uv sync --locked` | 锁文件变化/干净环境 | 通过（2026-07-15；ARM 镜像内 `uv sync --locked --no-dev` 解析 124 个锁定包并安装 35 个适用包；macOS ARM64/Linux x86_64 保留 PaddleOCR 3.7.0、PaddlePaddle 3.3.1，Linux ARM64 按 marker 排除 Paddle；模型只在 amd64 镜像构建阶段下载） |
| API 格式 | `cd services/api && uv run ruff format --check .` | 每次 API 变更 | 通过（2026-07-15；85 files） |
| API Lint | `cd services/api && uv run ruff check .` | 每次 API 变更 | 通过（2026-07-15） |
| API 类型 | `cd services/api && uv run mypy src` | 每次 API 变更 | 通过（2026-07-15；37 source files） |
| API 单元 | `cd services/api && uv run pytest -m "not integration"` | 每次 API 变更 | 通过（110 tests，2026-07-15；含 Household、Bearer 令牌签名/过期/篡改、家长删除授权/幂等/失败保留、家长保存/立即删除授权与重放、任务版本、Attempt 幂等、Capture 校正、私有上传确认、实际对象 SHA-256、默认 text/按需 formula OCR 入队与 mode 幂等冲突、ImageAnalysis disabled/queued/幂等/家庭边界、提取结果仓储、NewAPI worker 默认关闭时安全空闲及 claim/complete/fail、无 Provider Tutor Policy 1～3 级提示/答案阻断及 Household/Child/Capture 校验、NewAPI 配置/响应 Schema/安全上限、Dispatcher、一次性与 watch Worker 启动/退出边界、OCR 运行时平台/版本/模型预检、锁定模型 synthetic 输入生成/匹配门禁、生命周期上限、对象级联删除成功/失败/重试、预签名 URL、对象有界读取、完整像素解码/规范化重编码/EXIF 清理、图片容器头/尺寸/像素数边界、Provider-neutral PrivacySanitizer 实色覆盖/阻断/安全边距/手动确认 Schema、OCR/规则敏感区域检测、PrivacySanitizer synthetic eval、OCR Worker 安全读取/未确认状态拒绝/失败不持久化、OCR 输出形状/置信度/人工确认/临时文件清理/未锁定模型关闭边界、文本/公式引擎实例复用、公式结果解析与临时文件执行、OCR 候选草稿状态/控制字符边界、child-only OCR 结果读取/候选确认与 Household/Child/Capture 边界、环境凭据边界、预置模型目录与构建清单边界） |
| Compose 配置 | `docker compose -f infra/compose/compose.yml config` | Compose 变更 | 通过（2026-07-15；以 `.env.example` 和 `--no-env-resolution` 静态展开 PostgreSQL、迁移、MinIO、Redis、API、家长 Web、ImageAnalysis worker 七个默认服务，profile 列表为空） |
| Compose 完整启动 | `docker compose -f infra/compose/compose.yml up -d --build` | API/数据/跨模块变更 | 待本机执行；Apple Silicon 默认使用已验证构建的原生 ARM 调试镜像，amd64 构建才下载并校验 Paddle 模型；本轮未启动持久服务或覆盖卷 |
| Web 镜像 | `cd apps/web && docker buildx build --platform=linux/arm64 --load -t study-web:arm64-debug .` | Web/Compose 变更 | 通过（2026-07-15；Next.js standalone 镜像使用 Node 24.18.0、pnpm 11.7.0，包含 `/healthz`） |
| 集成环境 | `docker compose -f infra/compose/compose.yml up -d postgres minio` | API/数据/跨模块变更 | 通过（2026-07-13；Docker Desktop 29.2.1，postgres:16.10 与 MinIO healthy，端口 5432/9000，synthetic local 配置） |
| API 集成 | `cd services/api && uv run pytest -m integration` | 跨模块/数据变更 | 通过（18 tests，2026-07-15；migration schema 含 `0007_ocr_job_mode`、`0008_image_analysis_job`、`0009_question_extraction`、Learning/Capture/OCR/ImageAnalysis ledger 持久化幂等与 mode、receipt-only blocked job、OCR 候选确认复用 CaptureCorrection 事务、PostgreSQL 行锁领取/stale lease 恢复、家长保存/立即删除图片、OCR_FAILURE 七天保留、规范化候选/空结果、家庭边界、对象键内部持久化、到期对象认领/删除审计、批次原子性、连接池重连、并发版本冲突，以及 PostgreSQL + MinIO synthetic API + Worker `queued → succeeded → candidate` 闭环） |
| API 镜像 | `cd services/api && docker buildx build --platform=linux/arm64 --load -t study-api:arm64-debug .`；发布仍构建 `linux/amd64` | 合并/发布前 | 通过（ARM：2026-07-15，镜像 `study-api:arm64-debug` 原生构建成功，锁内 35 个适用运行包不含 Paddle，未下载模型；构建后容器启动烟测未获执行。amd64：2026-07-13，镜像 `study-api:local` 的五个官方 PaddleOCR 归档均校验 SHA-256，并在无网络容器内完成 1×1 synthetic PNG 真实 CPU 烟测） |
| AI eval | `cd services/api && ./.venv/bin/python ../../evals/run_ocr_eval.py`；`./.venv/bin/python ../../evals/run_privacy_sanitizer_eval.py`；`./.venv/bin/python ../../evals/run_tutor_policy_eval.py` | OCR/脱敏/Provider/模型路由/Tutor Policy 变更 | 通过（2026-07-15；OCR 6、PrivacySanitizer 6、offline Tutor Policy 3 cases，均 0 Provider calls；云视觉 Adapter、真实检测器和云 Tutor Provider 仍未实现） |
| PrivacySanitizer / Tutor eval | `cd services/api && ./.venv/bin/python ../../evals/run_privacy_sanitizer_eval.py && ./.venv/bin/python ../../evals/run_tutor_policy_eval.py` | 脱敏规则/OCR/视觉检测、图片外发、Tutor Policy/Provider/Schema/路由变更 | 本地 PrivacySanitizer 6 cases 与 offline Tutor Policy 3 cases 通过（2026-07-15）；云视觉 Adapter、真实检测器和云视觉固定评测仍未实现 |
| OCR 真实运行时预检 | `cd services/api && ./.venv/bin/python scripts/check_ocr_runtime.py` | Ubuntu/模型镜像或 Paddle 版本变更 | 代码与 synthetic 门禁测试通过（2026-07-14）；当前 macOS 预检按预期 `blocked`，Ubuntu 24.04 CPU 实测未执行 |
| OCR 锁定模型 synthetic smoke | `cd services/api && ./.venv/bin/python ../../evals/run_ocr_model_eval.py` | Ubuntu/模型/Provider 变更 | 评测脚本与预检接线完成（2026-07-15；含普通 OCR 与按需公式 OCR case）；当前 macOS 按预期 `blocked`，未执行真实推理 |
| 契约结构/差异 | `ruby -ryaml -e '...'`（见任务记录） | OpenAPI/Schema 变更 | 通过（2026-07-15）：21 paths、34 OpenAPI schemas、6 JSON schemas；含 Bearer scheme、ImageAnalysis queued/blocked 状态、QuestionExtractionRecord 读取路径；SDK 生成器未决定 |
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
- 图片脱敏/AI：固定版本评测敏感标签/手写信息/人脸/二维码/条形码漏检与误遮挡、EXIF/缩略图/原始像素清除、实色遮挡、用户确认哈希绑定、单 Provider、临时副本删除；云视觉/Tutor 继续覆盖正确提示层级、禁止直接代答、低置信度校正、Schema 失败、Prompt 注入、敏感内容、Provider 超时/限流、降级和成本上限。
- 缺陷：先建立失败复现，再做最小修复和回归测试。

## 5. 测试矩阵（目标）

| 能力 | 单元 | 集成 | E2E/设备 | 安全 | 性能/成本 | Owner |
| --- | --- | --- | --- | --- | --- | --- |
| 家庭/账号/孩子/设备 | 账号规范化、密码策略、会话状态、权限策略 | Account/AuthSession migration、登录/改密/退出/孩子账号 API、契约 | Web 首次改密/孩子账号管理、Flutter 孩子登录、iPad + Windows 共享档案 | 默认凭据仅 loopback、改密前数据阻断、枚举/爆破、Cookie/CSRF、会话撤销、跨 Household/反向孩子绑定 | Argon2id、登录/同步延迟 | `TBD` |
| 任务/会话/Attempt | 状态机、追加写 | 事务、幂等、冲突 | 创建到完成、断网重连 | 越权、载荷篡改 | 队列吞吐 | `TBD` |
| Capture/PrivacySanitizer/云视觉 | 脱敏规则、Schema、置信度、哈希绑定 | 签名上传、元数据清除、实色遮挡、单 Provider Adapter、临时副本删除 | 四端权限、裁切、脱敏预览、手动涂抹、题目校正 | 文件类型/大小、恶意内容、敏感信息漏检/误遮挡、原图外发、跨 Provider 广播、URL | 上传/脱敏/云解析延迟和单题成本 | `TBD` |
| Tutor | Policy、提示级别、Schema | Provider 失败/降级、审计 | 完整分步提示 | 直接代答、敏感内容、提示注入 | token/延迟/家庭预算 | `TBD` |
| 错题/复习/周报 | 规则和聚合 | 数据追溯、重算 | 家长查看与异常说明 | 家庭隔离、删除联动 | 周报生成时间 | `TBD` |
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

- [ ] 依赖按锁文件安装；格式、Lint、类型检查通过。
- [ ] 最小相关测试和受影响套件通过，测试失败不能通过无解释重跑掩盖。
- [ ] OpenAPI/Schema 兼容检查通过，生成物无漂移。
- [ ] 家庭授权、幂等/离线、文件输入、AI 安全和删除路径的高风险测试通过。
- [ ] PrivacySanitizer、用户外发确认、单 Provider、云视觉 Schema/人工确认和临时脱敏副本删除门禁通过；未实现前保持图片外发功能关闭。
- [ ] 无未批准的高危依赖/镜像/密钥扫描问题；SBOM/签名策略在生产前确定。
- [ ] 构建产物可生成，迁移与备份恢复经过验证。
- [ ] ADR-0017 认证门槛通过：空库引导幂等、默认账号只允许 loopback、首次改密强制阻断、Argon2id、5 次失败锁定、统一登录错误、Web Cookie/CSRF、Flutter 安全存储、会话过期/撤销、孩子账号管理和反向越权测试。
- [ ] P1 核心 E2E 全通过，四类设备完成职责内弱网/横竖屏/权限回归。
- [ ] AI eval、成本告警、周报追溯和儿童数据删除有可审查记录。

## 8. 无法运行测试时

必须在 `TASK.md` 完成记录中写明：未运行的命令、阻塞原因、已完成的替代验证、残余风险和下一位执行者的精确下一步。当前 Android/iOS 本地构建均已通过，但不等同于真实设备安装、签名、权限或四设备回归验证。
