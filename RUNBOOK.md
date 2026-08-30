# RUNBOOK.md

## 1. 服务概览

- 服务：家庭 AI 学习助手（目标包括 Flutter 孩子端、Web/PWA、FastAPI/Worker、PostgreSQL、Redis、S3/MinIO 和 AI Provider）。
- 当前状态：`SELF_HOSTED_DEPLOYED`。Ubuntu 24.04 x86_64 VM `192.168.1.4` 正运行自用 Compose `0.17.1`/`0038_classical_poem_options`；API/Web/worker 健康，已审核语文教材只保留标题、连续诗句和全部选项均通过确定性目录的六首 21 道古诗题。没有 staging/production、Dashboard 或日志平台，本 Runbook 仍不构成生产部署批准。`ADR-0008` 已 Accepted。
- Owner/值班：`TBD（项目 Owner/运维负责人在 staging 前确认）`。
- 用户影响：服务中断会阻止同步、拍题、AI 提示和周报；孩子端必须保留离线任务/作答，不能因服务中断丢学习记录。
- 外部依赖：单一获批云视觉 Provider、Tutor Provider、可选本地 Qwen 模型镜像/权重、HMS（或应用内提醒）和对象存储；具体云供应商 `TBD`。本地 OCR 仅是目标 PrivacySanitizer 的隐私检测依赖，不是外部 Provider。
- Dashboard/日志/Trace：目标为 OpenTelemetry 接入批准的可观测平台；链接和查询 `TBD`。

### 2026-08-29 古诗题库门禁部署记录

- 备份：首次 `/home/syin/study-backups/20260829T070622Z` 隔离恢复为 39 张 PostgreSQL public 表和 534 个 MinIO 文件；发现旧干扰项后再次创建 `/home/syin/study-backups/20260829T220038Z`，隔离恢复为 39 张 public 表和 528 个 MinIO 文件。旧源码分别保存在 `/home/syin/study-source-backups/20260829T072000Z` 与 `/home/syin/study-source-backups/20260829T220500Z`。
- 发布：保留 `.env` 和数据卷，白名单同步 API/契约/`0037`/`0038`，以 legacy builder 构建同一 API 镜像供 API、迁移和四个 worker 使用；两次均停止全部写入端后执行事务迁移，再按 `--no-deps --force-recreate` 切换运行容器。
- 数据：`0037` 将 178 道 approved 古诗题收敛为六首 21 道，其他 157 道标记 `retired`；`0038` 将保留题中的 42 个童谣干扰项替换为目录内古诗句。Attempt/Review 全程均为 1，未删除教材、审核或学习事实。
- 运行：API `0.17.1`、Alembic `0038_classical_poem_options`、API/Web `/healthz`、四个 worker、`classical-poem-catalog.v2`、页级 Prompt v4 和 MinIO 无宿主端口均通过。Nova 9 覆盖安装保留登录态，迁移后 12 轮抽查覆盖全部六首，题干/下一句/全部选项正确且未提交作答。
- 回滚：可以恢复旧 API 镜像/源码，但不得 downgrade `0037`/`0038` 或重新批准已退役题/童谣选项；未知古诗和非目录选项继续失败关闭，扩展目录必须前向提交、测试和审核。数据库/对象恢复仅在确认数据损坏时使用上述已验证备份。

### 2026-08-30 家长首页简化部署记录

- 备份：`/home/syin/study-backups/20260830T004506Z`；隔离恢复验证为 39 张 PostgreSQL public 表、528 个 MinIO 文件。同步前源码回滚包位于 `/home/syin/study-source-backups/20260830T004632Z`。
- 发布：仅同步首页、学习历史日期工具、Web BFF 和当前状态文档共 12 个受控文件；保留远端 `.env`、数据卷和其他源码。Docker BuildKit 因 Docker Hub IPv6 token 超时未替换运行容器，随后使用 legacy builder 和本地缓存成功构建 `study-local-web:latest`，再以 `--no-deps --force-recreate` 重建 Web。
- 运行：API `0.17.1`、Web `/healthz` 均返回 `200`，全部 Compose 服务 running；`page.tsx`、`household-data.ts` 和 `learning-history.ts` 的远端 SHA-256 与本地一致。未执行真实账号浏览器或设备回归。
- 数据：用户确认两个孩子后，使用 `/home/syin/study-backups/20260830T004506Z`（已隔离恢复验证）执行有界事务清理。删除两名孩子的任务/会话/Attempt、Capture 及 23 个已登记私有对象、语文 Attempt/Review、错题/复习/推荐、Tutor/视觉/OCR/看图写话记录、导出快照和关联幂等记录；全部目标历史表为 0。保留 2 个 ChildProfile、3 个 Account、3 份教材、3 个 CurriculumSnapshot、184 条已审核 ChineseContentItem、设备设置和 149 条 AuditEvent。孤立且无法关联目标 Capture 行的对象未递归删除。
- 复核：API `0.17.1`、Web `/healthz`、全部 Compose 服务和 Alembic `0038_classical_poem_options` 均恢复正常；MinIO `captures/` 前缀聚合对象数为 0，`curriculum/` 前缀保留 3 个对象。删除不可通过代码回滚，需在确认数据损坏时从上述备份恢复并接受备份时点数据覆盖。
- 回滚：Web 可恢复源码回滚包并重建旧镜像；数据删除不依赖代码回滚，使用已验证备份恢复。

### 2026-08-25 语文教材分析修复部署记录

- 来源：先定向同步本地工作区中的 `newapi_provider.py`、`curriculum_knowledge.py` 与 `curriculum_analysis_jobs.py`，保留远端 `.env`、数据卷和其他源码。阶段源码备份位于 `/home/syin/study-source-backups/20260825T142000Z`、`20260825T143000Z` 和 `20260825T145000Z`；最终以 GitHub 提交固化并成对重建 API/worker。
- 备份：`/home/syin/study-backups/20260825T141449Z`；第一次 `verify-restore.sh` 的临时 PostgreSQL 容器在 ready 后关停导致 `pg_restore` 失败，正式数据库未受影响；确认宿主磁盘/内存正常后复跑通过，结果为 `postgres_public_tables=39`、`minio_snapshot_files=363`。
- 发布：先停止 CurriculumAnalysis worker。BuildKit 在请求 Docker Hub frontend token 时遇到 IPv6 超时且没有替换运行容器；改用 `DOCKER_BUILDKIT=0` 和本地缓存成功构建 API/worker，再以 `--no-deps --force-recreate` 重新创建两者。
- 运行修复：页级 Prompt `chinese-curriculum-page-visual.v3` 固定可选观察结构；四页请求遇到 `provider_http_413` 时只在同一 Provider 内递归二分，单页 413 保持失败；整书 Prompt `chinese-curriculum-book-consolidation.v3` 禁止 Provider 已出现的章节替代字段。固定 Schema、引用校验和家长批准门禁不变。
- 真实作业：运维显式重排既有失败作业，不读取或记录 Provider 原始响应和教材正文。第 3 次尝试完成页级分析后暴露整书字段漂移；修复后第 4 次完成 `118/118` 页并停在 `needs_review`，数据库计数为 10 个章节、12 个 draft 知识点、38 条古诗边界证据、无错误码。
- 后续审核事实：2026-08-26 最终部署后只读复核显示知识图谱和 12 个知识点均为 `approved`；该状态来自部署之外的审核操作，worker 的解析完成路径仍只写入 `needs_review`/`draft`，没有自动批准。
- 验收：API `0.17.0` 与 Web LAN `/healthz`、Alembic `0036` current/head、运行时 `provider=newapi enabled=True`、全部 Compose 服务、MinIO `HostConfig.PortBindings={}`、远端/容器源码 SHA-256、两个 v3 Prompt 和作业计数通过；新容器日志无启动或 Schema 错误。
- 未执行：token/费用基线、正式版权/教研签核、Ubuntu 真实账号浏览器和设备验收。数据库批准事实不得扩展描述为这些独立门槛已经通过。

### 2026-08-23 部署记录

- 来源：部署动作先使用本地未提交工作区，随后以提交和 tag `v0.17.0` 固化并推送；远端运行目录为 `/home/syin/study`。
- 备份：`/home/syin/study-backups/20260823T030248Z`；`verify-restore.sh` 报告 `postgres_public_tables=39`、`minio_snapshot_files=359`。
- 发布：保留远端 `.env` 和数据卷，只同步 Git 跟踪文件及本轮新增运行时文件；`docker compose config`、`DOCKER_BUILDKIT=0 docker compose up -d --build` 和 Alembic `0035 -> 0036` 均成功。
- 验收：API/Web `/healthz`、OpenAPI `0.17.0`（68 paths）、Alembic `0036`、四个 worker、容器内源码哈希和局域网 `192.168.1.4:8000/3000` smoke 均通过；MinIO `HostConfig.PortBindings={}`，没有发布 `9000`。
- 未执行：真实 Provider/PDF 质量评测、Ubuntu 真实账号浏览器、Nova 9/iPad/Windows/iPhone 真机 E2E；这些不能由本次服务端部署代替。

## 2. SLO 与关键指标

SLO 必须在 staging 获得基线后由产品/技术 Owner 批准，不在零代码阶段编造。

| 指标 | 目标 | 告警阈值 | 当前状态 |
| --- | --- | --- | --- |
| API 可用性 | `TBD` | `TBD` | Ubuntu 自用健康检查存在，无 SLO 基线 |
| 任务/会话 API 延迟 | `TBD` | `TBD` | 无正式基线 |
| 本地脱敏/云视觉解析/首个 Tutor 提示延迟 | `TBD` | `TBD` | NewAPI synthetic 已通过，无真实家庭基线 |
| 错误率 | `TBD` | `TBD` | 无正式基线 |
| 离线同步冲突/失败 | 不得丢失或覆盖学习记录 | 阈值 `TBD`；任何确认的数据丢失立即升级 | 无实现 |
| AI Schema/安全失败 | 阻断不合规响应 | 阈值 `TBD`；无错题门禁直接代答、错误完整讲解或敏感泄露立即升级 | 本地 5-case Tutor eval 与来源键推荐回归已通过；真实 Provider 基线未建立 |
| AI 成本 | 每家庭/请求预算 `TBD` | 超批准预算即告警/降级 | 无成本数据 |
| 导出/删除/备份失败 | 0 个静默失败 | 任一超时或错误立即告警 | 导出/删除/备份恢复已实现；180 天详细历史清理输出计数，自动告警未接入 |

## 3. 环境与部署

GitHub Actions Android APK 构建、稳定签名 Secret、Artifact 校验/安装、首次自托管部署和外部教材工具的完整操作入口见 [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md)。本 Runbook 继续作为运行态、迁移、备份、故障处置和回滚的事实来源。

### 当前环境

- local：`infra/compose/compose.yml` 已编排 PostgreSQL、Redis、MinIO、API、家长 Web、一次性 Alembic migration、AI worker 和可切换的 llama.cpp/Qwen 本地模型服务；Apple Silicon `linux/arm64` 调试镜像构建成功。`STUDY_LOCAL_MODEL_ENABLED=false` 时本地模型容器保持空闲，路由读取 NewAPI；设置为 `true` 时所有当前 AI 请求只走 Compose 内部本地模型，模型缓存写入独立持久卷且不发布推理端口。
- Ubuntu 自用验收：宿主为 Ubuntu 24.04/x86_64、12 GB 内存/8 核，远端 `infra/compose/.env` 权限 600。2026-08-24 备份 `/home/syin/study-backups/20260824T024445Z` 已隔离恢复验证 39 张 PostgreSQL public 表和 353 个 MinIO 文件；API/OpenAPI `0.17.0`、迁移 `0036_task_session_progress`、PostgreSQL、MinIO、Redis、Web 和四个 worker 健康。Qwen3.5-4B Q4_K_M 在 4 核下视觉 synthetic 600 秒内不收敛，8 核下耗时 373.128 秒且生成到 2048 token 上限后仍因 Schema 无效失败；当前 `STUDY_LOCAL_MODEL_ENABLED=false`、模型容器已停止并保留缓存，运行态选择 `newapi`。回退后 synthetic 数学文本 Schema smoke 3.591 秒通过，宿主约 10 GiB available、Swap 为 0；真实 PDF、账号浏览器和设备未验证。
- 真机拍题当前事实：API/Flutter/Compose/Ubuntu 已切换为 App 携带 Session 向 API 上传，且 Compose 不发布 MinIO `9000`。最新 iPad Release `Runner.app` 已安装到无线设备 `00008110-0011356E0E41801E`，但 iOS 首次启动要求用户在“设置 → 通用 → VPN 与设备管理”显式信任开发者 Team `VZ59988J63`；信任后仍需执行拍题、权限、弱网和重启验收。Provider HTTP `402` 只表示 NewAPI 余额/模型额度不可用，不应误判为上传或 MinIO 故障。
- staging：未建立。
- production：未建立且未获部署授权。

### 账号密码认证切换（ADR-0017；代码已实现，环境验收待执行）

自用首次启动和迁移按以下顺序执行；`0011_account_password_session` 已提供 migration/API。项目 Owner 已授权首次引导可从受信家庭局域网完成，首次改密和真实设备验收仍需执行：

1. 应用 Account/AuthSession 前滚迁移；仅当账号表为空时创建一次性 `admin/admin123456`，确认数据库只含 Argon2id 哈希且 `must_change_password=true`。首次引导仅限受信家庭局域网，禁止公网暴露。
2. 从受信 LAN 设备登录，验证除当前账号、改密和退出外的家庭数据接口均返回 `password_change_required`；立即修改管理员密码。
3. 确认所有引导会话已撤销，新会话可读取同一 Household 数据；禁止让默认密码继续有效。
4. 在 Web 创建孩子账号并绑定 ChildProfile；验证孩子只能访问自己的任务/会话，不能访问家长管理接口或兄弟孩子数据。
5. 验证登出、改密、停用、重置和 30 天到期均能撤销会话；验证 Web Cookie/CSRF、Flutter 登录前服务端地址配置和 Keychain/Android Keystore 生命周期。
6. 唯一管理员忘记密码时当前仅允许服务器本机维护人员按恢复方案处理；正式受审计恢复命令仍待实现，不提供短信、邮箱或 MFA 恢复。

回滚时优先前滚修复；确需回退时只回退应用镜像并保留 `0012`～`0019` 数据表，不执行生产 downgrade，不删除 Profile/Device/Account/AuthSession/TutorTurn/Export 或恢复已撤销会话。迁移前备份必须保留到新版本验收完成；恢复验证脚本不得对运行中数据库执行。

### 统一孩子管理迁移（PLAN-0013 / ADR-0019 Proposed；首版已实施）

实施前先对 `accounts` 与 `child_profiles` 做只读基数审计，分别统计无账号档案、一对一绑定和同档案多账号；报告只使用 UUID/计数，不打印用户名或儿童姓名。发现重复绑定时停止自动迁移，由项目 Owner 选择保留的账号并显式处理其余账号/会话，不得静默删除。

发布顺序为：备份 → 数据审计/处置 → 部署扩展后的数据库约束与 API 聚合合同 → 运行原子创建/授权 smoke → 部署匹配 Web → 用两个 synthetic 孩子验证切换、刷新和删除回退 → 收缩旧 Web 分离创建入口。数据库继续保留 `accounts`/`child_profiles` 两表，应用回滚不得重新允许同档案多账号。该首版流程已在 Ubuntu 完成前滚，隔离 Chromium 双孩子创建/切换已通过；Ubuntu 真实账号/PostgreSQL 浏览器仍待执行。

### 教材驱动错题闭环与智能推荐发布（ADR-0020/0022；PLAN-0016/0017）

按独立特性开关和里程碑发布，禁止一次性开放全部目标能力：

1. 先备份 PostgreSQL/MinIO，并接受 ADR-0021、锁定 PDF 解析依赖、许可证/SBOM、无网络 worker、PDF 对象展开/CPU/内存/超时上限和原文保留；先成对部署 Web/OpenAPI/API 的 PDF-only allowlist，确认 Word/PPT/Excel 新上传被稳定拒绝。
2. 部署新增迁移和 API/解析 worker，但保持解析开关关闭；依次用 synthetic 文本/扫描/加密/损坏/超限/危险 PDF 验证状态机、隔离、重试、删除和恢复，再开放家长预览/审核发布。既有非 PDF 对象不得进入回填队列。
3. 独立部署错题 closeout 与 ReviewAttempt/ReviewPolicy v2：先验证同一 Session 重试只产生一条错题、失败不显示成功、历史只生成证据完整候选；再验证到期/全部真实题目、服务端判定、`1/3/7/14/30`、并发/断网/时区后开放复习入口。
4. 部署 Tutor Hint Schema/Policy 和匹配 Flutter；固定题集证明 L2 绑定 L1、增加方法脚手架且 L1/L2 不泄露答案。Provider/完整讲解仍须通过四态、worked/blank、来源和确定性校验。
5. 只有已发布教材的来源回看和跨孩子授权通过后才开启 Tutor grounding；TaskRecommendation 最后接入已审核页级题目/知识点，继续默认家长审批，AI 新编题保持关闭。
6. 部署 `0024_intelligent_recommendations` 前再次备份并记录 `alembic current`；按“migration → API/worker → Web → Flutter”成对前滚。2026-07-23 已完成本轮 rsync、Compose 重建、远端 Alembic `current/head` 校验和 API/Web 健康校验；后续仍需用 synthetic/真实受控数据确认旧 Task/Recommendation 可读、新推荐只引用允许的 source key、到期错题排当天、每日不超过 3 项、批准后 Task 保留具体题/页码/日期/时长。
7. 打开真实 NewAPI 规划前，先用非儿童 synthetic 题和教材验证 L1/L2 相关性、来源键拒绝、超时/Schema 失败、请求量和费用；真实孩子数据验收只发送已确认题目文字和有界教材候选，不发送图片/PDF/对象键。
8. `0025_curriculum_knowledge_map` 已于 2026-07-24 前滚：先完成 `/home/syin/study-backups/20260724T015356Z` 的 quiesced PostgreSQL/MinIO 备份和隔离恢复，再部署匹配 API/Web/五个 worker；API `0.11.0`、迁移头、健康端点、私有 MinIO 边界及教材分析/原页 OpenAPI 路径通过。仍须用不含个人信息的 synthetic 图文 PDF 验证私有原页与页码一致、每批最多 4 页、缺页/伪造页码/伪造练习键整体拒绝、token/延迟/成本可见、删除同时清理 `curriculum/` 和 `curriculum-previews/`；随后才可进行真实教材和 Flutter 原页人工验收。
9. `0026_parallel_curriculum` 已于 2026-07-27 前滚：先完成 `/home/syin/study-backups/20260727T065635Z` 的 quiesced PostgreSQL/MinIO 备份；迁移只将旧自动替换逻辑写入的 `rejected` 教材快照恢复为 `published`，不删除或改写内容。Alembic revision ID 必须不超过现有 `alembic_version.version_num varchar(32)`；本轮超长 ID 的首次尝试在提交版本号前整体事务回滚，无数据变化，已改用短 ID 后重试成功。迁移后 API/Web healthcheck 通过，远端教材状态汇总为两份 `published`；发布新教材后应再次确认旧教材仍可查看且推荐来源保持各自 `snapshot_id`。
9. 真实教材只允许上传家庭有权使用的清洁电子版，家长必须确认文件不含儿童姓名、个人批注或其他个人信息。`curriculum-analysis-worker` 会把页级派生图发送给配置的单一 NewAPI Provider；未确认 Provider 数据条款、预算、模型上下文和留存策略前，保持 `STUDY_NEWAPI_ENABLED=false`，不得用真实教材试跑。

回滚只停止 `curriculum-analysis-worker`，关闭 `material_parsing/curriculum_knowledge_map/curriculum_grounding/mistake_closeout/review_v2/progressive_hints/task_recommendation_sources` 对应能力并回退匹配应用，不破坏性 downgrade 或删除已发布 Snapshot、已批准 KnowledgeMap、Mistake、Attempt/ReviewAttempt、Review/审批事实。Provider 或解析器不可用时保留私有原 PDF/原页、手工教材、既有讲解和确定性复习事实；解析草稿/索引可重算，发布/学习事实不可覆盖，也不得恢复从残缺页级文字抽题。

### 自用 NewAPI 启用流程

默认 `STUDY_NEWAPI_ENABLED=false`，此时图片分析只记录 `provider_not_enabled` 的 blocked 回执，worker 保持空闲，不读图片、不出网。自用部署者在本机 NewAPI 已可达并确认模型支持视觉后，注入对应环境变量，再重启 API 和 worker：

```bash
export STUDY_NEWAPI_ENABLED=true
export STUDY_NEWAPI_BASE_URL=http://127.0.0.1:3000
export STUDY_NEWAPI_API_KEY="<local-newapi-key>"
export STUDY_NEWAPI_VISION_MODEL="<vision-model>"
export STUDY_NEWAPI_USER_AGENT="study-api/0.5"
cd services/api
uv run python scripts/run_image_analysis_worker.py --watch
uv run python scripts/run_curriculum_analysis_worker.py --watch
```

启用前先用 synthetic 图片验证 NewAPI 返回 `question-extraction.v1`，再用 synthetic 图文教材验证 `curriculum-page-analysis.v1` 与 `curriculum-book-analysis.v1`；教材 Provider 会依次尝试 `json_schema`、`json_object`、无 `response_format` 以兼容网关，但无论采用哪种格式均必须在服务端通过固定 Schema。页级 Prompt `curriculum-page-visual.v5` 仅将明确的中英文难度同义标签、0–100/百分比置信度标度和同页章节标题归一化；页级观察可省略无法可靠判断的学习目标，最终整书知识点仍严格要求目标，其他字段错误仍拒绝。整书 Prompt `curriculum-book-consolidation.v5` 允许封面/目录/过渡章节为空，把非数组可选引用收敛为空、过滤缺少非空目标的知识点，并将超过既有 Schema 上限的章节、知识点、目标、先修项和练习引用截为有界前缀；至少一个最终知识点、其目标、页码和练习来源校验仍不可省略。单次请求只对 `429`、`5xx`、网络错误和超时按 1 秒、2 秒退避，最多三次；最终失败留在可见状态，须由家长明确重新理解。默认 `STUDY_NEWAPI_USER_AGENT=study-api/0.5`，用于兼容会拦截 Python 默认 `urllib` 签名的前置网关。该值只能是 1–256 个可打印 ASCII 字符，禁止换行或其他控制字符。worker 的失败只写稳定错误码和 Schema 字段路径及截断计数，原始 Provider 请求/响应、教材文字和页图不写日志。发现外发范围、模型行为或成本异常时，立即将 `STUDY_NEWAPI_ENABLED=false` 并停止两个 Provider worker；已入队任务不会在关闭开关后继续被新 worker 领取。

### 自用本地 Qwen 启用流程（ADR-0028）

在 `infra/compose/.env` 设置：

```dotenv
STUDY_LOCAL_MODEL_ENABLED=true
STUDY_LOCAL_MODEL_NAME=Qwen3.5-4B-Q4_K_M
STUDY_LOCAL_MODEL_HF_REPO=bjivanovich/Qwen3.5-4B-Vision-GGUF
STUDY_LOCAL_MODEL_MODEL_FILE=Qwen3.5-4B.Q4_K_M.gguf
STUDY_LOCAL_MODEL_MMPROJ_FILE=Qwen3.5-4B.BF16-mmproj.gguf
STUDY_LOCAL_MODEL_BASE_URL=http://local-model:8080/v1
```

执行 `docker compose -f infra/compose/compose.yml up -d local-model api image-analysis-worker curriculum-analysis-worker`，等待 `local-model` 健康后再运行不含儿童数据的 text/vision/schema smoke。开启后不要同时把真实请求送往 NewAPI；本地服务或模型不可用时不会自动云端回退。恢复云端路径时把开关改为 `false`，配置并验证 `STUDY_NEWAPI_*`，再重启 API 和两个 AI worker。本机 Linux ARM64 已完成镜像、权重/projector 下载和 synthetic smoke；Ubuntu 12 GB/8 核视觉质量门禁已失败，重新选型并通过固定 Schema eval 前不得重新启用当前模型。GGUF 来源/许可证和镜像摘要仍需最终核对。

### 生产前置检查

- [ ] CI、契约、测试、AI eval、安全扫描和四设备回归通过。
- [ ] 版本化产物、配置清单、迁移、容量、功能开关、模型/Prompt/Policy 版本已审查。
- [x] 备份、隔离恢复演练和数据导出/删除已验证；成本和安全告警仍未接入。
- [ ] 适用法域、儿童隐私、保留期限、Owner/值班和安全联系渠道已批准。
- [ ] ADR-0017 环境验收：代码及隔离 Chromium 已验证首次改密阻断、会话轮换/撤销、Web Cookie/CSRF、跨家庭角色和双孩子；Ubuntu 真实账号/PostgreSQL 浏览器及真实设备验证后才能勾选。
- [x] 自用 NewAPI 的 URL、API key、视觉模型、响应 Schema、停用开关和 synthetic 大图联调已验证；PrivacySanitizer/用户确认/临时副本删除 eval 已通过。
- [ ] ADR-0028 本地 Qwen：Ubuntu 已完成首次下载、health/models、文本 JSON、路由、内存和私有端口核验；`question-extraction.v1` synthetic 大图在 600 秒内不收敛，视觉质量门禁失败。模型来源最终核对、chat template/Schema 修复、固定质量评测和真实设备回归尚未完成。
- [ ] ADR-0018 上传收敛：本地与 Ubuntu OpenAPI/Flutter/API/Compose 已切换为单一有界流式上传；公开 MinIO 配置和 `9000` 映射已删除，相关本地回归及远端端口复核通过；断连/超限/超时/并发现场压测和真机验证待执行。
- [ ] ADR-0019/PLAN-0013：孩子聚合原子创建/幂等/唯一约束、孩子选择/服务端过滤、反向授权和 API/Web 成对部署已通过；隔离 Chromium 双孩子已通过，旧数据审计、真实 PostgreSQL 浏览器和设备回归仍待执行。
- [ ] PLAN-0016/0017/0018、ADR-0021/0022/0023：Ubuntu 已实施 `0.11.0`/`0025` 的 PDF-only、错题 closeout/ReviewAttempt、私有原页、多模态知识图谱、家长批准、批准知识点推荐和孩子端原页入口，并完成备份恢复、迁移头、健康和私有端口烟雾。仍须完成真实 Provider/PDF/iPad/浏览器验收、个人信息门禁及 AI 成本观测后才可勾选。
- [ ] 发布、停止、回滚和前滚负责人明确，真实数据不来自开发环境。

### 本地/自用 Compose 流程

```bash
cp infra/compose/.env.example infra/compose/.env
openssl rand -hex 32
docker compose -f infra/compose/compose.yml config
docker compose -f infra/compose/compose.yml up -d --build
docker compose -f infra/compose/compose.yml ps
curl http://127.0.0.1:${WEB_PORT:-3000}/healthz
```

ImageAnalysis 和 DataLifecycle worker 是默认服务；NewAPI 关闭时前者安全空闲，后者继续执行到期对象/导出及 ADR-0026 的 180 天详细学习历史清理。清理按有界批次删除不再被开放错题引用的 VerifiedQuestion/TutorTurn 和已结束复习链路，完成日志只记录三类删除计数。若范围异常，设置 `LEARNING_HISTORY_CLEANUP_ENABLED=false` 并重启该 worker；不要手工删除开放错题。Apple Silicon 原生 Linux ARM 调试镜像不包含 PaddlePaddle 3.3.1；需要旧完整 Paddle 路线时使用 macOS 原生进程或 `linux/amd64` 镜像。完整变量、迁移、备份、恢复验证、停止和回滚见 `infra/compose/README.md`。Compose 使用持久卷；任何时候都不得把 `down -v` 当作备份或正式删除。日志/遥测、定时异机备份、告警和静态加密仍需补齐。

以下命令只运行 ADR-0012 下已经实现的本地完整 OCR synthetic 路线，用于兼容/回滚验证；它不实现 ADR-0015，也不会向云端发送图片。API 与旧 OCR Worker 要共享 Job 状态时，必须显式启用 PostgreSQL Learning/Capture、Job 和结果仓储；Worker 需要五个带构建期 SHA-256 标记的模型目录、PostgreSQL、MinIO 配置：

```bash
cd services/api
STUDY_API_LEARNING_REPOSITORY=postgres \
STUDY_API_OCR_QUEUE=postgres \
STUDY_API_OCR_RESULTS=postgres \
uv run uvicorn study_api.main:app --host 0.0.0.0 --port 8000

# One job:
STUDY_API_OCR_QUEUE=postgres uv run python scripts/run_ocr_worker.py

# Continuous local polling:
STUDY_API_OCR_QUEUE=postgres OCR_WORKER_POLL_INTERVAL_SECONDS=2 \
uv run python scripts/run_ocr_worker.py --watch
```

一次性命令只处理一个任务；`idle` 和 `succeeded` 返回 0，OCR 失败返回 1，启动配置错误返回 2。队列请求默认使用普通 text OCR；只有显式提交 `{"mode":"formula"}` 才调用本地公式模型。`--watch` 会持续轮询 PostgreSQL 队列，Ctrl-C 后关闭资源并返回最近状态；当前未定义进程管理、Redis Worker 或生产告警。

### staging/production 部署

```text
TBD：当前提供已验证的单家庭自托管 Compose；公网暴露、CI/CD、定时异机备份、监控和多环境发布流程尚未决定。
```

未获用户明确授权不得部署、修改云资源、迁移生产数据或发送外部通知。

## 4. 部署后验证（目标）

1. 验证版本、配置、迁移状态和依赖健康，不打印密钥。
2. 使用合成监控家庭验证家长登录/改密/退出、孩子账号创建/停用/重置、孩子登录、会话撤销、孩子档案、任务同步和会话开始；确认默认引导凭据和改密前会话不能读取家庭数据。
3. 验证一次离线作答重连、幂等重复提交和同步冲突路径。
4. 使用 synthetic 图片验证 Session 鉴权的 API 有界流式上传、大小/类型/文件头/尺寸/哈希、断连清理、本地脱敏/手动涂抹/用户确认、单 Provider 云视觉结构化、题目校正、临时副本删除、Tutor Schema/Policy 和成本记录；确认 App 不连接 MinIO，Provider 请求不含原图、MinIO URL、对象键或敏感 OCR 文本。
5. 验证错题/周报追溯、应用内提醒降级和导出/删除测试流程。
6. 检查授权异常、错误率、延迟、队列、AI 安全/成本、对象删除和备份指标。

具体烟雾测试命令 `TBD（P0/P1 实现时建立）`。

## 5. 回滚与前滚

英语口语紧急关闭：将 `STUDY_ENGLISH_LIVE_ENABLED=false`、`STUDY_ENGLISH_LIVE_PROVIDER=disabled` 后重启 API。不得改为 `fake` 维持用户流量；保留 `english_practice_settings` 和 `english_practice_sessions` 摘要用于家庭导出与审计，不做数据库 downgrade。Ubuntu 已部署供应商中立框架和 `0029` 表，但 2026-07-31 运行态确认开关为关闭、Provider 为 `disabled`，没有真实语音 Provider 流量。

- 触发条件：跨家庭越权、学习记录丢失/覆盖、迁移破坏、AI 安全阻断失败、Restricted 数据泄漏、删除错误、错误率/成本超过批准阈值。
- 功能降级顺序：关闭云视觉图片外发 → 降级为重新裁剪/手工录入或显式本地 OCR 回滚 Provider → 关闭受影响 Tutor 模型/Policy → 关闭拍题/Tutor/通知/周报等独立开关 → 回退应用版本 → 隔离写入。任何降级都不得发送原图或自动广播给其他 Provider。
- 应用回滚：部署平台与命令 `TBD`。必须回退到已验证版本，并保持客户端/契约兼容。
- 数据策略：优先向前修复；只有已验证无数据损失且符合迁移契约时才回滚。Attempt/AuditEvent 不做破坏性覆盖。
- 离线兼容：回滚版本仍须接受或明确拒绝已发放客户端的版本化事件，不能让队列永久卡死。
- 验证：重跑部署后烟雾、授权、幂等/同步、AI 安全和数据追溯；确认告警恢复且无新增丢失。

## 6. 常见告警与处置框架

### 家庭授权异常

- 含义：跨 Household 访问尝试或本不应成功的授权路径。
- 首先检查：版本/配置变更、actor/device/household 不可逆标识、路由和策略版本；不得查看无关原始儿童数据。
- 临时缓解：撤销会话/设备、关闭受影响接口或回退；确认成功越权时按 Critical 事件处理。
- 升级：任一确认的跨家庭成功访问立即升级安全 Owner。

### 离线同步冲突或失败激增

- 含义：设备队列无法清空、重复副作用或版本冲突超基线。
- 首先检查：Schema/客户端版本、幂等存储、数据库错误、队列积压和最近迁移。
- 临时缓解：停止破坏性状态写入，保留追加事件和客户端队列；不得要求用户清空应用数据。
- 升级：任何学习记录丢失/覆盖立即按高严重度事件处理。

### AI Schema/安全/成本异常

- 含义：模型输出不符合契约、Tutor Policy 阻断率变化、练习/复习直接代答、错题完整讲解错误或成本超限。
- 首先检查：Provider/model、Prompt/Policy/Schema 版本、路由、延迟/token/成本和最近开关。
- 临时缓解：切回已验证版本/低风险模型，收紧提示或暂停 AI；保留任务与手工学习路径。
- 升级：敏感泄漏、对儿童有害输出或预算失控立即升级产品/安全/技术 Owner。

### 图片脱敏或外发门禁异常

- 含义：原图/未确认副本可能外发、敏感信息漏检、遮挡可逆、同一图片跨 Provider 发送或临时副本未按期删除。
- 首先检查：Capture/脱敏副本不可逆标识、sanitizer/rule/schema 版本、用户确认哈希、Provider 路由、请求摘要和删除状态；不得查看或复制无关原图/敏感 OCR 文本。
- 临时缓解：立即关闭云视觉外发开关，撤销 Provider 凭据，阻止待发队列并保留最小审计证据；学习流程降级为手工录入。
- 升级：任一确认的原图/身份外发、跨 Provider 广播或删除失败按 Restricted 数据事件升级安全/法务/产品/技术 Owner。

### 导出/删除/备份失败

- 含义：数据生命周期或恢复能力未达到承诺。
- 首先检查：任务状态、对象/数据库/缓存/备份范围、权限和审计关联。
- 临时缓解：停止报告“完成”，阻止进一步自动清理造成证据丢失，人工跟踪受影响请求。
- 升级：超批准时限或遗漏 Restricted 数据立即升级安全/法务 Owner。

## 7. 事故响应

1. 确认影响、严重度、开始时间、家庭/设备/版本范围，避免复制原始敏感数据。
2. 优先止损：撤销凭据、关闭功能/Provider、隔离写入或回退；不在事故中做无关重构。
3. 保留最小必要日志、指标、变更和操作证据；不得删除审计或擅自对外通知。
4. 状态更新间隔 `TBD（值班制度建立前建议高严重度不超过 30 分钟，但需 Owner 批准）`。
5. 恢复后验证核心学习、授权、离线、AI 和数据生命周期路径。
6. 建立复盘、回归测试、TODO/ADR，并更新 `SECURITY.md`、本 Runbook 和告警。

## 8. 灾难恢复

- RPO：`TBD（生产前批准）`。
- RTO：`TBD（生产前批准）`。
- 备份位置/加密/权限：`TBD（部署平台确定后记录，不在仓库写密钥）`。
- 恢复流程：目标为在隔离环境恢复 PostgreSQL、对象引用和必要配置，验证家庭边界、事件完整性、对象可用性和删除策略后才切流。
- 演练频率：`TBD`；staging 上线前至少完成一次端到端恢复演练，production 后按批准频率重复。
- Redis 和端侧 SQLite 不作为服务端灾难恢复事实源；Redis 可重建，端侧未同步队列需在恢复后兼容接收。

## 9. Runbook 完成条件

在 staging/production 建立后，本文件必须补齐实际 Owner、平台、Dashboard、日志查询、SLO/告警阈值、部署/回滚命令、RPO/RTO、备份位置和演练记录。任何一项仍为 `TBD` 时，不得宣称具备生产运维能力。
