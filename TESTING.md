# TESTING.md

## 1. 当前状态与质量目标

当前仓库已有 P0/P1 依赖清单、三类锁文件、核心测试和 CI 草案。API 的 Household/认证/学习/Capture/可信 Tutor/周报/导出、Mistake/Review closeout、教材 PDF-only 私有原页/多模态知识图谱、作答四态/推荐审批、Web/Flutter 入口、SQLite 离线队列和 Compose 已验证；Android/iOS 构建及 PostgreSQL/MinIO 恢复已有记录。本地与 Ubuntu 目标均为 API/OpenAPI `0.13.0`/`0030`；剩余是真实 PDF/Provider、设备和最终 E2E 发布门槛。

2026-08-10 成人英语移除与 GitHub 开源整理：删除未部署的成人 Gemini Provider、家长本人实时会话授权、成人/Gemini 环境变量、直接依赖、专属测试和 ADR；孩子 REST/WebSocket、家长逐孩子设置、三情景、PCM16、播放打断、摘要/导出/删除、`0029` 表和 Flutter 页面保留。API 英语 `16 passed`，相关 Ruff、Mypy 通过；英语安全 eval `7/7`；Flutter `50 passed`、Analyze 无问题；Web `32 passed`、TypeScript、Prettier 通过，本机 Node 20.17 低于锁定 engine 并产生 warning。OpenAPI/JSON 解析及本地引用闭合通过，并修复学习记录 `422` 对不存在 `ValidationError` 的旧引用；`uv lock --check`、Compose `config --no-env-resolution`、README 本地链接、密钥特征扫描和 `git diff --check` 通过。首次并行执行 Flutter Analyze 与测试时争用启动锁并报临时目录清理错误，测试结束后单独重跑 Analyze 通过。未运行 API 全量/集成、Web build/lint、Flutter release、实体设备、Ubuntu 部署或 GitHub 推送。

2026-07-29 英语插件本地验证：OpenAPI `0.12.0` 为 60 paths、92 个唯一引用，8 个 JSON Schema 解析并闭合；Alembic 单一 head 为 `0029_english_speaking_practice`，从零及 `0028 → 0029` 静态 SQL 生成通过。API 英语/导出定向 `20 passed`，Ruff/Mypy（58 source files）通过；全量非集成为 `214 passed, 2 failed, 27 deselected`，两个失败是既有拍题 Owner 作用域与孩子删除幂等重放回归。英语安全 eval `7/7`；Flutter 格式、Analyze、全量 `50` 项、Android release（64.1 MB）与 iOS 无签名 release（24.0 MB）通过；Web `29` 项、Lint、TypeScript、Prettier 和生产构建通过，本机 Node/pnpm 低于锁定 engine 并产生 warning。真实 PostgreSQL 集成与实体设备未执行，不计为完成。

2026-07-30 学习记录本地验证：API 默认 30 天、上海单日 UTC 边界、非法/过期范围和版本定向 `9 passed`；PostgreSQL 生命周期 synthetic 集成 `1 passed`，覆盖过期无错题、已解决错题、开放错题保护和近期记录，并在测试结束清理全部 synthetic 行。Mypy 58 source files、相关 Ruff、Alembic 单一 head `0030_learning_history_retention` 及离线 SQL 通过。Web `32 passed`、Lint、TypeScript、Prettier 和生产构建通过并包含 `/learning`。API 全量非集成为 `218 passed, 2 failed, 28 deselected`，两个失败仍是上述既有回归。本机 Node 20.17/pnpm 9.10 仍低于锁定 engine。

2026-07-31 Ubuntu `0.13.0`/`0030` 发布验证：升级前备份 `/home/syin/study-backups/20260731T020739Z` 通过隔离恢复，恢复库含 32 个 public 表、MinIO 快照 359 个文件；Compose 以锁定 Node 24.18/pnpm 11.7 重建并启动 API、Web、PostgreSQL、Redis、私有 MinIO、四个常驻 worker 和一次性迁移服务。API/Web `/healthz`、Alembic current/head、OpenAPI 版本及学习详情时间参数、`0029` 英语表、`0030` 两个索引、容器内保留策略源码均通过；生命周期首轮计数全为 0，英语 Provider 保持 `disabled`，MinIO `9000` 未发布。未认证 `/learning` 返回登录跳转；登录态浏览器 E2E 仍未执行。

2026-07-28 Web 拍题聚焦与家庭权限：API 定向 `34 passed`，包含超级管理员家长列表、普通家长越权拒绝、存在所属孩子时删除冲突和可删除家长的会话/账号清理；Ruff 与 Mypy（56 source files）通过。Web `27` 项 Vitest、ESLint、TypeScript、Prettier 和生产构建通过，覆盖家庭权限 BFF 的 Cookie/CSRF 转发及 `204 No Content` 响应。本机 Node `20.17`/pnpm `9.10` 低于锁定 Node `24.18`/pnpm `11.7`，命令只作为本地验证并有 engines warning。Ubuntu 已以锁定 Node `24.18`/pnpm `11.7` 重新构建 API/Web/迁移与四个 worker；API/Web 健康、迁移 current/head 为 `0028_super_admin_ownership`、未认证家长权限 API 为 `401`、`/family` 为 `200`。仍待浏览器角色人工验收。

2026-07-29 iPad Release 覆盖安装：实体 iPad mini 6（iPad14,1）已配对、开发者模式启用。以 Flutter `3.44.6` 构建 `Runner.app`（21.2 MB），注入 `STUDY_API_URL=http://192.168.1.4:8000`；再以 Team `VZ59988J63` 的自动签名完成 Release 构建并通过 `devicectl` 覆盖安装、启动 `Study Child 0.1.0 (1)`。未读取设备账号或学习数据；登录、相机、局域网与拍题闭环仍待设备侧人工验收。

2026-07-27 客户端连接与账号显示修复：`flutter test` 43 项、`flutter analyze`、Dart 格式化和 `git diff --check` 通过；release APK 已用 `aapt` 验证包含 `android.permission.INTERNET` 与 `android:usesCleartextTraffic=true`。APK 已覆盖安装到 Nova 9（`2026-07-27 16:21:21`）并成功启动，Android 日志未见权限/明文 HTTP 拒绝；Ubuntu API 近端日志有认证和孩子档案初始化请求。仍须由设备界面确认旧会话用户名回填、账号页显示和学习桌完整加载。

2026-07-27 推荐计划日可见性修复：截图中的 `2026-08-01` 推荐不是丢失，而是未来计划被孩子端的“仅今日任务”过滤。Flutter 现在将未来最近计划只读提示、当天和过期未完成任务显示为可开始；Web 在批准后明确计划日。Flutter `45` 项/Analyze/格式通过，Web `20` 项 Vitest/类型/Lint/格式通过；Ubuntu 锁定 Node `24.18`/pnpm `11.7` 已完成 Web 重建且 `/healthz` 通过，APK 已覆盖安装 Nova 9。仍待以真实未来/逾期任务核对孩子端界面。

2026-07-27 孩子端任务入口临时隐藏、账号切换与完成返回修复：真实体验发现多计划堆叠且“开始任务”退化为通用拍题，学习桌因此不再请求或渲染任务列表。新增 Widget 回归断言“今日任务”、来源题和任务 API 请求都不存在；档案页在服务端、Session 或用户名变化时重新加载，新增 A→B→A 回归；题目完成及完整解答后通过根路由返回学习桌，新增对应回归。保留错题讲解进入拍题与独立 Tutor 练习回归。`flutter test` 45 项、`flutter analyze` 与 Dart 格式化通过；release APK 已构建，待 Nova 9 重连后安装。

2026-07-29 完整解答教材匹配降级：新增 API Tutor/NewAPI 回归，验证可靠匹配继续将知识点、目标、先修和来源页传给 Provider；未匹配的已确认题目不再返回 `409`，仅传 `curriculum_grounding=not_matched` 和空范围，返回适龄完整解答且不附教材来源。两条路径均断言不含图片。API 定向 `23 passed`、相关 Ruff、Mypy（58 source files）通过；Flutter `capture_api_client_test.dart` `15 passed`、全量 `50 passed`、Analyze、Dart 格式化和 `git diff --check` 通过。Ubuntu API/教材分析 worker 已重建，API `/healthz` healthy 且运行态确认加载该策略；修复版 iPad Release 已覆盖安装并启动。未运行真实 Provider，不计为质量验收；截图题的真实界面回归待用户操作。

同日部署复核发现首次同步的 `tutor.py` 路径错误，运行容器仍使用旧路由，导致设备日志中 L1/L2 为 `200` 而 L3 为旧 `409`。已同步到 `services/api/src/study_api/routes/tutor.py`、清除误放的未引用副本并重建 API；远端健康端点、文件检查和容器内 `inspect` 均确认新 `general-solution-policy.v1` 路由已经运行。

- 核心用户路径：家长上传清洁 PDF → 服务端私有渲染原页、分批多模态理解并归纳全书知识图谱 → 家长对照原页批准并发布 → 孩子选择数学/学习模式 → 错题安全拍摄题目+答题区 → 确认题目和作答状态 → L1 看懂题意/L2 找到方法/L3 允许时完整讲解 → 原子 MistakeRecord/ReviewSchedule → 到期或提前加载真实题目、重新作答并追加 ReviewAttempt → 家长审核由错题和已批准知识点生成、包含具体题目/视觉说明/页码/日期/时长的任务 → 孩子执行并可打开教材原页 → 周报。本地与 Ubuntu `0.13.0` 已接通代码和自动化，真实 Provider/PDF/登录态浏览器/设备 E2E 未通过前仍不能判定整条路径完成。
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
| Flutter 格式 | `cd apps/child_flutter && dart format .` | 每次 Flutter 变更 | 通过（2026-07-23；任务来源题卡与受鉴权教材原页入口已格式化） |
| Flutter 静态/类型 | `cd apps/child_flutter && flutter analyze` | 每次 Flutter 变更 | 通过（无 issues，2026-07-27） |
| Flutter 单元/Widget | `cd apps/child_flutter && flutter test` | 每次 Flutter 变更 | 通过（45 tests，2026-07-27；今日任务入口隐藏且不请求任务列表，A→B→A 切换会重新加载目标账号档案，完成题目或完整解答会回学习桌，既有认证/拍题/脱敏/提示/离线队列回归保持通过） |
| Flutter UI 视觉 QA | 原型目标 viewport `1194 × 834` 的真实设备/截图比较 | 每次客户端 UI 原型变更 | 阻塞（2026-07-14）：实体 iPad 已成功横屏启动 Debug 应用，但 Flutter screenshot 不支持实体设备；iPad mini 模拟器仅完成 portrait smoke screenshot，详见 `design-qa.md` |
| Flutter 构建 | `cd apps/child_flutter && flutter build apk --release`；`flutter build ios --release --no-codesign` | 合并前/平台变更 | 通过（2026-07-17）：Android release APK 53.8 MB，iOS release 无签名 `Runner.app` 20.9 MB；不再要求 `STUDY_CAPTURE_SESSION_ID`。Android 仍为自用 debug key 签名，正式 App ID/签名由 `TODO-013` 跟踪；iOS 提示 `flutter_secure_storage` 尚不支持 Swift Package Manager，当前 CocoaPods 构建不受影响 |
| Flutter Android 实体设备 | 在华为 Nova 9 验证 ADB 识别、登录、相机/相册权限、脱敏预览、弱网与会话重启 | Android/认证/图片输入变更 | 进行中（2026-07-17）：Nova 9 已完成登录、相机/相册选择、脱敏预览、即时拍题会话、3.09 MB MinIO 上传/确认和 ImageAnalysis 入队；首次 Provider 请求返回 `provider_http_413`，现已部署 600 KB 有界压缩并覆盖安装最终 APK，等待第二次拍题确认 Extraction/VerifiedQuestion。弱网和重启仍待验收 |
| Ubuntu API LAN 部署 | 构建并启动匹配的 API 运行目录，验证健康、迁移和 LAN 认证 | API/认证/部署变更 | 通过（2026-07-24）：rsync 保留远端 `.env`、卷和备份；隔离恢复验证后 API `0.11.0`、Web、PostgreSQL、MinIO、Redis healthy，迁移 `0025_curriculum_knowledge_map`；ImageAnalysis/DataLifecycle/MaterialParse/CurriculumAnalysis worker 运行，API/Web `/healthz` 通过 |
| Web 孩子账号与档案管理（当前分离流程） | 中文用户名请求头、档案选择绑定、档案 CRUD 代理和生产 Web 构建 | Web/认证或档案变更 | 通过（2026-07-17）：现有账户页可先创建/选择档案再创建账号，请求幂等键为 ASCII 随机值，代理 Content-Type 与 409 错误已覆盖；这只验证旧分离流程，不满足 PLAN-0013 的聚合创建体验 |
| Web 统一孩子管理与多孩子工作台 | 单事务创建 Profile+Account、旧数据审计/唯一约束、聚合卡、当前孩子选择、任务/周报服务端过滤、刷新/删除回退/空状态 | PLAN-0013 的 OpenAPI/API/迁移/Web 变更 | 通过（2026-07-23）：后台方案 1、顶层孩子切换、三项顶层侧栏、双孩子作用域、逐题详情及 1214×805 同尺寸截图对照；真实 PostgreSQL 浏览器 E2E/设备回归仍待执行 |
| 教材范围与多模态知识发布 | Web/OpenAPI/API PDF-only、非 PDF 稳定拒绝；授权/无个人信息声明、SHA-256、隔离 worker、逐页私有 JPEG、每批最多 4 页视觉理解、全书知识图谱、缺页/伪造来源拒绝、家长原页审核批准、并行多教材发布、删除及 Prompt 注入 | PLAN-0018、ADR-0021/0023、OpenAPI/API/Web/Flutter/迁移变更 | 通过（2026-07-27）：Provider/解析/上传定向、完整 API 非集成、Ruff、Mypy 56 source files、契约结构、Web `tsc`/20 项 Vitest/格式/Lint、迁移离线 SQL 通过（本机 Node 20 仅产生 engines warning）。覆盖 PDF 标题待识别/本地封面回填/家长覆盖、页级稀疏目标、临时 `5xx` 三次有界重试、空知识点章节、非数组可选引用、超长引用截断、过滤缺少学习目标的点和虚构页拒绝；两份已发布教材保持独立及推荐聚合两份批准图谱回归。Ubuntu `0026` 已在 quiesced 备份后前滚，API/Web healthcheck 通过、汇总为两份 published；真实教材/费用/重试和浏览器/设备 E2E 待执行 |
| Flutter 数学三入口与错题详细讲解 | 数学 → 错题讲解/复习错题/今日任务；视觉四态候选与人工校正；按 `worked/blank` 分支，`unclear/answer_area_missing` 阻断；完整步骤/答案/验算 | TODO-017 的 Flutter/API/Tutor/Schema 变更 | 代码与自动化通过（2026-07-23：未到期错题自动回退到全部列表，今日任务显示所有当天来源题/页码；客户端+Widget 定向 29 tests、analyze 通过）；真实设备相机/复习/多任务仍待人工复验 |
| 正式错题本与到期复习 | closeout 原子/唯一/失败文案、历史候选；实际 VerifiedQuestion、ReviewAttempt、服务端判定、ReviewPolicy v2、到期/全部队列、晋级/重置/重激活、时区/断网重试 | PLAN-0016 M1/M2 每次错题/复习变更 | `0021` closeout、题目回读、ReviewAttempt、服务端答案判定和 1/3/7/14/30 策略已通过 API 全量测试；真实设备/并发及时区 E2E 待执行 |
| Tutor L1/L2 渐进提示 | L1 看懂题意/定位疑点；L2 builds-on L1 并增加方法脚手架；worked/blank/review 分支、答案泄露、重复、题意相关、降级和交互状态 | PLAN-0017 的 Policy/API/Flutter/eval 变更 | 通过（2026-07-23：NewAPI L1/L2 路由、builds-on、答案/重复/题意门禁、同时经过时间回退和 5-case synthetic eval；Tutor/推荐定向 30 tests）；真实 Provider 质量验收待执行 |
| PDF 智能任务推荐 | 遍历全部开放错题和已批准教材知识点/练习；错题频次/到期/知识点关联；具体教材题/视觉说明/页码/原页；来源键校验；每日上限；家长批准后 Web/Flutter 同源展示 | PLAN-0017/0018、ADR-0022/0023、OpenAPI/迁移/三端变更 | Ubuntu `0.11.0` 代码通过：推荐路径不再读取 `CurriculumChunk.text` 抽题，未知知识点/练习来源整体拒绝，孩子 Session 原页读取和 2 MiB/JPEG 客户端门禁已覆盖；真实 PDF/NewAPI、浏览器 E2E、AI 成本审计和设备待执行 |
| 可解释任务建议 | 到期错题/已批准教材具体题与来源、错题—知识点关联、家长批准/拒绝、去重、批准后 Task、每日上限和失败回滚 | TODO-019 / PLAN-0018 每次任务/推荐变更 | 本地已实现全量错题/已批准知识图谱排序、具体题、视觉说明、页码/原页、7 天日期、预计时长、每日 3 项上限和未知来源整体拒绝；真实 PDF/NewAPI/最终 E2E 未执行 |
| Flutter 实体设备相机/相册权限 | iPad 上依次验证 `拍照`、`从相册选择`、系统权限拒绝/允许、上传进度态和回到人工确认页 | 相机/图片输入变更 | 部分通过（2026-07-20）：iPad mini 6 已由 Flutter 工具重新安装、热重启，启动健康检查到达 API 并返回 200；用户已触发真实拍照、脱敏、上传和识别流程，并发现的 PNG 体积膨胀问题已加入 7.5 MB 有界重编码修复；修复后的完整上传与人工确认仍需设备点击复验 |
| Flutter iOS 本地网络 | 声明本地网络用途、仅允许局域网 ATS，真机允许/拒绝权限并验证 LAN API 请求 | iOS/LAN API 变更 | 阻塞于设备网络（2026-07-20）：`Info.plist` 与编译产物包含 `NSLocalNetworkUsageDescription`/`NSAllowsLocalNetworking`；精确卸载 Bundle 后重新安装，登录页真实 `/healthz` 返回 `errno 65: No route to host`，API 无入站。iPhone Safari 对跨网段 Ubuntu 和同网段 Mac 临时端口均无入站，指向 iPhone 权限/VPN/网络过滤或 Wi-Fi 客户端隔离；临时端口/RVI 已关闭，服务端和 Mac 访问健康。 |
| Flutter legacy Capture 上传 smoke | 使用合成 StudySession 和 iPad 可达 MinIO，验证旧预签名 PUT、服务端确认、OCR 入队 | 历史回归，不再作为目标发布门槛 | 通过（2026-07-14）；ADR-0018 已替代该直传目标，记录只证明 `0.8.0` 历史实现，不代表新架构验收 |
| API 流式 Capture 上传 | Session 鉴权单一上传 API；分块大小/哈希、MIME/文件头/尺寸/像素/完整解码、幂等、慢速/断连、MinIO/DB 失败补偿、staging 清理、内存/并发上限 | PLAN-0012 每次上传/API/Compose 变更 | 首版已实现并在本地/Ubuntu 部署；断连/超限/超时现场压测和真机回归待执行 |
| Web 安装 | `cd apps/web && pnpm install --frozen-lockfile` | 锁文件变化/干净环境 | 通过（2026-07-12；构建脚本白名单已审查） |
| Web 格式 | `cd apps/web && pnpm format:check` | 每次 Web 变更 | 通过（2026-07-30；学习记录页、表格和日期工具经 Prettier 复核） |
| Web Lint | `cd apps/web && pnpm lint` | 每次 Web 变更 | 通过（2026-07-30） |
| Web 类型 | `cd apps/web && pnpm typecheck` | 每次 Web 变更 | 通过（2026-07-30） |
| Web 单元 | `cd apps/web && pnpm test` | 每次 Web 变更 | 通过（2026-07-30：32 项；新增上海自然日/180 天边界和学习导航覆盖） |
| Web E2E | `cd apps/web && pnpm e2e` | 用户流程变更/P1 门槛 | 不可运行 |
| Web 构建 | `cd apps/web && pnpm build` | 合并前 | 通过（2026-07-30；Next 16.2.10 production build包含动态 `/learning`；本机 Node 20.17/pnpm 9.10 产生 engine warning，锁定容器仍使用 Node 24.18/pnpm 11.7） |
| API 安装 | `cd services/api && uv sync --locked` | 锁文件变化/干净环境 | 通过（2026-07-15；ARM 镜像内 `uv sync --locked --no-dev` 解析 124 个锁定包并安装 35 个适用包；macOS ARM64/Linux x86_64 保留 PaddleOCR 3.7.0、PaddlePaddle 3.3.1，Linux ARM64 按 marker 排除 Paddle；模型只在 amd64 镜像构建阶段下载） |
| API 格式 | `cd services/api && uv run ruff format --check .` | 每次 API 变更 | 本轮 13 个教材知识图谱相关文件通过；全仓仍有此前 4 个迁移文件需统一格式化，不在本轮顺手修改 |
| API Lint | `cd services/api && uv run ruff check .` | 每次 API 变更 | `src tests scripts` 与 `0025` 迁移通过（2026-07-23）；全仓命令仍报告 `0018/0020/0021/0023` 历史行宽/导入格式问题 |
| API 类型 | `cd services/api && uv run mypy src` | 每次 API 变更 | 通过（2026-07-30；58 source files） |
| API 单元 | `cd services/api && uv run pytest -m "not integration"` | 每次 API 变更 | 部分通过（2026-07-30：`218 passed, 2 failed, 28 deselected`；失败仍是本轮前已记录的拍题 Owner 作用域和孩子删除幂等重放，学习记录定向 9 项通过）。 |
| Compose 配置 | `docker compose -f infra/compose/compose.yml config` | Compose 变更 | 通过（2026-07-31，Ubuntu 实际 `infra/compose/.env` 展开无错误；权限保持 600） |
| Compose 完整启动 | `docker compose -f infra/compose/compose.yml up -d --build` | API/数据/跨模块变更 | 通过（2026-07-31，Ubuntu 24.04 x86_64；API `0.13.0`、Web、ImageAnalysis/DataLifecycle/MaterialParse/CurriculumAnalysis worker 重建运行，迁移 `0030`，API/Web healthcheck 通过；PostgreSQL/MinIO/Redis 数据卷保留） |
| Web 镜像 | `cd apps/web && docker buildx build --platform=linux/arm64 --load -t study-web:arm64-debug .` | Web/Compose 变更 | 通过（2026-07-15；Next.js standalone 镜像使用 Node 24.18.0、pnpm 11.7.0，包含 `/healthz`；2026-07-20 Ubuntu 重建验证教材上传幂等键兼容修复） |
| 集成环境 | `docker compose -f infra/compose/compose.yml up -d postgres minio` | API/数据/跨模块变更 | 当前通过（2026-07-13；旧配置发布 5432/9000）。PLAN-0012 目标要求 MinIO 仅在 Compose 内部网络可达，并增加宿主/LAN `9000` 不开放的断言 |
| API 集成 | `cd services/api && uv run pytest -m integration` | 跨模块/数据变更 | 本轮相关通过（2026-07-30：学习历史生命周期 1 项，独立 synthetic 行覆盖开放错题保护并全部清理；未运行其余集成套件） |
| API 镜像 | `cd services/api && docker buildx build --platform=linux/arm64 --load -t study-api:arm64-debug .`；发布仍构建 `linux/amd64` | 合并/发布前 | ARM 本地通过（2026-07-15）；amd64 Ubuntu 远端通过（2026-07-16，构建期模型目录 26 文件/清单标记、Paddle 3.3.1 + PaddleOCR 3.7.0、容器预检 ready、内存 synthetic OCR 4/4）；运行时无模型下载 |
| AI eval | `cd services/api && ./.venv/bin/python ../../evals/run_ocr_eval.py`；`./.venv/bin/python ../../evals/run_privacy_sanitizer_eval.py`；`./.venv/bin/python ../../evals/run_tutor_policy_eval.py` | OCR/脱敏/Provider/模型路由/Tutor Policy 变更 | Tutor 通过（2026-07-23；offline Tutor Policy 5 cases，新增同时经过时间 L1/L2，固定输入不含真实数据）；OCR/PrivacySanitizer 最近结果仍为 2026-07-17 |
| PrivacySanitizer / Tutor eval | `cd services/api && ./.venv/bin/python ../../evals/run_privacy_sanitizer_eval.py && ./.venv/bin/python ../../evals/run_tutor_policy_eval.py` | 脱敏规则/OCR/视觉检测、图片外发、Tutor Policy/Provider/Schema/路由变更 | 通过（2026-07-17）；NewAPI Adapter/live synthetic 已验证，真实自动视觉检测器仍未实现，外发继续要求手动确认 |
| 英语口语安全 eval | `services/api/.venv/bin/python evals/run_english_conversation_safety_eval.py` | 英语 Policy、Provider 或控制合同变更 | 通过（2026-07-29；7/7，个人信息、成人/危险话题、中文兜底和回答长度；真实 Provider 质量/成本另行评测） |
| OCR 真实运行时预检 | `cd services/api && ./.venv/bin/python scripts/check_ocr_runtime.py` | Ubuntu/模型镜像或 Paddle 版本变更 | 宿主 Ubuntu 24.04/x86_64 已确认；预检新增显式 `STUDY_OCR_CONTAINER_RUNTIME=true`，仅接受锁定 Debian 13 amd64 容器层，不放宽其他门禁；对应单元测试通过 |
| OCR 锁定模型 synthetic smoke | `cd services/api && ./.venv/bin/python ../../evals/run_ocr_model_eval.py` | Ubuntu/模型/Provider 变更 | 通过（2026-07-16，远端 x86_64 Debian 13 锁定容器，4/4 cases：普通文本 3、公式 1，CPU；只使用内存 synthetic 图片，无外部 Provider）；真实题型评测仍待执行 |
| NewAPI synthetic live eval | `docker compose -f infra/compose/compose.yml exec -T api python scripts/run_newapi_live_eval.py` | NewAPI key/model/网络或 worker 变更 | 通过（2026-07-20，Ubuntu x86_64）：纯合成题仅传确认文字，返回 3 个完整步骤、答案 17 只和独立验算；实际拍题四态仍待设备人工验收 |
| 备份/恢复 | `infra/compose/scripts/backup.sh`；`verify-restore.sh <backup-dir>` | 数据/迁移/发布变更 | 通过（2026-07-17，Ubuntu；PostgreSQL custom dump + MinIO 快照 + SHA-256 清单，隔离 PostgreSQL 16.10 恢复完成，18 个 public tables，MinIO 快照 36 个文件） |
| 契约结构/差异 | 结构化解析 `openapi.yaml` 与 `schemas/*.json` 并闭合本地引用 | OpenAPI/Schema 变更 | 通过（2026-07-30；OpenAPI `0.13.0` 可解析，学习详情时间参数与 180 天描述已同步；SDK 生成器仍未决定） |
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
| 教材/知识发布 | Assignment/MaterialParseJob/Chunk/PageAsset/PageAnalysis/KnowledgeMap/KnowledgePoint/Snapshot 状态机、页码/练习来源 Schema | 文字/扫描/图形/加密/损坏/超限 PDF；私有页图、4 页批次、全书归纳、缺页/伪造来源、扩展名/MIME/文件头/结构/哈希/对象展开/CPU/内存/超时；非 PDF 拒绝；批准/发布/撤销/删除/迁移 | 家长导入 synthetic PDF、对照原页批准知识图谱并发布，两个孩子不同教材；讲解/推荐/孩子任务打开原页 | 危险动作/链接/附件、解析器出网、版权/无个人信息声明、Prompt 注入、页图单 Provider、未批准/跨家庭、PDF/对象键外发 | 页数/预览大小/整本输入、内存/时长、队列、token/延迟和 Provider 成本 | `TBD` |
| 任务/推荐/会话/Attempt | 来源/审批状态机、追加写、每日上限 | 推荐→批准→Task 事务、幂等/冲突、错题/教材引用 | 家长安排/到期复习/系统建议到完成、断网重连 | 越权、载荷篡改、AI 绕过审批/静默下发 | 队列吞吐、每日任务量/推荐成本 | `TBD` |
| Capture/PrivacySanitizer/云视觉 | 脱敏规则、Schema、置信度、哈希绑定 | Session 鉴权流式上传、元数据清除、实色遮挡、单 Provider Adapter、临时副本删除 | 四端权限、裁切、脱敏预览、手动涂抹、题目校正 | 反向越权、流式大小/类型/文件头/尺寸/哈希/断连、恶意内容、敏感信息漏检/误遮挡、原图外发、跨 Provider 广播 | 上传内存/并发、脱敏/云解析延迟和单题成本 | `TBD` |
| Tutor | guided/review/mistake_explanation Policy、L1/L2/L3 披露、builds-on、来源和确定性校验 Schema | VerifiedQuestion/AttemptEvidence/Snapshot 三重门禁、层级连续/披露差异、Provider 失败/降级、审计 | worked/blank/review 分支；L1 看懂题意、L2 方法脚手架、允许时 L3 完整讲解 | L1/L2 换词重复/答案泄露、未确认状态绕过、错版/超纲、来源缺失、计算/单位错误、文档提示注入 | token/延迟/每级/每题和家庭预算 | `TBD` |
| 错题/复习/周报 | closeout、Mistake 状态、ReviewAttempt、ReviewPolicy/到期算法和聚合 | 原子/幂等/并发、历史候选、迁移、服务端判定、重算/重激活、导出/删除 | 拍题进入错题；到期/全部显示题目、重新作答、逐题过关；家长查看 | 批量误判 Capture、家庭隔离、客户端伪造正确、答案提前泄漏、AI 改到期/掌握、删除联动 | 队列加载/判定/周报时间 | `TBD` |
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
- [ ] PLAN-0016/0017/0018：本地与 Ubuntu `0.11.0`/`0025` 代码/部署门槛已通过；仍需真实 118 页 PDF/NewAPI、固定 Tutor/教材 eval、成本审计、双孩子/设备/E2E、删除和发布安全门槛。
- [ ] P1 核心 E2E 全通过，四类设备完成职责内弱网/横竖屏/权限回归。
- [ ] AI eval、成本告警、周报追溯和儿童数据删除有可审查记录。

## 8. 无法运行测试时

必须在 `TASK.md` 完成记录中写明：未运行的命令、阻塞原因、已完成的替代验证、残余风险和下一位执行者的精确下一步。当前 Android/iOS 本地构建均已通过，但不等同于真实设备安装、签名、权限或四设备回归验证。
