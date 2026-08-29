# PLANS.md — PLAN-0035 古诗题库确定性门禁与真机修复

## 计划元数据

- 计划 ID：`PLAN-0035`
- 关联：`TASK-0012`、`PLAN-0033`、`ADR-0027`
- 状态：`IN_PROGRESS`
- 优先级：`P0 / CHINESE / CHILD CONTENT / RELEASE`
- Owner：Codex（实现与发布）；项目 Owner（Nova 9 现场验收）
- 创建：`2026-08-29`

## 目标、边界与里程碑

修复 Nova 9“古诗抽查”把《剪窗花》等儿歌、童谣和现代韵文当作古诗的问题。Provider 的宽泛 `poem` 分类只能作为候选，服务端必须用版本化、可测试的公共领域古诗标题与连续诗句签名做确定性门禁；未识别候选失败关闭，不进入孩子题库。对同一教材重新发布时先将旧派生古诗题前向退役，再只重建通过门禁的题目；保留既有 Attempt、Review 和教材审核事实，不删除学习记录。本计划包含用户明确要求的 Ubuntu 部署、Nova 9 实机验证、提交、tag 和 GitHub 推送。

- [x] M1 — 复现截图与 Ubuntu 题库，确认错误候选、有效古诗和历史引用范围。
- [x] M2 — 实现古诗签名门禁、Provider 提示收窄、同教材派生题重建和 `0037` 前向退役迁移。
- [x] M3 — API 单元/集成、迁移、Ruff、Mypy、Flutter 回归和契约/版本门槛通过；本机无 PostgreSQL，真实迁移和历史引用验证在 Ubuntu 完成。
- [x] M4 — Ubuntu 备份恢复、迁移、重建、健康、运行源码和真实题库只读验收通过：157 道错误题退役，保留六首古诗 21 道，Attempt/Review 均保持 1。
- [ ] M5 — Nova 9 登录态实际多次进入古诗抽查，只出现通过门禁的古诗；完成文档、提交、`v0.17.1` tag、GitHub 推送和 Release/CI 核验。

## 回滚与风险

应用回滚时保留 `0037` 已退役状态和所有学习事实，以前向修复恢复；不得重新启用未验证候选。签名目录初期只覆盖已审核的公共领域古诗，未知但可能正确的古诗会失败关闭，后续必须通过内容审核和回归测试扩展，不能改回相信模型标签。Ubuntu 数据变更前执行 PostgreSQL/MinIO 备份与隔离恢复；设备验收不提交作答，避免制造学习记录。

---

# PLANS.md — PLAN-0034 本地 Qwen 模型部署与 Provider 路由

## 计划元数据

- 计划 ID：`PLAN-0034`
- 关联：`TASK-0012`、`ADR-0004`、`ADR-0015`、`ADR-0028`
- 状态：`COMPLETE（本地路由与 Ubuntu 部署完成；视觉质量门禁未通过，继续作为发布后风险跟踪）`
- 优先级：`P0 / LOCAL AI / DEPLOYMENT`
- Owner：Codex（实现）；项目 Owner（本地模型来源、硬件质量和启用验收）
- 创建：`2026-08-23`

## 目标、边界与里程碑

在现有 Provider Adapter 和 Compose 内增加 Qwen3.5-4B Q4_K_M 本地多模态服务。`STUDY_LOCAL_MODEL_ENABLED=true` 时 API、ImageAnalysis worker 和 CurriculumAnalysis worker 只能访问本地模型；关闭时继续读取现有 NewAPI 云端配置。保持题目确认、教材审核、Tutor Policy、固定 Schema 和单 Provider 约束；本计划包含项目 Owner 于 2026-08-24 明确授权的 Ubuntu 自用部署，不包含真实儿童数据验收。

- [x] M1 — 核对 NewAPI Adapter 的全部文本/视觉调用入口，确认统一配置可覆盖 API、ImageAnalysis worker、CurriculumAnalysis worker。
- [x] M2 — 增加 Compose `local-model`、Q4_K_M GGUF/视觉 projector 配置、内部健康检查和持久模型缓存；关闭时容器空闲。
- [x] M3 — 增加本地开关优先级、实际 provider/model 记录和本地/云端路由回归测试。
- [x] M4 — 完成 Compose 配置校验、API 定向测试、静态质量门槛和差异审查；本机 Linux ARM64 已完成模型下载与 synthetic text/vision/schema smoke，目标 Ubuntu 硬件质量评测仍需部署者执行。
- [x] M5 — 在 12 GB/4 核 Ubuntu 完成发布前备份与隔离恢复、白名单同步、模型下载、迁移、health/models、文本 JSON smoke、Provider 选择、私有端口和常驻内存核验。
- [ ] M6 — Ubuntu `question-extraction.v1` synthetic 大图在 12 GB/4 核下 600 秒内未收敛；升级到 8 核后耗时 373.128 秒，但生成到 2048 token 上限后仍因 Schema 无效失败。视觉质量门禁未通过，需按 `docs/local-qwen-evaluation-report-2026-08-24.md` 重新选型；真实 PDF、真实设备和儿童数据均未测试。

## 回滚与风险

设置 `STUDY_LOCAL_MODEL_ENABLED=false` 并重启 API、ImageAnalysis worker 和 CurriculumAnalysis worker 即可恢复云端路径；不自动回退、不删除模型缓存、学习事实或数据库。本地请求有 600 秒、2048 输出 token 和单次尝试上限，失败保持可见。默认 GGUF/镜像来自外部仓库，首次下载和质量/许可证/供应链验证不得被本地代码测试替代。

---

# PLANS.md — PLAN-0033 古诗抽查与看图写话

## 计划元数据

- 计划 ID：`PLAN-0033`
- 关联：`TASK-0012`、`PLAN-0032`、`ADR-0015`、`ADR-0027`
- 状态：`IN_PROGRESS`
- 优先级：`P0 / CHINESE / CHILD SAFETY`
- Owner：Codex（实现）；项目 Owner（2026-08-16 明确授权儿童图片 Provider 与公开教材跨家庭复用）
- 创建：`2026-08-16`

## 目标、边界与里程碑

孩子端语文入口只保留“古诗抽查”和“看图写话”。现有原创演示内容通过前向迁移退役而不删除其 Attempt/Review。古诗只从家庭上传、已声明授权、已完成语文分析且由家长审核发布的教材页中提取；每一首诗保存标题、页码、逐行文本、来源哈希和审核状态，孩子每次只取得一个相邻诗句选择题。错误结果返回正确下一句并进入既有确定性 Review 队列。

看图写话使用独立会话，不把照片当数学题目或把 AI 输出当作文答案。照片继续经过现有元数据清除、敏感区域处理和用户确认；仅确认后的派生图可交给单一已启用 Provider。Provider 只能返回场景观察、三个启发问题和句式支架，不能生成完整作文、评价儿童外貌或推断身份。Provider 未启用、低置信或安全门禁失败时明确阻断并允许孩子改拍或从观察问题开始。

- [x] M1 — 退役六项演示内容；新增家庭范围古诗表、来源/审核字段、相邻诗句题和确定性评分/复习。
- [x] M2 — 语文教材页分析扩展为私有逐行古诗提取；家长审核/发布后才进入题库，且不跨家庭泄露。
- [x] M3 — 看图写话的独立 `picture_writing` 会话、脱敏确认图、`picture-writing-guide.v1` 场景观察结果表与“观察-说一句-补细节”引导；不调用数学题目提取链路。
- [x] M4 — Flutter 只显示古诗抽查与看图写话，古诗先均匀抽取诗目再选择相邻下一句，错误显示正确下一句；自动化覆盖古诗选择与看图写话入口。
- [x] M5a — 本机 PostgreSQL 前滚后的古诗并发 Attempt/Review/导出集成已通过；本轮完整 PostgreSQL 矩阵为 `32 passed`。
- [x] M5a-followup — 语文教材批准自动生成古诗选择题的 API 回归、Web 语文审核动作、看图写话空句阻断与安全通用降级已通过；API 非集成 `244 passed`、Flutter `70 passed`、Web `35 passed`。
- [x] M5a-release — 2026-08-23 将未提交的 `0.17.0/0036` 工作区前向部署 Ubuntu；备份隔离恢复、Compose 重建、迁移、OpenAPI、健康、worker、源码哈希、MinIO 私有端口和局域网 smoke 均通过。随后已提交、推送并创建 `v0.17.0`。
- [ ] M5b — 真实 Provider、Nova 9 相机/相册授权、弱网和登录态设备验收仍待执行；OpenAPI/API/Flutter 静态验证已完成。

## 回滚与风险

应用回滚仅隐藏入口和停止新会话，保留诗库、审核事实、Attempt、Review 和图片生命周期记录；不做数据库 downgrade。`is_public_reusable` 或“公开教材”声明不是版权许可的替代，缺少可追溯授权或审核时不得发布。真实 Provider、教材质量和实体设备验收另行记录，自动测试不能替代。

---

# PLANS.md — PLAN-0032 语文完整 MVP 与证据化验收

## 计划元数据

- 计划 ID：`PLAN-0032`
- 关联：`TASK-0012`、`PLAN-0030`、`ADR-0027`、`docs/deep-research-report.md`
- 状态：`IN_PROGRESS`
- 优先级：`P0 / CHINESE CONTENT / REVIEW / CURRICULUM`
- Owner：Codex（实现）；项目 Owner（教研、版权与设备现场验收）
- 创建：`2026-08-16`

## 边界与里程碑

本计划扩展语文确定性内容、复习和家长可解释报告，并为私有语文教材建立独立的分析版本。所有新增公共内容必须是项目原创或具备明确授权；代码可保存审核人、审核时间和权利凭证摘要，但不得编造真实教研/版权通过记录。上传教材继续只在家庭私有边界内处理，页图只给单一获批 Provider。

- [x] M1a — 内容台账门禁代码和拼音、字词、古诗文八类技能的确定性题型 golden scorer 覆盖已完成；待审核原创内容不会进入孩子题库。
- [ ] M1b — 具名教研/版权审核和权利凭证摘要仍待项目 Owner 记录；代码不能代替正式签核。
- [x] M2 — 按到期日读取语文复习项，孩子端以同一内容版本重做；家长获得按技能聚合、可追溯的报告。
- [x] M3 — 语文教材分析 `v2`：独立 schema/prompt、页级证据/篇章边界和家长审核；禁止复用数学提示。
- [x] M4a — 本机 PostgreSQL、Web Chromium 和 Flutter 自动验收已通过；任务入口/指定题目上下文、窄屏按钮布局、同一会话多题串行执行和幂等跳过状态也有 Flutter/API 回归覆盖。
- [x] M4b-code — 语文首页固定为古诗抽查/看图写话两项；数学任务题号由端侧 SQLite 持久化，确认作答、任务完成和跳过可在断网时进入结构化队列，并在联网后先批量同步 Attempt 再按顺序幂等重放终态；服务端拒绝重复启动活动任务；Flutter 全量回归 `67 passed`。
- [ ] M4b — iPad mini 6、Windows、iPhone 11、Nova 9 的登录、横竖屏、弱网和权限结果必须由实际设备记录；本轮按要求未连接设备。

## 回滚与风险

应用回滚隐藏新语文入口和候选内容，保留 Attempt、Review、审核事实和新迁移结构；不做数据库 downgrade。没有具名审核和权利凭证的内容保持不可发布，设备 E2E 不能由模拟器、截图或浏览器自动测试替代。

---

# PLANS.md — PLAN-0031 登录态浏览器 E2E

## 计划元数据

- 计划 ID：`PLAN-0031`
- 关联：`TASK-0012`、`PLAN-0007`、`ADR-0017`、`ADR-0019`
- 状态：`COMPLETE（本地 Chromium E2E 及 CI 门槛已实现并通过）`
- 优先级：`P0 / AUTH / BROWSER E2E`
- Owner：Codex（执行）；项目 Owner（2026-08-16 明确要求继续实现）
- 创建/更新：`2026-08-16`

## 目标与边界

建立可在本机和 GitHub Actions 重复运行的 Chromium E2E，以隔离的内存 API 和 synthetic 账号验证真实 Next.js 浏览器链路。覆盖未登录重定向、一次性管理员首次改密、HttpOnly Session/SameSite Cookie、CSRF 拒绝、会话轮换与退出撤销、超级管理员开通独立家庭、普通家长角色可见性、双孩子聚合创建、`math/chinese` 学科差异和当前孩子切换。

本计划不读取或写入 Ubuntu 家庭数据库，不记录浏览器 Cookie、原始 Session 或明文运行时密码，不验证真实 Provider/PDF/设备，也不增加免登录、测试 Header 或固定生产凭据。PostgreSQL 会话持久化继续由现有 API 集成测试覆盖；浏览器层使用进程隔离的内存仓储确保每次运行可重复且无儿童数据残留。

## 依赖与实施

- `@playwright/test` 固定为 `1.61.1`，Apache-2.0、Microsoft 维护，仅用于开发/CI；不进入客户端运行 bundle。相较人工浏览器验收可稳定覆盖 Cookie、CSRF、重定向和多账号流程；相较再引入 Cypress，Playwright 原生支持多 Web Server、浏览器上下文隔离和失败 Trace，依赖面更小。
- [x] M1 — 增加 Playwright 配置、忽略失败产物和标准 `test:e2e`/浏览器安装命令。
- [x] M2 — 启动隔离 API/Next，验证首次登录、改密前数据阻断、Cookie/CSRF、会话轮换、退出和撤销。
- [x] M3 — 验证超级管理员创建新家庭、普通家长首次改密、角色导航、双孩子创建及学科/切换作用域。
- [x] M4 — GitHub Actions 安装锁定 Python/Node 依赖与 Chromium并运行 E2E；为避免密码或 Session 进入持久产物，不上传 HTML/Trace/视频/截图。
- [x] M5 — Web 格式/Lint/类型/32 项单测/build、API 认证/档案 25 项和 Chromium E2E `1 passed` 通过；CI YAML、差异和生成物完成审查。

## 回滚与风险

删除 Playwright 配置、E2E 用例、CI Job 和仅开发依赖即可回滚，业务代码、契约和数据库不变。浏览器二进制会增加 CI 下载时间与缓存外存储；失败输出不得包含表单输入值、Cookie 或请求 Authorization，因此使用终端 reporter，禁用 Trace、视频和截图且不上传报告。

---

# PLANS.md — PLAN-0030 多学科基础与语文 MVP

## 计划元数据

- 计划 ID：`PLAN-0030`
- 关联：`TASK-0012`、`ADR-0027`、`docs/deep-research-report.md`
- 状态：`COMPLETE（多学科/语文本地纵向切片、v0.14.0 Ubuntu 0031 发布及发布验证完成）`
- 优先级：`P0 多学科基础 / P0 语文首个纵向切片`
- Owner：Codex（执行）；项目 Owner（2026-08-15 明确要求先多学科、再语文、英语最后）
- 创建/更新：`2026-08-15`

## 目标与边界

先把数学唯一的隐式边界改为显式 `math/chinese` 学科模型，再交付语文确定性练习的首个可验收纵向切片。通用 `StudyTask`、`StudySession` 和 Household/Child 授权继续共用；语文只新增版本化内容、答案规范、评分证据和复习事实，不复制一套会话模型。

本计划不接入英语 Provider、不改变英语 PCM/WebSocket/同意与数据最小化合同，也不实现朗读、作文自动打分、公共教材抓取或未经教研审核的正式题库。现有英语插件保持禁用态并排在语文之后。

## 分阶段实施

- [x] M1 — `Subject.CHINESE`、OpenAPI 学科枚举、孩子学科设置和数学回归。
- [x] M2 — additive `0031_multisubject_chinese_foundation`：放宽孩子学科约束；为教材 Material/Snapshot 增加不可空 subject 并将旧数据回填 `math`；新增语文内容、Attempt 和 Review 表。
- [x] M3 — 语文内容领域模型、discriminated `AnswerSpec`、版本化 deterministic scorer、Household/Child 授权和幂等提交 API。
- [x] M4 — 家长 Web 可选择数学/语文并按学科上传教材；Flutter 首页按孩子已启用学科显示语文入口，提供原创 synthetic starter content 的最小练习体验。
- [x] M5 — API/迁移/OpenAPI/Web/Flutter 定向与全量相关门槛，文档同步和差异/敏感信息审查。
- [x] M6 — 本机 PostgreSQL 从 `0025` 前滚到 `0031`；随机 Household/Parent/Child 的两个并发语文提交均追加 Attempt，Review 通过原子 upsert 合并，导出字段和级联清理 `1 passed`。

## 验收标准

- 旧孩子、旧任务和旧教材迁移后仍为数学；未启用语文的孩子不能取得或提交语文练习。
- 教材导入、列表、发布和复用不能跨学科混淆；语文内容必须保存来源类型、授权状态和版本。
- 客观题评分不调用 LLM，结果保存 `chinese-score.v1`、响应证据和反馈标签；重试不重复追加 Attempt/Review 副作用。
- Child 只能操作绑定档案，Parent 只能管理自己拥有的孩子；跨 Household/兄弟孩子统一不可枚举。
- starter content 仅使用仓库原创 synthetic 文本，不复制现行教材、教辅正文或答案。

## 兼容、发布与回滚

迁移只新增表/列并先回填旧数据，不重写历史迁移。应用回滚时保留 `subject`、语文内容、Attempt 和 Review 事实，关闭语文入口并以前向修复恢复；不得删除儿童记录或降级数据库来回滚。项目 Owner 于 2026-08-15 明确授权本计划的 Ubuntu 自用部署、提交、标签和推送；设备安装及公网/商业生产仍不在授权范围。

## v0.14.0 Ubuntu 发布里程碑（2026-08-15）

- [x] 远端 `0.13.0/0030`、服务/worker、MinIO 内网端口、英语关闭态和磁盘预检。
- [x] 暂停全部写入服务，生成 PostgreSQL custom dump、MinIO 快照、SHA-256 清单并完成隔离恢复。
- [x] 使用 Git 派生 allowlist 预览并精确同步 API/Web/契约/迁移/文档，保留远端 `.env`、卷和备份。
- [x] 以 `DOCKER_BUILDKIT=0` 重建，前滚 `0031`，核验 API/Web、current/head、表/列/约束/种子、worker、端口、英语门禁和容器内源码。
- [x] 同步部署事实后创建 Conventional Commit、`v0.14.0` annotated tag，并推送 `master` 与标签。

本次发布不启用英语或任何新 Provider，不运行真实儿童数据、真实教材或设备操作。若迁移或健康失败，停止切换并保留备份；应用回滚保留 `0031` 数据结构和新增学习事实，使用前向修复恢复。

---

# PLANS.md — PLAN-0029 GitHub APK Release 与 API CI 修复

## 计划元数据

- 计划 ID：`PLAN-0029`
- 关联事项：用户 2026-08-10 截图反馈、GitHub `v0.1.0`、`TASK-0011`
- 状态：`COMPLETE（本地门槛、GitHub Quality、标签构建和 Release 附件验收通过）`
- 优先级：`P0 / CI / RELEASE`
- Owner：Codex（执行）；项目 Owner（明确要求 Release 提供 APK 并修复 API CI）

## 范围与里程碑

- [x] API Ruff 全仓格式/检查、Mypy 正式源代码范围和非集成测试通过。
- [x] 修复超级管理员题目确认角色分支和孩子删除幂等重放，删除回执绑定发起家长账号。
- [x] 标签构建在独立 `contents: write` Job 创建或更新同名 GitHub Release；手动构建仍只保留 Artifact。
- [x] 同步 README、部署、测试、任务和变更文档。
- [x] 提交并推送 `master`，创建不改写历史的 `v0.1.1` 补丁标签；Quality run `31388975526`、Android run `31389022670` 成功，Release 五个附件均为 `uploaded`。

回滚：停用 Release Job 但保留 Actions Artifact；API 使用前向修复，不改迁移、不删除现有数据或幂等回执。

---

# PLANS.md — PLAN-0028 移除成人英语并准备 GitHub 开源

## 计划元数据

- 计划 ID：`PLAN-0028`
- 关联事项：用户 2026-08-10 明确要求、`TASK-0011`、`PLAN-0022`、`ADR-0025`
- 状态：`COMPLETE（成人增量已删除，孩子框架保留，开源文件与本地远程已准备）`
- 优先级：`P1 / OPEN SOURCE / CHILD SAFETY / API`
- Owner：Codex（执行）；项目 Owner（批准移除成人英语并公开仓库）
- 创建：`2026-08-10`

## 范围与不变量

- 删除尚未部署的家长本人英语练习、成人专用 Gemini Provider、成人实时会话授权、成人环境变量、专属依赖/测试和部署文档。
- 保留 `PLAN-0022` 的孩子英语学科入口、家长逐孩子设置、三个有界情景、PCM16/WebSocket 合同、Provider 中立接口、`disabled`/测试 `fake`、摘要、导出/删除和安全 Policy。
- 不修改数学合同、英语 `0029` 附加表或孩子历史摘要；运行态继续默认 `STUDY_ENGLISH_LIVE_ENABLED=false`、`STUDY_ENGLISH_LIVE_PROVIDER=disabled`。
- 为 GitHub 公开补齐准确 README 和根许可证；许可证只覆盖仓库自有代码/文档，不自动授权第三方依赖、模型权重、教材、题库、用户数据或商标。
- 保留工作区无关改动，不提交、不推送、不部署 Ubuntu；只准备并核验远程地址 `git@github.com:yubinhong/AIStudy.git`。

## 里程碑

- [x] M1：移除成人/Gemini 服务端实现、授权分支、环境变量、OpenAPI 描述、直接依赖和专属测试。
- [x] M2：确认孩子端 REST/WebSocket、家长设置、通用播放打断、安全 Policy、迁移/导出/删除和 Flutter 页面完整保留。
- [x] M3：撤回未部署的成人 ADR/计划并同步 `AI_CONTEXT.md`、`PROJECT.md`、`TASK.md`、`SECURITY.md`、`RUNBOOK.md`、`TESTING.md`、`DECISIONS.md` 和 `CHANGELOG.md`。
- [x] M4：采用 `Apache-2.0`，加入标准 `LICENSE`，重写根 README 的状态、架构、快速开始、安全、贡献、许可证边界和 GitHub 地址。
- [x] M5：英语定向 API `16 passed`、Ruff/Mypy、英语安全 eval `7/7`、Flutter `50 passed`/Analyze、Web `32 passed`/类型/格式、OpenAPI/JSON 解析、Compose、依赖锁、README 链接、密钥特征和最终差异检查通过。

## 发布与回滚

- 回滚代码时只允许恢复供应商中立孩子框架，不恢复成人 Gemini、成人授权或密钥配置；任何真实儿童 Provider 仍需新的合规 ADR。
- 发布仓库不等于部署服务。没有真实 Provider、正式儿童同意文本、设备/E2E 和安全门槛时，README 必须继续说明英语入口默认锁定。
- 不为本轮执行数据库 downgrade 或删除英语表/摘要；不运行 `git commit`、`git push` 或远程部署。

---

# PLANS.md — PLAN-0024 家长学习记录与 180 天保留

## 计划元数据

- 计划 ID：`PLAN-0024`
- 关联事项：项目 Owner 2026-07-30 明确要求、`ADR-0026`
- 状态：`COMPLETE（本地门槛及 Ubuntu 0.13.0/0030 发布验证通过）`
- 优先级：`P1 / WEB UX / DATA LIFECYCLE / PRIVACY`
- Owner：Codex（执行）；项目 Owner（批准 180 天学习历史保留）
- 创建：`2026-07-30`

## 范围与不变量

- 家长工作台直接列出已到期错题的题干和到期时间，不再只显示数量。
- 最近学习记录迁移到独立页面，默认读取最近 30 个上海自然日，并支持在 180 天窗口内选择单日；所有查询继续按 Session、Household 和 Child 授权。
- 详细题目、TutorTurn 和已经结束的复习链路保留 180 天；超过窗口后由既有 DataLifecycle Worker 有界清理。仍为 `open` 的错题及其复习事实不因年龄被删除，直到错题解决后再进入清理范围。
- `Attempt`、`AuditEvent`、账号、教材、开放错题等其他事实不在本次清理范围内；不得用批量删除破坏追加写、审计或当前学习状态。

## 里程碑

- [x] M1：为学习详情增加有界 UTC 时间范围、默认近 30 天、180 天硬窗口和索引，更新 OpenAPI 与 API 回归。
- [x] M2：新增独立学习记录页、按日筛选、孩子切换和导航；工作台保留 7 天趋势并直接展示到期题目。
- [x] M3：DataLifecycle Worker 按依赖顺序删除超过 180 天且不再被开放错题引用的详细学习历史，覆盖幂等和开放错题保护测试。
- [x] M4：完成 API/Web/迁移/契约验证，更新任务、测试、安全、运行和变更文档。
- [x] M5：Ubuntu 备份 `/home/syin/study-backups/20260731T020739Z` 已通过隔离恢复校验；匹配的 API/Web/worker/契约已发布并前滚至 `0030`，API `0.13.0`、Web、四个常驻 worker、迁移服务、OpenAPI、数据库索引和容器内运行源码均已核验。

## 回滚

应用和查询可成对回退，但 `0030` 只增加索引，不需破坏性降级。180 天清理由显式环境开关控制；若发现范围异常，先关闭清理并前向修复，不恢复已按批准策略删除的历史，也不删除开放错题。

---

# PLANS.md — PLAN-0023 完整解答教材匹配降级

## 计划元数据

- 计划 ID：`PLAN-0023`
- 关联事项：`TASK-0010`、`ADR-0020`、`ADR-0023`
- 状态：`COMPLETE（本地自动化、Ubuntu 发布与 iPad 覆盖安装已完成；真实 Provider 界面复核待用户操作）`
- 优先级：`P0 / CHILD UX / AI SAFETY`
- Owner：Codex（执行）；项目 Owner（要求完整解答不得因匹配缺失而消失）
- 创建：`2026-07-29`

## 范围与结果

- [x] 保留 `VerifiedQuestion`、已确认 `worked/blank` 作答和 Provider 可用性门禁；未确认的题目仍不能请求完整解答。
- [x] 可靠命中已批准知识点时，继续只向 Provider 发送该点的目标、先修范围和来源页，结果可标注教材依据。
- [x] 未命中时不再返回 `409`；只发送确认题目、确认作答与 `curriculum_grounding=not_matched`，要求适龄基础方法、禁止伪造教材来源或使用高年级方法，响应不附教材来源。
- [x] API/NewAPI 回归覆盖两条分支以及无图片外发；Flutter 不再把普通 `409` 重写为“未匹配教材”提示。
- [x] API 已部署 Ubuntu 并健康；修复版已覆盖安装、启动 iPad。截图中的线段图题仍需用户完成真实 Provider 界面复核。

## 回滚

恢复匹配阻断会重新造成儿童端无法获取完整解答，故仅在出现安全或教学质量回归时采用前向修复；不删除既有 TutorTurn、VerifiedQuestion 或学习事实。

---

# PLANS.md — PLAN-0022 英语学科与合规口语练习框架

## 计划元数据

- 计划 ID：`PLAN-0022`
- 关联事项：`TASK-0011`、`TODO-218`、`ADR-0025`
- 状态：`IN_PROGRESS（供应商中立框架、Ubuntu 禁用态部署、本地自动化和双平台 release 构建已完成；PostgreSQL 并发/级联集成和实体设备验收待完成）`
- 优先级：`P1 / CHILD UX / PRIVACY / AI SAFETY`
- Owner：Codex（执行）；项目 Owner（批准范围与合规边界）
- 创建：`2026-07-29`

## 范围与不变量

- 登录并加载绑定档案后固定显示数学、英语；数学保持现有学习桌，英语为独立插件。
- 英语只有打招呼、校园交流、点餐三个 5–8 分钟情景；家长逐孩子启用并选择 `Pre-A1/A1/A2`，每天 10 分钟、单活动会话、单次 8 分钟。
- 当前不接入 Gemini 或任何真实 Provider。默认开关与 Compose 均为 `disabled`；`fake` 只允许显式测试注入。
- 不保存音频、完整转写或 Provider 消息，只保存设置与隐私最小化摘要；不修改数学 Subject/Task/Session。

## 里程碑

- [x] M1：OpenAPI `0.12.0`、控制事件 Schema、`0029` 附加表和供应商中立 Provider/Policy。
- [x] M2：家长设置 API/Web，Owner/Household、Cookie/CSRF、版本、幂等、同意和 Provider 门禁。
- [x] M3：孩子 REST/WebSocket、PCM16 流量计数、配额、单会话、空闲/断线/撤销处理、导出与删除级联。
- [x] M4：Flutter 学科首页、英语主题/摘要、按住说话、低延迟播放、打断和前后台关闭；锁定音频依赖与平台权限。
- [x] M5：固定英语安全 eval、API/Flutter/Web 定向测试、契约与迁移静态检查。
- [ ] M6：Android/iOS release 构建已通过；真实 PostgreSQL 集成及 iPad mini 6/Nova 9 麦克风、扬声器、弱网、打断、后台生命周期验收待完成。
- [ ] M7：只有合规 Provider、监护人同意文本、真实质量/延迟/成本/儿童安全评测全部批准后，另写 ADR 修订并考虑开放。

## 回滚

保持 `STUDY_ENGLISH_LIVE_ENABLED=false` 和 `STUDY_ENGLISH_LIVE_PROVIDER=disabled` 即可关闭全部实时会话；保留首页锁定入口、设置和摘要。数据库优先前向修复，不删除已有英语摘要。2026-07-31 已将禁用态框架随 `0.13.0`/`0030` 部署 Ubuntu，不改变 `TASK-0010` 的真实教材/设备剩余验收。

---

# PLANS.md — PLAN-0019 多孩子教材作用域与教材内容复用

## 计划元数据

- 计划 ID：`PLAN-0019`
- 关联事项：`TASK-0010`、`TODO-015`、`TODO-016`、`ADR-0017`、`ADR-0019`、`ADR-0023`
- 状态：`COMPLETE（多家庭会话、公开教材复用与后续 0028 超级管理员收敛均已部署；真实跨家庭浏览器/设备回归另行验收）`
- 优先级：`P0 / WEB UX / DATA LIFECYCLE / TENANCY`
- Owner：Codex（执行）；项目 Owner（用户，提出多孩子、多家庭与教材复用方向）
- 创建：`2026-07-28`

## 问题与范围

1. 教材页为客户端组件，首次加载后没有响应 `?child=` 变化；顶栏链接更新 URL，但教材快照、知识图谱和推荐仍使用旧孩子状态。
2. API 的资源路径和授权已携带 `household_id`，但 Web 代理曾固定默认 Household，认证初始化只支持单家庭自用，无法让亲戚的孩子登录到独立家庭。
3. 同一国家公开 PDF 上传给不同家庭时会重复保存原件、页图和分析，造成存储和 Provider 成本重复；不能把未经明确授权的教材做跨家庭全局去重。

## 决策边界

- 当前 Session 的 Household 是 Web/API/Flutter 唯一作用域；全实例唯一 `super_admin` 可以开通新家庭及其首个普通 `parent`，普通家长只能管理自己拥有的孩子，不能创建家庭或跨家庭管理账号。
- 只有家长每次上传时显式声明为公开可复用的 PDF，才可按 SHA-256、媒体类型和字节数匹配另一个已批准来源；目标家庭得到独立待审核 Snapshot/知识图谱，不复用任务或学习事实。
- 原始 PDF 与页图共享必须由引用检查保护；删除一个家庭教材绝不能删除另一家庭仍引用的对象。
- 不复用或外发儿童学习记录、拍题图、孩子资料；接口和 UI 不返回来源家庭、对象键或复用命中信息。

## 实施阶段

- [x] M0 — 当前孩子切换：教材页监听并验证 `?child=`，原子切换教材/知识图谱/推荐视图，清除旧孩子瞬态状态；增加 URL 切换回归。
- [x] M1 — 多家庭会话与账号边界：Web BFF/Flutter 由 Session 读取 Household；后续 `0028` 将原 `parent_admin` 收敛为唯一实例级 `super_admin`，其可创建独立家庭的首个普通家长，用户名全局唯一。
- [x] M2 — 公开教材复用：显式公开声明的 PDF 以完整内容指纹命中已批准来源时，复用私有 PDF、页图、页级解析和知识图谱草稿，目标仍须独立审核发布。
- [x] M3 — 生命周期与迁移：`0027_multi_household_public_curriculum` 增加公开复用标记、来源 Snapshot 和可多引用对象键，`0028_super_admin_ownership` 进一步收敛角色并绑定孩子所有者；删除时保留仍有其他材料/Snapshot 引用的对象。

## 验收与回滚

- 两个孩子在 `/curriculum?child=A` 与 `/curriculum?child=B` 间切换时，标题、上传目标、教材、知识图谱和推荐请求全部使用同一个已授权孩子 ID；篡改 ID 不得得到另一家庭/孩子数据。
- 两个家庭上传相同且明确声明的公开 PDF 后不重复解析/分析；各自 Snapshot/审核/发布/推荐仍互不影响。
- 任一删除后另一家庭仍可查看原页和发布；最后引用删除后才进入对象清理。
- 多家庭仍是自托管管理员开通，不开放匿名注册、跨家庭账号切换或公网商业化服务。
- 回滚优先前向修复。迁移保留原材料/Snapshot/学习事实；紧急回退应用时继续读取旧对象键，禁止批量删除或合并已有教材。

# PLANS.md — PLAN-0018 教材原页、多模态知识图谱与知识点任务

## 计划元数据

- 计划 ID：`PLAN-0018`
- 关联事项：`ADR-0023`、`TODO-016`、`TODO-019`、`FR-011`、`FR-020`
- 状态：`IN_PROGRESS（M1～M6、本地三端质量门槛和 Ubuntu 0.11.0/0025 前滚已完成；真实教材、Provider、浏览器和设备验收待完成）`
- 优先级：`P0 教材可用性 / P1 推荐质量`
- Owner：Codex（执行）；项目 Owner（用户，2026-07-23 根据真实教材结果要求整改）
- 创建/更新：`2026-07-23`

## 1. 真实缺陷

- 原始 PDF 仍在私有 MinIO，但当前家长阅读器只展示 `pdfplumber` 文字流，丢失插图、方框、连线、涂色和位置关系；“100%”仅代表文字抽取，并不代表语义完整。
- 解析 worker 把每一页伪装成一个“教材小节”，学习目标固定为“理解本页/完成练习”，没有全书章节、知识点、先修关系或教材方法。
- 推荐引擎从残缺文字按问号/关键词抽题，导致题干缺图、主语丢失、知识点错配，虽有页码仍不可用。

## 2. 目标流程

1. PDF 原件私有保存，并逐页生成受鉴权原页预览。
2. NewAPI 每批理解最多 4 页的文字与视觉，再对全部页级结构化结果归纳全书章节和知识点。
3. 服务端保存可追溯知识图谱草稿；家长同时查看原页、全书摘要、章节、知识点、目标、先修关系和练习证据后批准。
4. 全部开放错题与已批准知识点交给云模型关联；服务端统计薄弱知识点频次，再生成来源受限的未来学习任务。
5. Web 和孩子端展示完整题干、知识点依据、教材页码；需要图形语义的题可以查看受鉴权教材原页。

## 3. 里程碑

- [x] M1 — `0025_curriculum_knowledge_map`：页图资产、页级 AI 分析、知识图谱、规范化知识点与状态/审计字段。
- [x] M2 — 本地 PDFium 有界逐页渲染、私有预览存储、Session API 原页读取和删除清理。
- [x] M3 — NewAPI 页批次多模态 Schema、全书归纳 Schema、来源键/页码验证和可恢复分析 worker。
- [x] M4 — 上传后自动排队、旧教材手工重新分析、家长知识图谱审核/批准和发布门禁。
- [x] M5 — 推荐改为“已批准知识点 + 全部开放错题 → 云端关联/规划”，删除残缺页文字直接抽题路径。
- [x] M6 — Web 原页/知识图谱/状态 UI、推荐知识依据与原页入口；Flutter 显示视觉描述，并以孩子 Session 打开对应私有 JPEG 原页。
- [ ] M7 — OpenAPI `0.11.0`、迁移、API/Web/Flutter 本地门槛、文档和 Ubuntu `0.11.0`/`0025` 前滚已完成。2026-07-27 增加本地封面标题识别（显式家长覆盖不改写）及整书 Prompt `v5`：封面/目录/过渡页可形成无知识点章节，非数组可选引用收敛为空、缺少非空学习目标的知识点直接丢弃、超出既有 Schema 上限的集合仅截取有界有效前缀而不编造；最终知识点的目标/页码/来源校验保持严格。同一 Provider 的临时 `429`/`5xx`/网络/超时会按 1 秒、2 秒重试，最终失败仍由家长显式重试。真实 AI 质量 eval、已上传教材的人工重试/质量、浏览器和设备验收未执行。
- [x] M8 — 多教材并行发布：发布新教材不得撤销同一孩子既有已发布快照；家长页面须显示每份教材的独立发布状态。Tutor 检索和任务推荐遍历所有已发布且已批准知识图谱的教材，每条来源继续绑定确切 `snapshot_id`、页码和练习键；删除是唯一的下线操作。`0026_parallel_curriculum` 恢复旧自动替换造成的 `rejected` 快照；API 定向 14 项、全量非集成、Ruff/Mypy、Web 20 项/类型/格式/Lint 和迁移离线 SQL 通过。Ubuntu 备份 `/home/syin/study-backups/20260727T065635Z` 后前滚，API/Web 健康，远端汇总为两份 `published` 快照。
- [x] M9 — 计划日可见性：孩子端仍只允许当天的 `assigned/in_progress` 任务进入“今日任务”，但会读取最近一项未来 `assigned` 计划并只读显示其日期和标题；已过计划日但未完成的任务继续可补做。家长端批准反馈和已批准状态明确“将于计划日期出现在孩子端”。不修改 Task 数据、计划日期、来源题或服务端授权。Flutter `45` 项/Analyze、Web `20` 项/类型/Lint/格式通过；Ubuntu Node `24.18`/pnpm `11.7` 已重建 Web 并健康，新 release APK 已安装 Nova 9。待用未来计划和过期任务进行设备界面人工验收。
- [x] M10 — 任务入口临时收口：真实 Nova 9 体验显示孩子端将多个已分配任务堆叠展示，且“开始任务”准备会话后仍进入通用拍题，不能代表已分配教材题的学习流程。2026-07-27 起学习桌不再渲染或请求今日任务，不显示“今日任务”按钮或“稍后再做”；任务、推荐和家长审批数据保持不变。Flutter `45` 项/Analyze 通过，release APK 已构建；设备重连后覆盖安装并人工确认。任务执行重构转入 `TODO-215`。
- [x] M11 — 错题 closeout 与教材范围讲解收口：`needs_review` 只有在原子 `mistake-closeout` 返回错题记录后才可显示成功，并自动回到学习桌；未确认题目/作答状态会在客户端明确阻断。完整解答先匹配当前孩子已批准知识图谱中的具体知识点，再把该点的标题、目标、先修范围和来源页作为模型唯一允许的教学范围；无法可靠匹配时以 `409` 阻断完整解答，不把通用模型知识伪装为教材讲解。API Tutor/NewAPI 定向 22 项、Flutter 全量 48 项、Analyze、Mypy 与 Ruff 已通过；API 全量非集成套件在本机两次于约 72% 后无结果结束，未计为通过。Ubuntu API 与 Nova 9 APK 尚未部署/安装，待发布窗口与设备重新连接。

## 4. 验收标准

- [ ] 截图中的“位置”“分与合”页面在 Web 能看到原页图，不再把残缺文字标为完整教材。
- [ ] 知识图谱按真实章节归纳知识点，保存来源页、学习目标、先修关系、摘要和练习证据。
- [x] 模型伪造页码/练习来源、缺页、Schema 错误或 Provider 失败时图谱不能批准或进入推荐（固定 Schema/来源 allowlist 自动化）。
- [ ] 当前 118 页教材可重新分析；旧已发布 Snapshot 不被篡改，批准知识图谱后才启用新推荐。
- [ ] 推荐理由能说明“哪些错题 → 哪个教材知识点 → 哪些来源页/练习”，孩子端需要图形时能查看原页。
- [ ] 同一孩子发布两份教材后，两份均保持 `published` 并可独立查看、删除；任务推荐可从两份已批准知识图谱取候选，且不跨教材混淆来源。
- [ ] 删除教材同时删除 PDF、原页预览、知识图谱和未批准推荐，不泄露对象键或 MinIO URL。

## 5. 风险与回滚

- 页面视觉分析会增加 NewAPI 调用、延迟与费用；每批最多 4 页、单图有界压缩、最大页数和调用审计必须生效，真实全书运行前展示成本风险。
- 教材页可能含个人批注；当前功能只面向家庭有权使用的教材原件，若检测到手写姓名/身份信息必须阻断该页云分析并要求家长确认。
- 回滚只关闭 `curriculum_multimodal_analysis` 和知识图谱推荐，保留原 PDF、页图及已批准知识事实；旧纯文本只作检索辅助，不恢复残缺题目推荐。

---

# PLANS.md — PLAN-0017 云端递进 Tutor 与教材智能任务整改

## 计划元数据

- 计划 ID：`PLAN-0017`
- 关联事项：`ADR-0022`、`TODO-016`～`TODO-020`、`FR-005`、`FR-019`、`FR-020`
- 状态：`IN_PROGRESS（M1～M6 代码、自动化与 Ubuntu 0024 部署已完成；真实 Provider/PDF/iPad 验收待执行）`
- 优先级：`P0 Tutor 质量 / P0 复习可用性 / P1 智能推荐`
- Owner：Codex（执行）；项目 Owner（用户，2026-07-23 要求立即整改）
- 创建/更新：`2026-07-23`

## 1. 用户反馈与根因

真实 iPad 体验证明当前实现虽然保存了 L1/L2 递进元数据，但教学内容仍不可用：

- “四个人一起玩 40 分钟，每人玩多久”被本地模板误判为增减/比较/平均分，L1/L2 与题目核心的“同时经历同一时间段”无关；L3 走 NewAPI 完整解答所以反而正确。
- 错题讲解完成虽可创建 `MistakeRecord`，复习入口默认只查询“今天到期”，首个 1 天间隔内会显示没有错题，用户无法立即进入“全部错题”提前复习。
- 任务推荐只在到期错题和教材首个手工小节之间二选一；没有遍历已发布 PDF 页级内容、统计错题薄弱点、抽取具体教材题、生成未来数日计划或把题目/页码送到孩子端。

本计划以可运行闭环为完成标准，不再把字段存在、按钮存在或 PDF 已上传描述成能力完成。

## 2. 目标行为

### 2.1 Tutor L1/L2

- NewAPI 已配置时，L1/L2 与 L3 使用同一已确认题目事实和同一 Provider Adapter，但采用独立严格 Schema。
- L1 必须指出这道题独有的关键关系并提出一个聚焦问题；L2 必须引用实际 L1，新增方法/图示/第一步脚手架。
- L1/L2 的 `direct_answer`、`solution_steps` 为空，`answer_exposure=none`；服务端拒绝“答案是/所以得”等明显答案泄露、等式算完和与 L1 重复的响应。
- Provider 不可用或响应不合格时使用题型化确定性降级；至少覆盖“同时发生/共同经历同一时长”，不得再落回错误的平均分模板。

### 2.2 错题复习

- “复习错题”先显示今日到期；若今日无到期但存在开放错题，自动显示全部错题并标注“可提前复习”。
- 复习继续展示实际 VerifiedQuestion、隐藏历史答案、要求新作答并追加 `ReviewAttempt`；不放宽服务端确定性判定。

### 2.3 智能任务推荐

- 服务端遍历当前孩子最新已发布 Snapshot 的全部页级 chunks，在本地计算与全部开放错题、到期状态、题型和重复频次的相关度；只把有界候选摘要交给 NewAPI，不外发整本 PDF。
- 云模型在这些候选中规划最多 5 条、未来 7 天内的学习安排：优先到期错题和高频薄弱点，再选择已发布教材中的具体原题/练习；输出原因、题量、预计时间和计划日期，正式知识点由服务端从所选来源回填。
- 教材题必须绑定 `snapshot_id/chunk_id/page_number`，发送给孩子端的题目正文必须来自已发布 chunk，不能由模型伪造为教材原题。
- 推荐保留家长批准/忽略门禁；批准后创建带同样来源、题目、预计时间和计划日期的 Task。Provider 未配置或没有可靠来源时明确失败/空结果，不再生成“练习一小节”占位任务。
- 同一内容只允许一个待审核推荐；已批准/忽略的历史保留，新的计划周期可以重新推荐，但不得因重试重复创建。

## 3. 分阶段实施

- [x] M1 — 新增失败回归：同时关系题 L1/L2、云提示 Schema/泄露/递进、无到期但有错题的提前复习。
- [x] M2 — 扩展 NewAPI 文本 Tutor 提示能力，重构 Tutor 路由先取得 L1/教材来源再调用并验证 L2。
- [x] M3 — 新增 `0024_intelligent_recommendations`，扩展 Recommendation/Task 来源、题目、页码、知识点、题量、时长、日期、Provider/策略字段。
- [x] M4 — 实现全 Snapshot 本地扫描、错题频率/题型聚合、有界候选和 NewAPI 7 日计划；删除占位推荐路径。
- [x] M5 — Web 展示具体来源/题目/日期/时长，Flutter 显示全部今日任务、教材题和复习任务；复习入口增加提前复习降级。
- [x] M6 — OpenAPI/Schema、迁移、API/Web/Flutter、固定 AI eval 和文档同步；Ubuntu/真机部署仍需单独授权和现场验收。

## 4. 验收标准

- [x] 本地固定题“4 人同时玩 40 分钟”中，L1 聚焦“同时还是轮流/时间是否按人数分”，L2 增加同步起止时间轴脚手架；两级不直接说最终答案。
- [x] L2 持久化 `builds_on_turn_id` 且披露集合严格增加；云响应不合格会安全降级。
- [x] 一个刚加入、明天才到期的开放错题今天也能从复习入口看到并提交新作答。
- [x] 推荐同时消费开放/到期错题和已发布 PDF chunks，原因包含频次或到期依据；教材推荐包含具体题目和页码。
- [x] 家长批准后，孩子端能看到题目、知识点、来源、预计时间；多条今日任务不再只显示第一条。
- [x] 没有 NewAPI 或可靠来源时不生成误导性占位推荐；跨家庭/孩子、未发布材料和模型伪造 source key 被拒绝。

以上为本地自动化和 Ubuntu `0024` 前滚验收结果；真实 NewAPI 输出质量、真实文本/扫描 PDF 和 iPad 操作仍是独立现场验收项。

## 5. 兼容、回滚与安全

- 数据库只做向前兼容加列/索引，旧 Task/Recommendation 使用空来源字段继续读取；不覆盖既有审批、Task、Mistake、ReviewAttempt 或 TutorTurn。
- 关闭云提示时回退已验证确定性模板；关闭智能推荐时既有任务和审批历史仍可读取，家长仍可手工创建任务。
- 题目图片不进入 Tutor/推荐调用。Tutor 只发送已确认文字和最多 3 个最小教材片段；推荐只发送经过本地全量扫描后选出的有界候选，不发送 PDF、对象键或 URL。
- 推荐模型只能选择服务端给出的 source key；教材题正文由服务端按 source key 回填，模型输出不能直接写教材事实。正式 Task 仍必须由家长批准。

---

# PLANS.md — PLAN-0016 复习错题、教材解析与渐进提示收口

## 计划元数据

- 计划 ID：`PLAN-0016`
- 关联事项：`ADR-0020`、`ADR-0021（Accepted）`、`TODO-016`～`TODO-020`、`FR-005`、`FR-011`、`FR-019`、`FR-020`
- 状态：`IN_PROGRESS（M0～M5 代码已落地；M6 设备/E2E/发布验证待完成）`
- 优先级：`P0 学习闭环 / P1 分阶段交付`
- Owner：Codex（后续执行）；项目 Owner（用户，提出本轮三项缺口）
- 创建/更新：`2026-07-23`

## 1. 目标与完成定义

本计划不新增第四条学习主线，而是把已有三个“可见但不可用”的壳收口为真实闭环：

1. 拍题讲解完成后，服务端以已确认题目和作答证据原子沉淀错题；复习入口展示真实题目、要求重新作答并追加复习证据，不能只让客户端上报“会了/不会”。
2. 私有 MinIO 中的 PDF 经有界本地解析、家长审核和不可变发布后，既可为错题讲解提供有页码来源的最小知识片段，也可生成默认待家长批准的任务建议；首版教材上传合同不接受 Word、PPT 或 Excel。
3. Tutor 的第 1、2 级从“不同文案”升级为语义递进：第 1 级帮助看懂题意/定位首个疑点，第 2 级给出方法与第一步脚手架，第 3 级才在允许的模式和证据门禁下给完整过程。

完成标准是数据、契约、交互和测试同时闭环，而不是仅存在表、接口、上传记录或三个按钮。

## 2. 当前事实与缺口

2026-07-23 实施收口：M1/M2 的证据链、M3 的原子 closeout 与 ReviewAttempt、M4 的 PDF 解析/页级 grounding 和 M5 的 Tutor 递进元数据已写入代码，并已部署 Ubuntu 0024 与 iPad 最新签名包。剩余工作是浏览器/四设备 E2E、真实 PDF/扫描 PDF 验收和安全/成本发布门槛，不再把这些实现缺口留给后续规划。

### 2.1 错题与复习

- 已有 `MistakeRecord`、`ReviewSchedule`、原子 closeout、实际题目回读和 Flutter 的“复习错题”入口。
- 拍题讲解完成现在由 `/mistake-closeout` 在 PostgreSQL 事务内校验已确认题目和 `worked/blank` 证据，幂等创建错题/复习计划后完成 StudySession。
- 复习页收集新的作答文本与确认标记，追加写 `ReviewAttempt`；API 根据服务端标准答案和 `review-policy.v2` 判定，不再信任客户端直接上报结果。
- 间隔算法已锁定版本化 `1/3/7/14/30` 天策略；真实设备、并发及时区验收仍属于 M6。

### 2.2 教材解析与消费

- 当前运行时代码只允许 PDF 上传到私有 MinIO，并创建 `queued/parsing/needs_review` 草稿；Word/PPT/Excel 在 API 边界以 `unsupported_material_format` 拒绝，未解析文档仍禁止发布。
- 文本 PDF 已由隔离 worker 解析为页级 `CurriculumChunk`，PostgreSQL 检索只返回当前孩子已发布 Snapshot 的最小来源锚点；扫描 PDF 进入 `needs_ocr`。练习候选仍以后续规则化抽取和家长审核为边界。
- 因此“文件已上传”不等于“教材已生效”；在解析、审核和发布前，讲解与推荐都不得引用文件内容。

### 2.3 第 1、2 级提示

- Tutor Policy 已为 L1/L2/L3 生成稳定的教学目标、孩子动作、披露集合、答案暴露级别和 `builds_on_turn_id`；worked/blank/review 分支保留不同的教学语义。
- M5 的契约、持久化和 Flutter 展示已实现；固定 Tutor 质量/泄露 eval、真实 Provider 和设备交互仍属于 M6。

## 3. 工作流 A：正式错题复习

### 3.1 讲解完成原子沉淀

- 增加一个服务端编排命令（目标语义为 `mistake-closeout`，精确路径以 OpenAPI 差异为准），在同一幂等事务中校验 VerifiedQuestion、已确认 AttemptEvidence、讲解/会话归属，并创建或复用唯一 MistakeRecord、首个 ReviewSchedule，再完成 StudySession。
- 客户端不得串联“结束会话 → 创建错题”两个可能部分失败的事实写入；同一 Session/VerifiedQuestion 重试不得产生重复错题。
- 只有 `worked` 或 `blank + evidence_confirmed=true` 可直接沉淀；`unclear/answer_area_missing` 继续阻断。讲解或教材 grounding 尚未通过时可保留 `mistake_candidate/needs_parent_review`，不能伪造完成事实。
- 立即修正错误成功文案：只有 closeout 返回 MistakeRecord 后才显示“已加入错题本”。

### 3.2 历史拍题迁移

- 不把所有 Capture/拍题记录批量当成错题。仅将拥有 VerifiedQuestion、同孩子已确认 AttemptEvidence 且结果为 `needs_review` 的历史会话列为候选。
- 家长或孩子可对合格候选执行一次“加入错题本”；无法证明作答区状态的旧记录保持历史记录，不补造空白、错因或掌握度。

### 3.3 逐题复习与确定性判定

- 复习页提供“今日到期”和“全部错题”，每项先加载实际 VerifiedQuestion，默认隐藏历史答案、讲解与原作答。
- 孩子必须提交新的复习作答：首版对适合键入的题支持有限文本/结构化答案，复杂题复用受鉴权拍题链路；每次生成追加写 `ReviewAttempt` 并引用 mistake、question、policy version 和证据。
- 服务端用已批准标准解/确定性规则给出复习判定；无法可靠判定时进入人工确认，不让客户端或 AI 直接修改到期/掌握状态。
- `review-policy.v2` 采用版本化 `1/3/7/14/30` 天基线：正确晋级，错误回到首阶段并可进入渐进提示/既有讲解；最终过关门槛在 synthetic/家庭验收后锁定。旧 schedule 保留原 policy version，可重算派生状态但不覆盖 ReviewAttempt。

## 4. 工作流 B：教材文档解析与两类消费

### 4.1 首批格式与状态机

- v1 教材上传和解析只支持 PDF。Web 文件选择器只展示 `.pdf`，OpenAPI/API 同时校验扩展名、声明 MIME、文件头和实际 PDF 结构；允许一次选择多个 PDF，但批次中的任一非 PDF 文件都必须明确拒绝，不能只改前端。
- 文本 PDF 保留页码锚点；扫描 PDF 识别为 `needs_ocr`，不得冒充解析成功。其本地文档 OCR 是独立于拍题 PrivacySanitizer OCR 的后续能力。
- DOC/DOCX、PPT/PPTX、XLS/XLSX 均不属于首版上传合同。UI 提示家长先在本地转换为 PDF；API 返回稳定的 `unsupported_material_format`，不得把这些文件写入新的 LearningMaterial。
- 既有非 PDF 对象和数据库记录只为兼容/删除保留，统一标为 `unsupported_for_learning_content`，不得解析、发布、进入 Tutor 或推荐；不得自动转换或静默删除。
- 材料解析状态机：`uploaded → queued → parsing → needs_review | needs_ocr | failed/quarantined`；家长对 `needs_review` 草稿审核后另行创建不可变 `published` Snapshot，发布不是解析 Job 自动状态。

### 4.2 解析架构与数据

- 在独立 worker 中增加 `MaterialParseJob`、`CurriculumChunk`、`KnowledgePointEvidence` 和 `ExerciseCandidate`；API 只负责鉴权、入队、查询与审核，不在请求进程同步解压/解析整份文档。
- PDF 提取页面文字、标题和表格的有限表示；拒绝加密、损坏、含危险动作/嵌入附件或超过批准资源上限的 PDF，扫描件进入 `needs_ocr`。
- 每个 chunk 记录 material/snapshot、页码锚点、文本哈希、解析器/Schema 版本和置信度；原文、草稿、发布快照分离。
- 首版检索采用 Household/Child/Snapshot 强过滤 + PostgreSQL 全文检索/元数据匹配；pgvector 混合检索只在固定 eval 证明收益后启用。

### 4.3 消费一：错题讲解 grounding

- 由 VerifiedQuestion 候选知识点检索当前孩子已发布 Snapshot 中的最少 chunks，返回来源锚点和匹配置信度；未发布、跨家庭、低置信、版本冲突或超纲时阻断教材化讲解并请求校正。
- Tutor 只接收完成当前题目所需的最小文本片段，固定标记为不可信资料；文档中的指令不能进入系统 Prompt。
- TutorTurn 保存 snapshot/chunk/knowledge-point 引用、Policy/Prompt/模型版本；“按教材讲解”必须能在家长端回看来源，不允许只显示无来源模型结论。

### 4.4 消费二：推荐学习任务

- Recommendation 组合到期错题、重复薄弱知识点、已发布 `ExerciseCandidate`/章节范围；每条保存“为什么推荐”、错题/知识点/材料来源和策略版本。
- 首批只选择已有错题或家庭材料中经家长审核的练习，不由 AI 静默新编题；推荐默认待家长批准/修改/拒绝，批准后才生成 Task。
- 建立重复去重、每日上限和无可靠来源时不生成规则；同一教材更新不静默改变既有任务依据。

## 5. 工作流 C：真正渐进的第 1、2 级提示

### 5.1 教学语义

| 级别 | 目标 | 可披露内容 | 禁止内容 |
| --- | --- | --- | --- |
| L1 看懂题意 | 确认已知/所求，或指出已有作答中最早需要检查的位置 | 一个具体关系、一个聚焦问题、孩子下一步动作 | 最终答案、完整算式、直接纠正全部步骤 |
| L2 找到方法 | 解释为何使用某方法，给出图示/关系式/算式骨架或修正第一步 | 比 L1 多一个明确策略和可执行脚手架，并引用 `builds_on_turn_id` | 最终答案、完整解题步骤；不得与 L1 换词重复 |
| L3 完整讲解 | 在模式与证据允许时给出完整步骤、答案和验算 | 经过 Schema、教材范围和确定性校验的完整过程 | 在 guided/review 未先作答，或题目/作答状态未确认时泄露答案 |

### 5.2 契约、状态与交互

- 发布新版本 Tutor Hint Schema/Policy，至少增加 `hint_goal`、`builds_on_turn_id`、`revealed_elements`、`child_action`、`answer_exposure`、`knowledge_point_ids/source_refs`；L1/L2 的 `direct_answer` 必须为空且不得含完整 `solution_steps`。
- 保存前一 TutorTurn，服务端校验 L2 引用同一会话 L1，并在结构化披露集合上至少增加一个方法脚手架；重复或越级时拒绝/降级到确定性模板。
- Flutter 明示“第 1 步：看懂题意 / 第 2 步：找到方法 / 第 3 步：完整讲解”，每级展示一个孩子可执行动作，并提供低干扰的“这一步懂了 / 还需要更具体”。
- worked、blank、review 三类上下文分别出题型模板：worked 的 L1 定位首个疑点、L2 给修正第一步；blank 的 L1 拆已知/所求、L2 给方法骨架；review 保持先提交新作答再提示。

## 6. 安全、依赖与资源门禁

- ADR-0021 已由项目 Owner 接受。实现锁定 `pdfplumber==0.11.7` 与 `pdfminer-six==20250506`（MIT），并已写入锁文件；生产发布前继续执行镜像/SBOM 扫描。
- 不默认采用 AGPL/商业双许可证的 PyMuPDF，也不为首版引入 `python-docx`、`python-pptx`、`unstructured` 或 LibreOffice。以后增加新格式必须重新修改 OpenAPI、测试矩阵和本 ADR，不能仅扩展文件后缀。
- 解析 worker 禁止出网，限制 PDF 大小、页数、对象/流展开量、CPU、内存、运行时间和重试；检测加密、危险动作/链接、嵌入附件、异常交叉引用/文件头和资源炸弹，失败进入隔离/清理流程且不记录正文。
- 材料/解析文本继续按 Confidential + 版权数据处理；Provider 不接收整本文件、对象键或 URL。导出、删除、授权撤销、备份恢复和审计必须覆盖新增解析事实。
- 复习判定、调度和掌握状态由服务端确定性策略控制；客户端输入和 AI 结论均为不可信候选。

## 7. 分阶段交付与依赖顺序

- [x] M0 — 契约/决策基线：接受 ADR-0021，将 OpenAPI/API/Web 上传 allowlist 收缩为 PDF-only，定义既有非 PDF 数据兼容和稳定错误码，并完成 AI Schema 差异、迁移设计、依赖/SBOM/资源上限和功能开关评审。
- [x] M1 — 错题沉淀修复：实现 closeout 原子事务、唯一/幂等约束、正确成功文案和合格历史候选，不再出现“显示已加入但队列为空”。
- [x] M2 — 正式复习：实现 Question 详情、ReviewAttempt 追加写、服务端判定、ReviewPolicy v2、到期/全部 UI 和离线重试。
- [x] M3 — 文档解析：实现隔离 worker、文本/扫描 PDF 分流、状态机、页码来源、家长审核和删除/重试；非 PDF 新上传明确拒绝。
- [x] M4 — 两类教材消费：接入错题 grounding 与来源回看；按已发布练习/知识点生成待审批任务推荐。
- [x] M5 — 渐进提示：发布 Tutor Hint Schema/Policy 新版本，接入 L1/L2 状态和 Flutter 交互，保留确定性降级模板。
- [ ] M6 — 质量与发布：完成 PostgreSQL/MinIO 集成、双孩子/反向授权、浏览器/Flutter E2E、固定数学与文档安全 eval、Ubuntu 备份恢复和 iPad 真机回归后逐项开关。`2026-07-23` 补充家长审核/推荐的可读文档详情：列表只呈现摘要，家长显式点击后读取同一孩子范围内的分页解析文本或单条推荐练习；已知 PDF 图形兼容警告不得淹没 worker 日志，真实解析失败仍须进入稳定状态。

M1 可与 ADR-0021 评审并行，但 M3 不得早于 ADR 接受；M4 依赖 M2/M3 的可追溯事实；M5 可以先用 VerifiedQuestion 的确定性模板实现，教材来源展示需等待 M4。

## 8. 核心验收

- [ ] 一道符合门禁的拍题讲解完成后，数据库中恰有一条 MistakeRecord 和一个 ReviewSchedule；重复提交不重复，失败不显示成功。
- [ ] 到期复习展示实际题目并隐藏历史答案；每次重新作答产生不可覆盖的 ReviewAttempt，只有服务端判定能按同一 policy version 晋级/回退。
- [ ] 既有拍题记录不会被批量误判为错题；只有证据完整的候选可人工加入。
- [ ] synthetic 文本 PDF 可解析为带页码来源的草稿并由家长发布；扫描 PDF 明确进入待 OCR、不能误发布；DOC/DOCX、PPT/PPTX、XLS/XLSX 在 Web 和 API 均被拒绝，既有非 PDF 记录不能被解析或发布。
- [ ] 错题讲解可回看所用 Snapshot/Chunk 来源；未发布/跨孩子/低置信/Prompt 注入内容无法进入 Tutor。
- [ ] 推荐任务能解释到期错题、知识点和已发布材料练习；未经家长批准不进入今日任务。
- [ ] 固定题集证明 L2 在同一题、同一作答状态下建立于 L1 并增加一个方法脚手架，且 L1/L2 的答案泄露率为 0；worked/blank/review 分支分别通过。
- [ ] API/worker/Web/Flutter 的授权、幂等、并发、断网、删除/导出、资源耗尽、Provider 失败和回滚测试通过。

## 9. 兼容、迁移与回滚

- 数据库采用向前兼容的新增表/列/唯一约束；不覆盖既有 Capture、VerifiedQuestion、Attempt、TutorTurn、MistakeRecord 或 Schedule。旧复习提交接口在兼容窗口内只供旧客户端，新的孩子端不得再以客户端结果直接晋级。
- 解析产物、知识匹配、推荐和 ReviewSchedule 是可重算派生数据；原材料授权/哈希、VerifiedQuestion、Attempt/ReviewAttempt、发布/审批事实不可静默重算覆盖。
- 部署顺序：数据库 → API/worker（开关关闭）→ Web 审核 → Flutter → synthetic/双孩子 smoke → 逐项开关。应用回滚保留新增事实并优先前滚修复，不执行生产 downgrade。
- 解析异常时关闭材料解析/grounding，保留手工小节、既有讲解和确定性复习；渐进提示异常时回退到上一版已验证 Policy，不绕过答案门禁。

---

# PLANS.md — PLAN-0015 多文档教材上传首版

## 计划元数据

- 计划 ID：`PLAN-0015`
- 关联事项：`TODO-016`、`ADR-0020`、`0019_curriculum_documents`
- 状态：`SUPERSEDED_IN_SCOPE（历史多格式上传已部署；目标上传合同由 PLAN-0016 收缩为 PDF-only）`
- 创建/更新：`2026-07-23`

## 目标与边界

为家长教材工作台增加可见的多选上传入口，支持 PDF、DOC/DOCX、PPT/PPTX、XLS/XLSX。API 按文件做扩展名、50 MB 单文件、200 MB 批次、SHA-256 和授权声明校验，经 boto3 S3 兼容接口写入私有 MinIO，并为每个文件创建待解析草稿；本计划不假定已完成 DOC/PPT/PDF 内容解析。

## 实施与验收

- [x] Web 多选文件、队列展示、上传状态和错误提示。
- [x] API multipart 接口、对象流式写入、`0019` 对象键/`uploaded` 状态和幂等材料。
- [x] OpenAPI、`python-multipart` 锁文件和 API 成功/拒绝回归测试。
- [x] Ubuntu 备份后前滚 `0019`，重建 API/Web/worker，验证健康、迁移和 OpenAPI 上传路径。
- [ ] 按 PLAN-0016 收缩 Web/API/OpenAPI 为 PDF-only，并只接入 PDF 解析、页码/章节来源、删除/撤销和文档安全 eval；历史非 PDF 对象保留但不得解析或发布。

## 回滚

应用回滚保留 `0019` 表结构和已上传对象；优先前滚修复，不执行生产 downgrade。未解析的 `uploaded` 草稿不进入孩子端或 Tutor，删除/清理继续遵循对象保留策略。

---

# PLANS.md — PLAN-0012 Capture 服务端流式上传收敛

## 计划元数据

- 计划 ID：`PLAN-0012`
- 关联任务：`TASK-0009`、`TODO-014`、`ADR-0018`
- 状态：`IN_PROGRESS（API/Flutter/契约/Compose 已迁移并部署 Ubuntu；最终设备/Provider 验收未完成）`
- 优先级：`P0 / SECURITY / API CONTRACT`
- Owner：Codex（后续执行）；项目 Owner（用户，架构决定已批准）
- 创建/更新：`2026-07-18`

## 目标与现状冲突

目标链路统一为：

```text
App → API：携带可撤销 Session 上传图片
API：有界流式校验大小、类型、文件头、尺寸/像素和 SHA-256
API → 私有 MinIO：只通过 Compose 内部地址流式写入
API → App：返回已完成对象校验的 Capture
```

当前 OpenAPI/API `0.8.0`、Flutter、Compose 和 Ubuntu 已执行“Session → API 原始流 → 内部 MinIO multipart”，并已移除正式契约中的预签名/独立确认；远端旧 `.env` 中残留的公开 MinIO 地址已清理，MinIO `9000` 未向宿主/LAN 暴露。隐藏旧路由仅作为测试与受控回滚兼容，不能作为正式客户端合同。

## 范围与不变量

- 修改范围：`packages/contracts`、`services/api`、`apps/child_flutter`、`infra/compose` 及测试/部署文档；不改变图片保留、脱敏、单 Provider、VerifiedQuestion 或 Tutor 信任边界。
- App 只连接用户配置的 API 基础地址，不解析、保存或请求任何 MinIO URL，不持有对象存储密钥。
- API 必须在读请求体前验证 Session、Household、角色、孩子和 StudySession；上传写接口继续要求 `Idempotency-Key`。
- API 必须分块读取、增量计数/哈希并向随机 staging 对象流式写入；禁止无界 `request.body()`/完整 `bytes` 聚合。超过 8 MB、超时或断连必须立即中止并清理。
- 声明 MIME、JPEG/PNG 文件头、宽高/总像素、完整解码、实际 SHA-256 和声明值必须由服务端独立验证；客户端计算值只作声明与幂等材料。
- MinIO Bucket 保持私有，服务端内部继续使用 S3 兼容 Adapter；宿主/LAN 不发布 `9000`。对象键、图片、会话、存储凭据和内部 URL 不得进入响应、日志或审计。

## 实施阶段

- [x] 1. 契约收缩：发布单一 Session 鉴权上传操作接收单文件原始流并返回 `Capture`；正式 OpenAPI 删除 `upload_url`、`upload_expires_at`、`CaptureUpload`、`ConfirmCaptureUploadRequest` 和独立确认端点。
- [x] 2. 存储 Adapter：用现有 boto3/S3 边界实现带背压的 staging/multipart 流式写入；失败中止，完成后验证失败删除对象，不新增依赖。
- [ ] 3. API 信任边界：在读取字节前完成授权；实现实际字节上限、媒体/文件头、宽高/像素、完整解码、增量 SHA-256、请求/空闲超时、并发/账号限速、幂等重放/冲突及稳定错误码。
- [x] 4. Flutter 迁移：只向 API 上传并展示服务端错误；删除生产上传客户端中的预签名 URL、MinIO 直连和独立确认，保留脱敏预览、手动涂抹与确认哈希。
- [x] 5. Compose 收口：示例配置删除 `OBJECT_STORAGE_PUBLIC_ENDPOINT_URL`、`MINIO_API_PORT` 和预签名 TTL；取消 `9000`/`9001` 宿主机端口映射，只允许 API/worker/备份通过内部 `minio:9000` 访问。
- [ ] 6. 质量门槛：已通过 API Ruff/Mypy/单元、Flutter format/analyze/test 和 OpenAPI 运行时路径检查；仍需完整契约差异、Compose 有真实 `.env` 的 config、断连/超时/并发/端口扫描测试。
- [x] 7. 部署迁移：先备份并部署匹配的 API/Web/worker，移除旧端点和 MinIO LAN 端口；Ubuntu synthetic 请求已走到 NewAPI，但 Provider 返回 HTTP `402`。Nova 9/iPad 真机回归和额度恢复后的 Extraction/VerifiedQuestion/Tutor 验收仍待执行。

## 验收标准

- [x] OpenAPI 和 Flutter 上传客户端响应模型中不存在 `upload_url`、`upload_expires_at`、对象键或独立上传确认合同。
- [ ] App 网络测试证明图片只发送到配置的 API 地址；代码、日志、SQLite 和错误中无 MinIO 地址或存储凭据。
- [ ] 0 字节、超过 8 MB、伪造 MIME/文件头、异常尺寸/像素、截断、哈希不一致、慢速/断连和并发请求均被服务端有界拒绝，失败无残留 staging 对象。
- [ ] 最大允许图片与批准并发下，API 内存受块大小和并发上限约束，不随请求体无界增长；MinIO/数据库部分失败可安全重试且不产生重复 Capture。
- [ ] `docker compose config` 与主机/LAN 端口检查证明没有发布 `9000`，运行配置不存在 `OBJECT_STORAGE_PUBLIC_ENDPOINT_URL`/`MINIO_API_PORT`，内部 API/worker/备份仍可访问私有 Bucket。
- [ ] synthetic 与真机均完成 `API upload → confirmed Capture → ImageAnalysis → Extraction → VerifiedQuestion`，不读取或输出真实题目内容；当前 Ubuntu synthetic 已完成上传/Provider 到达，因 HTTP `402` 尚未完成后半段。

## 兼容、部署与回滚

- 这是用户批准的破坏性预发布合同变化；API 和 Flutter 必须成对升级。不得让新 App 调旧 API，或让旧 App 在 `9000` 已关闭后继续使用预签名 URL。
- 迁移窗口只在测试环境保留旧端点；正式 OpenAPI 不同时暴露两套上传方式。确认新 App/API 通过后才关闭 MinIO LAN 端口和删除旧配置。
- 回滚必须使用上一套匹配的 API/App 镜像，并仅在隔离受信 LAN 临时恢复旧端点、`9000` 和旧配置；Bucket 继续私有，客户端永不获得长期密钥。不得删除已确认 Capture 或用清卷回滚。

---

# PLANS.md — PLAN-0013 Web 统一孩子管理与多孩子工作台

## 计划元数据

- 计划 ID：`PLAN-0013`
- 关联事项：`TODO-015`、`FR-001`、`FR-016`、`ADR-0005`、`ADR-0017`、`ADR-0019（Proposed）`
- 状态：`IN_PROGRESS（API/Web/首页选择已实现；PostgreSQL 迁移与真实部署验收待完成）`
- 优先级：`P0 / WEB UX / IDENTITY`
- Owner：Codex（后续执行）；项目 Owner（用户，交互方向已批准）
- 创建/更新：`2026-07-18`

## 问题与当前证据

- `apps/web/src/app/accounts/page.tsx` 已改为加载孩子管理聚合并用一个表单创建档案和账号；账号启停、重置密码、资料编辑、导出和删除入口集中在孩子条目。
- `apps/web/src/app/page.tsx` 已支持 `?child=<uuid>` 当前孩子选择，任务请求带孩子作用域，周报和档案卡使用同一授权孩子。
- `0016_child_account_uniqueness` 增加“一份孩子档案最多一个孩子账号”的条件唯一索引；迁移遇到历史重复绑定会明确失败，不静默删除账号。

## 目标与设计边界

- Web 将“孩子”作为一个管理聚合：一次填写姓名、年级、用户名和初始密码，一次提交后原子创建 ChildProfile 与绑定的 child Account；用户不再理解或手动选择两张表。
- 数据库不把认证与档案物理合表。`Account` 继续隔离密码哈希、锁定、状态和会话生命周期，`ChildProfile` 继续承载姓名、年级、教材和科目；API 用事务命令和聚合读模型提供单一产品体验。
- 家长账号与孩子列表分区展示。孩子卡片同时显示档案和登录状态，并集中提供编辑资料、启停账号、重置密码、导出和删除入口。
- 首页增加带可见标签、支持键盘和读屏的“当前孩子”下拉选择器。问候、今日任务、当前档案和周报必须全部按同一个已授权 `child_id` 查询；家庭孩子总数保持家庭级，设备数在设备尚未绑定孩子前也保持家庭级。
- 选择器只改变展示范围，不改变服务端授权。任意 URL、Cookie 或客户端状态中的 `child_id` 都必须重新校验 Session、Household 和角色，禁止跨家庭/跨孩子枚举。

## API、数据与兼容方案

- 在 `packages/contracts` 定义聚合写入与读取模型，例如 `CreateChildRequest { display_name, grade, curriculum_version, subjects, username, initial_password }` 和不含密码/哈希的 `ChildManagementView`。最终路径沿用 `/children` 还是新增显式聚合路径，在实现前通过 OpenAPI 差异确认；Web 不再串联两个公开创建请求。
- 单一受鉴权、带 `Idempotency-Key` 的事务同时创建 Profile 与 Account；用户名冲突、字段校验、密码策略或数据库错误时整体回滚，不留下孤立档案或孤立账号。响应不得返回初始密码、密码哈希或会话材料。
- “编辑档案”和“重置/启停账号”可保持不同内部命令与再认证策略，但 Web 统一从同一孩子管理卡进入；删除继续执行现有孩子数据级联和会话撤销。
- 实施前生成只读数据审计：已绑定的一对一记录直接聚合；无账号档案显示“未开通登录”并允许补建；同一档案绑定多个孩子账号时阻断自动迁移并要求人工选择，不静默删除。清理后增加 `(household_id, child_id)` 的 child-role 唯一约束或等价条件唯一索引，并提供前滚修复方案。
- 首页以 URL 查询参数作为本次选择的显式来源，并可持久化最近一次已授权选择；优先级为“有效显式选择 → 有效最近选择 → 稳定排序后的首个孩子”。孩子被删除或失权时清除旧选择并安全回退，零孩子时展示创建入口。
- 任务查询必须由 API/数据层按 `child_id` 过滤，周报继续要求同一 `child_id`；不得先拉取全家庭学习明细再只在浏览器隐藏其他孩子。

## 实施阶段

- [ ] 1. 契约与数据审计：确认现有账号—档案基数，补充聚合 Schema、稳定错误码、幂等语义和 OpenAPI 兼容说明。
- [ ] 2. API 事务聚合：实现原子创建/补建孩子登录、聚合查询和一对一约束迁移；保留现有档案数据并覆盖并发、回滚和反向越权。
- [ ] 3. 管理页重构：合并孩子档案/孩子账号创建表单和列表，家长账号移到独立区域；已有无账号档案提供“开通登录”，不要求输入或选择 UUID。
- [ ] 4. 首页孩子选择：增加可访问的选择器和无脚本/空状态回退；选择后统一刷新问候、任务、档案与周报，并在 URL/安全持久化状态中恢复最近选择。
- [ ] 5. 质量与发布：运行 OpenAPI 差异、迁移、API/Web 单元与集成、浏览器 E2E、生产构建、授权/CSRF/日志检查；先部署数据库/API，再部署 Web，并用两个 synthetic 孩子验证。

## 验收标准

- [ ] 新建孩子只出现一个表单和一次提交；成功后同时存在一份档案和唯一绑定账号，任一环节失败均为零新增记录，重复幂等请求不产生第二个孩子。
- [ ] 管理页每个孩子只显示一张聚合卡；卡片能区分“登录已启用/已停用/未开通”，家长账号不混入孩子卡片。
- [ ] 两个孩子场景中，选择任一孩子后，问候、今日任务数量/内容、档案卡和周报均属于同一个孩子；刷新后选择仍有效，删除当前孩子后安全回退。
- [ ] 家庭级孩子总数不随选择变化；设备在无 child 绑定模型时明确显示家庭级数据，不伪装成所选孩子的设备。
- [ ] 篡改其他 Household/未绑定孩子的 `child_id` 返回统一 403/404 且无数据泄漏；孩子会话不能使用选择器访问兄弟姐妹数据。
- [ ] 旧数据审计、重复绑定处置、约束迁移、前滚修复和 Web/API 成对回滚均有记录；日志不含密码、用户名明文或儿童姓名。

## 回滚

- Web 可回退到旧展示，但不得在已启用一对一约束后重新允许为同一档案创建多个孩子账号；API 优先保持新聚合端点并向前修复。
- 数据库迁移只新增校验/索引，不合并或删除 `accounts`/`child_profiles`。若约束上线阻塞旧写入，回滚应用并暂时移除新约束前必须保留审计结果，不删除任何孩子数据。
- 首页选择状态仅是显示偏好；回退版本忽略未知查询参数/Cookie，不影响学习事实。

---

# PLANS.md — PLAN-0014 教材驱动的数学错题学习闭环

## 计划元数据

- 计划 ID：`PLAN-0014`
- 关联事项：`ADR-0020`、`TODO-016`～`TODO-019`、`FR-002`、`FR-005`、`FR-006`、`FR-011`、`FR-017`～`FR-020`
- 状态：`IN_PROGRESS（基础实体/入口已实施；拍题到错题、证据化复习、真实文件解析/grounding 和渐进提示由 PLAN-0016 收口）`
- 优先级：`P0 产品主线 / P1 分阶段交付`
- Owner：Codex（后续执行）；项目 Owner（用户，方向与本计划原则已批准）
- 创建/更新：`2026-07-20`

## 1. 目标产品主线

将当前偏“今日任务 + 拍题 + 最小 Tutor”的实现收敛为数学首科的教材驱动错题学习系统：

```text
家长设置孩子年级/学期/教材版本
→ 导入家庭有权使用的教材与课程资料
→ 系统解析章节/知识点并由家长审核发布
→ 孩子选择“数学”
→ 错题讲解 / 复习错题 / 今日任务
→ VerifiedQuestion + 已确认作答状态（有作答 / 空白）+ 已发布知识依据
→ 分模式讲解、错题沉淀、到期复习和任务建议
```

成功标准不是“AI 给出答案”，而是每道错题都有可追溯题目、已确认的孩子作答状态、年级/教材/知识点依据、匹配作答状态的讲解记录、复习计划和后续掌握证据。

## 2. 当前实现事实与缺口

- `ChildProfile` 只有 `grade`、单个 `curriculum_version` 字符串和 `subjects=[math]`，没有学年、学期、教材版本实体、孩子教材绑定或发布快照。
- 当前已实现授权教材 manifest、多文档私有上传、SHA-256/来源声明、草稿快照、家长审核发布和版本替换；真实文档二进制解析、页码来源解析、删除/撤销链路仍待最终联调。
- `VerifiedQuestion`、TutorTurn、Attempt、StudySession 已持久化；`0020_answer_evidence` 将视觉四态候选、置信度、可见作答步骤和人工确认写入 VerifiedQuestion，Tutor 从服务端事实分支。第三级通过同一 NewAPI 对已确认文字生成步骤/答案/验算并追加写 TutorTurn；教材 grounding 和完整错步定位仍待联调。
- 当前已新增 `MistakeRecord`、`ReviewSchedule`、到期查询和原型间隔算法，但拍题讲解完成不会创建错题，复习 UI 不显示题目/收集新作答，提交接口直接信任客户端结果；这些只能称为脚手架，不能称为正式复习闭环。
- 当前已新增 `TaskRecommendation`，可从到期错题/已发布教材生成待审核项，家长批准后幂等创建数学 Task；Task 来源字段、每日上限和更细教材/错题引用仍待补齐。
- Flutter 当前首页已显示“错题讲解 / 复习错题 / 今日任务”三入口；题目确认页自动选中视觉四态候选并允许校正，练习页显示服务端确认状态和完整解答。家长 Web 已显示最近逐题题目、状态、提示、步骤、答案和验算；最终真机与浏览器 E2E 仍待执行。
- PLAN-0012 的 API 流式图片上传和 PLAN-0013 的统一孩子管理/多孩子选择已实现；本计划只在其之上补教材/错题/推荐主线，不绕过既有上传安全门禁。

## 3. 产品与交互定义

### 3.1 家长端：孩子学习范围

- 家长先选择孩子、数学、年级、学期、教材出版社/版本和适用学年，形成 `CurriculumAssignment`；更换年级/学期不覆盖历史学习记录。
- PLAN-0016/Proposed ADR-0021 将首批教材上传与解析限定为 PDF；文本 PDF 进入解析，扫描 PDF 进入待 OCR，所有 Word/PPT/Excel 新上传由 Web/API 拒绝。精确大小、页数、对象展开量和资源上限在 ADR 接受后的实现任务中批准。
- 每份 `LearningMaterial` 必须记录家庭、SHA-256、文件类型、版本、来源/授权声明、导入者和处理状态。重复文件幂等返回既有结果。
- 解析产物先进入草稿：目录、章节、知识点、页码/段落来源和置信度。家长必须审核、编辑并发布不可变 `CurriculumSnapshot` 后，Tutor/任务系统才能引用。
- 更新教材生成新版本快照；既有错题/讲解继续引用原快照，不静默漂移到新知识结构。

### 3.2 孩子端：数学三入口

- 登录并取得唯一绑定档案后显示学科页；当前只显示可用的“数学”，不制造尚未实现的语文/英语入口。
- 进入数学后固定呈现三个低干扰主入口：`错题讲解`、`复习错题`、`今日任务`。一次只进入一种模式，页面始终标明当前模式。
- 无教材、无错题、无到期复习或无今日任务时显示可操作空状态；不能用演示数据伪装真实内容。

### 3.3 错题讲解模式

1. 孩子拍摄做错或没有思路的题，画面应尽量同时包含完整题目和孩子的答题区。沿用 PLAN-0012 的 Session 鉴权 API 上传、隐私脱敏、云视觉解析和人工确认，生成 `VerifiedQuestion`。
2. 云视觉 Schema 必须分开提取题目与孩子作答，输出候选 `answer_state`：`worked`（看到作答）、`blank`（答题区可见且空白）、`unclear`（无法判定）、`answer_area_missing`（未拍到答题区），并返回置信度和作答步骤候选。该结果必须由孩子确认/修正后才成为 `AttemptEvidence`。
3. `worked` 记录可见的原答案/步骤，并允许补充审题错误、概念不清、方法错误、计算错误、粗心/抄写错误或其他自述；`blank` 在用户确认后以 `evidence_confirmed=true` 记录为 `no_approach`，不强迫孩子先编造一次错误作答。`unclear` 或 `answer_area_missing` 必须请孩子重拍或手工选择真实作答状态，不得自动当作空白。
4. 系统按孩子的已发布 CurriculumSnapshot 检索章节、知识点和最小来源片段。无可靠匹配、超出当前年级或来源冲突时明确标记 `needs_grounding_review`，不伪造教材依据。
5. `mistake_explanation` 按作答状态分支：`worked` 优先指出第一个可验证的错误步骤，解释“错在哪里/怎样改”；已确认的 `blank` 视为“没有思路”，可从题意、已知/所求和知识点开始完整讲解，无需再要求一次尝试。两个分支都要给出逐步过程、答案校验和一道低风险变式练习。
6. Schema、算术/单位等可确定规则、知识点范围和安全策略通过后，保存 `MistakeRecord` 与版本化讲解；AI 输出本身不能直接成为标准答案或掌握度事实。
7. 讲解后鼓励孩子完成一次重新作答；结果写入追加式 Attempt，并创建首个 ReviewSchedule。失败仍可保存为待家长复核，不丢原题、空白事实或已有作答。

### 3.4 复习错题模式

- 默认进入“今日到期”队列，而不是每次无差别遍历全部历史；另提供“复习全部”入口按筛选后的稳定顺序逐题过关。
- 每题先隐藏历史答案和完整讲解，要求孩子重新作答；错误时先给提示，再允许查看已批准讲解。
- `review-policy.v1` 使用可版本化的确定性间隔，初始建议为 1、3、7、14、30 天：正确晋级，错误回到 1 天并保留新 Attempt；具体间隔在实现前用家庭试用确认，AI 不直接决定到期时间。
- 每题结果原子更新 ReviewSchedule 派生状态并追加 ReviewAttempt/Attempt；重复提交幂等，历史不覆盖。连续达到批准门槛后标记“已掌握”，再次答错可重新激活。

### 3.5 今日任务模式

- `parent_assigned`：家长手工选择教材章节、已有练习或错题。
- `review_due`：系统按确定性复习策略把到期错题组成建议；在家长开启对应家庭设置后可自动下发。
- `system_suggested`：根据反复出错知识点和当前教材范围生成 `TaskRecommendation`，默认只作为家长可审核/修改/拒绝的建议，不能静默变成孩子任务。
- P1 第一阶段只从已有错题和家庭导入且已发布的练习中选题。AI 生成新变式题后置到固定正确性/难度/版权 eval 通过，并默认要求家长确认。
- Task 保存来源类型、Mistake/KnowledgePoint/Material 引用、推荐/批准者、策略版本和生成原因；周报可以解释“为什么安排”。

## 4. 领域与契约目标

### 4.1 新增或扩展实体

| 实体 | 最小职责 | 关键不变量 |
| --- | --- | --- |
| `CurriculumAssignment` | 孩子某学期的学科、年级、教材版本 | Household/Child scoped；历史不可覆盖 |
| `LearningMaterial` / `MaterialIngestionJob` | 导入文件、授权、哈希和解析状态 | 私有、版本化、幂等；原文不进入日志/Prompt |
| `CurriculumSnapshot` | 家长审核发布的章节/知识点/来源图 | 发布后不可变；Tutor 只引用已发布版本 |
| `KnowledgePoint` / `KnowledgeEvidence` | 知识点及页码/段落来源 | 每个结论可追溯到材料版本 |
| `MistakeRecord` | VerifiedQuestion、首次作答状态证据、错因/无思路、知识点和状态 | 必须有孩子/家庭、确认题目和已确认 AttemptEvidence；缺失答题区不等于空白 |
| `ReviewSchedule` | 到期时间、间隔、阶段和策略版本 | AI 不直接修改；并发/重试不重复晋级 |
| `TaskRecommendation` | 系统建议与依据 | 默认需家长批准；拒绝不生成 Task |

- 复用 `StudySession`、`Attempt`、`TutorTurn`，增加明确 `mode/source/mistake_id` 等引用；不为每个页面复制一套会话/作答模型。
- Attempt 继续追加写，扩展结构化 `answer_state`、`result`、有限答案/步骤表示和错误自述；已确认的 `answer_state=blank` 是有效学习事实而不是空数据。儿童原始作答属于 Confidential，不进入普通日志或 AI 调试。
- `AttemptEvidence` 首批作为 Attempt 内的版本化值对象/Schema，不预设独立物理表；包含作答状态、区域覆盖/置信度、有限步骤候选、用户确认来源和 Schema 版本。若后续查询/保留数据证明有独立表需求，再通迁移/ADR 调整。
- OpenAPI/Schema 统一由 `packages/contracts` 提供；所有写操作带 Idempotency-Key，列表使用稳定游标/排序和 Household/Child 过滤。

### 4.2 目标接口族

- 家长：`/children/{id}/curriculum-assignments`、`/materials`、`/material-ingestions`、`/curriculum-snapshots`、`/task-recommendations`。
- 孩子：`/subjects`、`/mistakes/explanations`、`/mistakes`、`/reviews/due`、`/reviews/{id}/attempts`、`/tasks/today`。
- 精确路径、分页和兼容版本在每个实施 TODO 的 OpenAPI 差异中确认；本计划不提前把示例路径描述成已发布合同。

## 5. AI、知识依据与安全门禁

- 图片解析和讲解保持两次独立调用：云视觉产出待确认题目以及与题目分开的作答区/作答状态候选；Tutor 只消费 VerifiedQuestion、已确认 AttemptEvidence、孩子 CurriculumAssignment 和已发布的最小知识片段。
- 教材文件和解析文本是不可信内容，不得把其中指令当系统 Prompt；检索结果以数据字段/引用传入，Prompt 采用固定边界和 Schema。
- Tutor 输出必须包含 `mode`、`curriculum_snapshot_id`、`knowledge_point_ids`、来源引用、逐步解法、最终答案、校验结果、置信/阻断状态和 Policy/Prompt/模型版本。
- “精确讲解”是质量目标，不作绝对保证。低置信度、题目识别未确认、教材不匹配、计算校验失败或超纲时阻断发布并要求重拍、校正或家长复核。
- `guided_practice/review` 模式仍先作答、再提示；`mistake_explanation` 在已确认 `worked` 或 `blank` 后允许完整过程。`unclear/answer_area_missing` 不得自动降级为空白；普通任务与复习也不得借讲解模式绕过它们各自的先作答规则。
- Provider 只接收完成当前讲解所需的最少片段，不发送整本教材、对象 URL、无关家庭历史或其他孩子数据；单 Provider、有界重试、成本与审计规则继续有效。

## 6. 分阶段交付

- [x] M0 — 前置安全与契约：PLAN-0012/0013 已落地；本轮补齐 0018 迁移和 OpenAPI 新增路径。
- [x] M1 — 教材基线（TODO-016）首版：授权 manifest、多文档私有上传、SHA-256、解析草稿、家长审核发布和孩子只读已发布快照；真实文档二进制解析/页码来源/删除仍待联调。
- [x] M2 — 数学入口与错题讲解首版（TODO-017）：Flutter 三入口、四态选择、Tutor `mistake_explanation` 分支与 Attempt 记录已实现；2026-07-20 修复视觉 VerifiedQuestion 与旧 Capture 状态门禁冲突，并将登录用户名及按已确认题目结构生成的零成本分级提示接入真机流程；真实视觉作答提取和完整错步讲解仍待联调。
- [x] M3 — 错题本与到期复习（TODO-018）：拍题 closeout 以已确认题目/作答证据原子完成会话并创建错题；复习返回题目、追加 ReviewAttempt，服务端按 `review-policy.v2` 判定并使用 1/3/7/14/30 天序列。
- [x] M4 — 今日任务建议（TODO-019）首版：到期错题/已发布教材生成推荐，家长批准/拒绝，批准后幂等生成 Task；每日上限和来源细化待完成。
- [ ] M5 — 质量与发布：代码质量门槛已通过；仍需完成固定教材/ Tutor eval、真实 Ubuntu 前滚、双孩子/跨家庭、弱网、迁移恢复、成本与删除验收及设备相机闭环。

## 7. 核心验收

- [ ] 家长能为两个孩子分别设置不同年级/教材，导入一份 synthetic PDF，审核章节/知识点并发布；未发布/跨家庭内容无法被 Tutor 检索。
- [ ] 孩子端登录后先看到数学，数学页准确显示三个入口；每个空状态和失败状态都能恢复。
- [ ] 一道错题必须完成安全上传、题目确认和作答状态确认后才能进入完整讲解；有作答时定位可验证错误，确认空白时从头讲解，答题区缺失/不清时不得自动当空白；讲解引用当前孩子已发布知识范围，并通过 Schema/计算校验。
- [ ] 讲解完成原子创建一条 MistakeRecord 和一个 ReviewSchedule；重试不重复，删除/导出覆盖其题目、作答、讲解和复习历史。
- [ ] 到期复习队列逐题展示且先作答；正确/错误按同一 Policy 产生可复算结果，刷新、断网重试和并发提交不覆盖历史或重复晋级。
- [ ] 今日任务能区分家长安排、到期复习和系统建议；系统建议默认未经家长批准不进入孩子任务，所有安排可解释到错题/知识点/教材来源。
- [ ] 固定数学 eval 覆盖题目识别错误、有作答多步骤提取、真实空白、浅色铅笔字/涂改被误判空白、答题区未入镜、人工修正、教材错版/超纲、计算/单位错误、Prompt 注入、低置信度、Provider 失败、模式绕过和成本上限。

## 8. 兼容、迁移与回滚

- 先扩展现有 Task/Session/Attempt，不重写既有历史；当前 `needs_review` 会话可迁移为“待人工补全”的 Mistake 候选，不能凭一个布尔结果伪造错误答案、已确认 `blank` 或知识点。
- Curriculum/Mistake/Review/Recommendation 使用新迁移和独立开关。部署顺序为数据库 → API/worker → Web 家长审核 → Flutter 三入口；未达到当前里程碑时入口保持隐藏或明确不可用。
- 回滚应用时保留新表和历史引用，优先前滚修复；不得删除教材、错题、Attempt、复习结果或把 ReviewSchedule 倒退覆盖。关闭 AI 时保留手工建档、手工错因和已有复习队列。
- 教材解析结果、AI 讲解和任务推荐均为可重算派生数据；家长已发布的 Snapshot、VerifiedQuestion、Attempt 和审批事实不可静默重算覆盖。

## 9. 明确后置范围

- 多题整页自动分割、语文/英语、语音、公开题库、教师/学校组织、社交排名继续后置。
- 视频讲解只有在来源版权、年龄适配、题目匹配、字幕/可访问性和离线降级通过独立评审后再接入；当前完整文字/图示解题流程是必达兜底。
- AI 自动生成全新练习题、无需家长审核的个性化课表和 AI 自动判定永久掌握不属于首批实现。

---

# PLANS.md — PLAN-0001 项目上下文建档

> 当前计划只覆盖 `TASK-0001` 的文档初始化，不创建业务代码或部署资源。

## 计划元数据

- 计划 ID：`PLAN-0001`
- 关联任务：`TASK-0001`
- 状态：`COMPLETE`
- Owner：Codex（执行）；项目 Owner `TBD`
- 基线：`master`，无 commit，全部文件 untracked
- 创建/更新：`2026-07-12 14:36 CST`

## 1. 目标结果

完成后，新会话能在 3 分钟内通过 `AI_CONTEXT.md` 理解家庭 AI 学习助手的当前零实现状态、P0/P1/P2 目标、唯一事实源、硬约束、开放决策、风险和推荐第一项任务。

## 2. 上下文与约束

- 当前行为：只有设计稿和通用上下文模板；无代码、依赖、CI、测试或部署。
- 目标行为：所有根目录上下文主文档具体、交叉一致，未知项有 Owner/截止条件，不虚构实现。
- 不变量：孩子端低干扰、AI 不直接代答、家庭强隔离、数据最小化、离线不丢、契约/模型可替换、内容版权边界。
- 禁止事项：不修改 DOCX/Prompt/ADR 模板；不写业务代码；不安装依赖；不部署、提交或推送；不自行批准许可证/法域/Provider/SLO。
- 关键依赖：`家庭AI学习助手_架构设计_v1.0.docx`、`AGENTS.md`、`PROJECT.md`、`prompts/00-project-bootstrap.md`。

## 3. 相关文件与入口

| 路径 | 作用 | 本计划输出 |
| --- | --- | --- |
| `AI_CONTEXT.md` | 3 分钟项目入口 | 当前事实、导航、约束、下一步 |
| `PRD.md` | P1 产品事实源 | 用户、流程、需求、NFR、验收、开放项 |
| `ARCHITECTURE.md` | 目标系统事实源 | 组件、数据流、接口、数据、NFR、边界 |
| `TESTING.md` | 质量事实源 | 当前可运行检查和 P0/P1 目标命令/门槛 |
| `SECURITY.md` | 安全事实源 | 儿童数据、身份、AI、供应链和生产阻塞 |
| `RUNBOOK.md` | 运维事实源 | NOT_DEPLOYED 状态和生产前契约 |
| `TASK.md`/`TODO.md` | 当前执行与队列 | 关闭建档任务，推荐首个 P0 任务 |
| `DECISIONS.md` | ADR 索引 | 明确无已接受 ADR，列优先候选 |
| `CHANGELOG.md` | 已发布变化 | 明确暂无产品发布 |

## 4. 分阶段计划

### Milestone 1 — 证据扫描

结果：确认仓库、Git、DOCX、依赖/入口/测试/CI/部署现状。

- [x] 按 AGENTS 顺序读取所有主文档和 bootstrap Prompt。
- [x] 使用 `rg/find/git` 验证仓库结构和 Git 状态。
- [x] 提取 DOCX 段落/表格并渲染、检查全部 3 页。
- 验证：31 段落、6 表格、3 页；Git `master` 无提交；无代码/清单/CI/部署。

### Milestone 2 — 主文档项目化

结果：产品、架构、质量、安全和运维事实源可审查。

- [x] 更新 `PROJECT.md` 的 Git 现状和文档状态。
- [x] 完成 `PRD.md`、`ARCHITECTURE.md`、`TESTING.md`、`SECURITY.md`、`RUNBOOK.md`。
- [x] 目标架构全部标记为尚未实现，开放阈值保留 `TBD`。
- 验证：逐文档核对设计稿和唯一事实源职责。

### Milestone 3 — 状态与交接

结果：当前任务、计划、决策、队列和变更状态一致。

- [x] 刷新 `AI_CONTEXT.md`、`TASK.md`、`TODO.md`、`DECISIONS.md`、`CHANGELOG.md`。
- [x] 推荐 `TODO-001` 为首个 P0 任务并限制范围。
- [x] 运行占位符、表格、引用、敏感信息和工作区检查。
- [x] 填写 Closeout，将 TASK/PLAN/AI_CONTEXT 状态改为完成。

## 5. Progress

- `2026-07-12 14:36 CST` — `[done]` 完成仓库与 DOCX 扫描；发现 Git 已初始化但无提交，所有文件未跟踪。
- `2026-07-12` — `[done]` 完成 PRD、架构、测试、安全、Runbook 项目化。
- `2026-07-12` — `[done]` 刷新状态文档；13 份上下文、32 个表格结构检查 0 错误，引用和敏感信息检查通过。

## 6. Surprises & Discoveries

- `2026-07-12` — 发现：相较上一轮，目录现已是 Git 仓库，但 `master` 无 commit；证据：`git status --short` 和 `git log`；影响：更新 `PROJECT.md`，同时强调 Git 无法恢复未跟踪文件。
- `2026-07-12` — 发现：设计稿在当前 LibreOffice 环境渲染中文缺字，但 OOXML 文本/表格完整；证据：DOCX 提取与 3 页 PNG；影响：产品/架构事实可读取，视觉发布需 `TODO-006`。
- `2026-07-12` — 发现：无任何业务代码、依赖、配置、迁移、测试、CI 或部署；证据：全文件扫描；影响：所有工程命令只能作为 P0 验收目标，不能报告通过。

## 7. Decision Log

- `2026-07-12` — 决定：不创建业务脚手架；原因：bootstrap Prompt 明确只建档；替代方案：同时初始化代码会扩大范围；ADR：否。
- `2026-07-12` — 决定：把 v1.0 设计写成 Draft/目标架构，不标为已实现或已接受 ADR；原因：无代码、无具名批准/权衡；ADR：后续需要，见 `DECISIONS.md`。
- `2026-07-12` — 决定：未知性能、合规、保留、Provider 和运维数值保留带 Owner/截止条件的 `TBD`；原因：缺少测量和授权；ADR：部分需要。

## 8. 验证与验收

```bash
rg -n '\{\{|\}\}' AGENTS.md AI_CONTEXT.md ARCHITECTURE.md CHANGELOG.md DECISIONS.md PLANS.md PRD.md PROJECT.md RUNBOOK.md SECURITY.md TASK.md TESTING.md TODO.md
git status --short
git diff --check
```

- [x] 非模板上下文无双花括号模板占位符，Markdown 表格列数和引用正确。
- [x] 常见密钥/凭据模式无命中，工作区无意外生成物。
- [x] `TASK.md`、本计划和 `AI_CONTEXT.md` 完成状态一致。
- [x] 最终汇报列出冲突、未知、风险、建议 ADR/TODO 和首个任务。

## 9. 回滚与恢复

- 可逆步骤：所有变更仅为 Markdown，可按文件回退。
- 不可逆步骤：无；未提交、未部署、未改 DOCX。
- 回滚流程：由于无基线 commit，只能使用编辑器本地历史或会话前内容逐文件恢复；不要用 `git clean` 删除未跟踪文件。
- 数据恢复：不适用；仓库没有业务数据。

## 10. Closeout

- 实际结果：所有根目录上下文主文档已项目化，目标/现状/开放决策分离；`AI_CONTEXT.md` 可作为下一会话入口，`TODO-001` 可转为首个 P0 任务。
- 与原计划的差异：发现 Git 已初始化而非完全无仓库；其余按 bootstrap 范围执行。
- 未解决事项：Owner、远程/许可证、版本/工具链、法域/保留、身份/Provider、SLO/RPO/RTO 和生产平台。
- 经验：在零代码阶段，最重要的是区分已验证现状、目标设计和待批准决策；工程命令不能凭技术栈推断为已可用。

---

# PLANS.md — PLAN-0002 P0 仓库骨架与质量门槛

## 计划元数据

- 计划 ID：`PLAN-0002`
- 关联任务：`TASK-0002`
- 状态：`COMPLETE`
- Owner：Codex（执行）；项目/技术 Owner `TBD`
- 创建/更新：`2026-07-12`

## 目标与边界

建立 `TODO-001` 所需的 contracts、API、Web、Flutter、evals、Compose 和 CI 最小边界，生成唯一锁文件并运行可用的质量命令。只建立健康端点和空壳消费者，不进入家庭业务、身份、迁移、离线同步、AI Provider 或真实数据。

## 阶段

- [x] 1. 读取上下文和设计基线，确认 `TODO-001` 是用户“开始开发”对应的最小首项。
- [x] 2. 写入目标目录、入口、合同、Compose、CI、忽略规则和脱敏环境样例。
- [x] 3. 使用批准/可用的 uv、pnpm、Flutter 工具链生成三类锁文件并修正解析版本。
- [x] 4. 运行 API/Web/Flutter/Compose 验证，补齐 `TESTING.md` 的实际状态；原生平台构建阻塞原因已记录。
- [x] 5. 工作区和安全审查，更新 `TASK.md`、`AI_CONTEXT.md`、`TODO.md`、ADR 与变更记录。

## 关键假设与阻塞

- 版本基线暂记录在 `docs/adr/0007-toolchain-and-scaffold-baseline.md`，状态为 Proposed，不等同于 Owner 批准。
- API/Web/Flutter 依赖已解析；Flutter 原生构建仍依赖本机 Android SDK、完整 Xcode 和 CocoaPods。
- Docker CLI 可用，但 Compose 启动会创建本地服务；在确认配置无外部连接且完成静态检查前不自动启动持久化服务。

## 回滚

本计划只产生未提交的本地文件。回滚时逐文件恢复本轮改动，不使用 `git clean`、强制 checkout 或删除用户未知文件。

## Closeout

- `TASK-0002` 和 `TODO-001` 已完成；P0 代码、锁文件、验证入口和文档状态一致。
- 原生平台构建保留为环境前置项，不扩大任务范围安装 Android Studio、Xcode 或 CocoaPods。

---

# PLANS.md — PLAN-0003 家庭/孩子/设备首个纵向切片

## 计划元数据

- 计划 ID：`PLAN-0003`
- 关联任务：`TASK-0003`
- 状态：`COMPLETE`
- Owner：Codex（执行）；产品/技术 Owner `TBD`
- 创建/更新：`2026-07-12`

## 阶段

- [x] 1. 读取 PRD/架构/安全边界，确认只做合成数据和 local/CI demo 主体。
- [x] 2. 建立 OpenAPI children/devices 增量和 Proposed 契约 ADR。
- [x] 3. 建立 API domain/repository/auth adapter/routes，并覆盖家庭隔离、角色和幂等。
- [x] 4. 补充 Web/Flutter 的契约入口，不复制手工领域模型。
- [x] 5. 运行质量门槛、更新文档并完成回滚/残余风险记录。

## 不变量

- Household 是每个资源的授权边界；跨 Household 访问返回 404。
- Demo principal 仅是测试适配器，不能被描述为真实认证。
- 内存仓储仅用于合成 vertical slice，不替代 PostgreSQL 事实源。
- 所有写接口带 `Idempotency-Key`，重复请求不产生重复副作用。

## Closeout

- `TASK-0003` 和 `TODO-003` 已完成；API、契约、Web/Flutter 合成消费入口和验证记录已同步。
- 真实认证、PostgreSQL 持久化和 SDK 生成器继续由后续 ADR/任务决定。

---

# PLANS.md — PLAN-0004 核心 ADR 起草与审批准备

## 计划元数据

- 计划 ID：`PLAN-0004`
- 关联任务：`TASK-0004` / `TODO-002`
- 状态：`COMPLETE`
- Owner：Codex（起草）；项目/技术/安全/产品/法务/运维 Owner `TBD`（审批）
- 创建/更新：`2026-07-12`

## 目标与边界

为八项核心决策建立可审批 ADR，并同步主文档。ADR 只起草为 `Proposed`；本计划不指定具名 Owner、不批准真实数据/Provider/部署，也不实现后续业务任务。

## 阶段

- [x] 1. 复读项目、架构、产品、安全、测试、Runbook、决策和当前任务，确认 TODO-002 的依赖与审批边界。
- [x] 2. 使用 `/usr/local/flutter/bin/flutter` 复核迁移后的 SDK；记录 iOS/Android 原生构建事实。
- [x] 3. 建立/补齐 ADR-0001 至 ADR-0008，保证模板字段、选项、权衡、迁移与验证完整。
- [x] 4. 同步 DECISIONS、TASK、TODO、AI_CONTEXT、架构/安全/运维/测试事实，运行文档与工作区验证。

## 审批清单

| ADR | 需要的具名审批 |
| --- | --- |
| ADR-0001/0002/0003/0007 | 技术负责人；需要时项目 Owner |
| ADR-0004/0005 | 产品、技术与安全 Owner |
| ADR-0006 | 项目、产品与安全/法务 Owner |
| ADR-0008 | 项目、技术、运维与安全 Owner |

## 回滚

变更仅为 Markdown；逐文件恢复本轮内容即可。不得通过 Git 清理未跟踪文件，也不得把 `Proposed` 自动改为 `Accepted`。

## 当前结果

- 项目 Owner（用户）已于 `2026-07-13` 批准 ADR-0001～0008；所有 ADR 改为 `Accepted`，但其中定义的真实数据、Provider、法域和 staging 前置条件未被解除。
- Flutter 3.44.6 已通过交互式 PATH 验证；Android/iOS 原生构建均已验证，详细结果见 `TESTING.md`。

---

# PLANS.md — PLAN-0005 Task/Session/Attempt 与离线同步基础

## 计划元数据

- 计划 ID：`PLAN-0005`
- 关联任务：`TASK-0005` / `TODO-007`
- 状态：`COMPLETE`
- Owner：Codex（执行）；项目 Owner（用户，ADR 已批准）
- 创建/更新：`2026-07-13`

## 目标与边界

实现数学任务、StudySession、Attempt 和版本化离线同步的第一条安全数据流。先完成契约、领域规则、API 和 Flutter 待同步队列边界；随后在同一任务中接入 PostgreSQL 迁移/持久仓储和集成测试。禁止以进程内状态作为完成声明，禁止接入真实数据、Capture、Tutor 或生产认证。

## 阶段

- [x] 1. 复核 PRD、架构、安全、已接受 ADR、现有 API/合同和工具链，建立活动任务。
- [x] 2. 在 `packages/contracts` 定义 Task/Session/Attempt/SyncBatch 的向后兼容合同与 Schema 版本。
- [x] 3. 在 API 的 Plan/Task/Session 模块实现授权、状态机、追加 Attempt、事件幂等与冲突结果，并写正反向测试。
- [x] 4. 建立 Flutter 待同步队列边界和最小测试；公共模型仍以合同生成策略为目标，避免复制完整领域语义。
- [x] 5. ADR-0009 已 Accepted；Docker Desktop/local PostgreSQL、依赖锁定、首个 migration 与 downgrade/upgrade 演练已完成；PostgreSQL 仓储、连接池重连、并发版本冲突与回滚/前滚验证通过。
- [x] 6. 审查差异和 synthetic 数据边界，更新测试/架构/任务/上下文并填写完成记录。

## 不变量

- Household 授权优先于资源披露；跨 Household 统一 404。
- Attempt/AuditEvent 追加写；客户端事件、时间和版本均不可信。
- 同键同载荷重放同一结果，同键异载荷冲突；任务状态不用最后写入覆盖。
- local/CI 仅使用 synthetic fixtures；Docker 持久卷只有在检查本地配置后才启动。

## 回滚

新增合同只做兼容性增量。迁移阶段先扩展、再迁移、最后收缩；优先前向修复，绝不通过删除 Attempt、AuditEvent 或客户端队列来恢复。

## Closeout

- `TASK-0005` / `TODO-007` 已完成：`0.3.0` Learning 合同、Household/角色边界、追加 Attempt/Audit、幂等同步队列、Alembic schema 和可选 PostgreSQL 仓储均已交付。
- 验证包含 11 项 API 单元测试、4 项本地 PostgreSQL 集成测试、迁移 downgrade/upgrade、OpenAPI 结构检查和 Flutter 4 项测试；只使用 synthetic 数据。
- 未包含真实认证、Flutter SQLite 持久化、真实设备离线或 staging/production 恢复演练；后续必须以新任务处理。

---

# PLANS.md — PLAN-0006 Capture 与人工校正安全基础

## 计划元数据

- 计划 ID：`PLAN-0006`
- 关联任务：`TASK-0006` / `TODO-008`
- 状态：`COMPLETE`
- Owner：Codex（执行）；项目 Owner（用户，明确授权 TODO-008）
- 创建/更新：`2026-07-13`

## 目标与边界

建立 Capture 的服务端安全数据流：受限媒体声明 → 必须人工校正 → 追加校正事件；已按 ADR-0010～0012 完成本地 MinIO 与本地 PaddleOCR 的 synthetic 安全基础。`2026-07-15` 起目标由 ADR-0015 调整为“本地 PrivacySanitizer → 用户确认脱敏副本 → 单一获批云视觉解析 → 题目人工确认”；现有本地完整 OCR 保留为迁移事实/关闭的回滚能力。真实儿童图片、生产保留/备份和具体云 Provider 仍不在范围内。

## 阶段

- [x] 1. 复核 PRD、架构、安全、测试、已接受 ADR、工作区和现有 Learning 代码，记录文档与代码基线冲突。
- [x] 2. 在 `packages/contracts` 增加向后兼容 Capture/Correction `0.4.0` 合同和结构检查。
- [x] 3. 在 API 建立 Capture 领域模型、child-only 授权路由、内存参考仓储与 PostgreSQL 事务仓储，禁止原始媒体/文本进入审计。
- [x] 4. 新增版本化迁移与 local PostgreSQL 集成测试，覆盖家庭隔离、幂等、校正追加和 downgrade/upgrade；真实多请求并发仍待下一里程碑。
- [x] 5. 已锁定并安装 `boto3==1.43.46`、Pillow `12.3.0`、PaddleOCR `3.7.0`、PaddlePaddle CPU `3.3.1` 与模型清单；私有 MinIO 预签名 Adapter、`0.5.0` 上传签发/服务端确认端点、`0003`～`0006` 对象键/生命周期/OCR Job Ledger 迁移、过期清理器、按 Household/Child 的 Capture 对象级联删除编排、local/CI 家长删除顺序与幂等入口、家长保存/立即删除图片、synthetic PostgreSQL/MinIO 测试、预置模型目录的 OCR Adapter、对象有界读取、图片容器头部校验、完整像素解码/无 EXIF 规范化重编码、PaddleOCR 文本结果纯解析、临时文件执行边界、`0005` OCR 候选结果事务持久化、幂等 OCR 入队/PostgreSQL 行锁队列、固定 `ocr-synthetic-v1` 评测和 linux/amd64 synthetic 真实模型烟测已完成。Redis/外部 Worker 适配、Ubuntu 原生基准/真实题型评测与生产 Profile/派生对象/备份级联仍在后续范围。
- [x] 6. 已执行相关质量门槛、安全审查和文档同步；真实设备、备份/法域和商业 Provider 的未完成项已记录。
- [x] 7. 读取项目 Owner 提供的架构讨论，建立并接受 ADR-0015；同步产品、架构、安全、决策、任务、测试和运维边界，明确旧代码与新目标冲突，本轮不修改代码/合同/迁移。
- [x] 8. 兼容实现里程碑已建立：Provider-neutral 脱敏/图片分析 Schema、PrivacySanitizer synthetic eval、本地检测信号、Flutter 脱敏预览/手动涂抹、旧 Capture 对象 SHA-256 核验、ImageAnalysis ledger/API、无 Provider offline Tutor Policy、Tutor hints API 和固定 Tutor synthetic eval 已完成。
- [x] 9. 自用部署边界已实现：ADR-0016 HMAC Bearer 令牌、Web/Flutter token 注入、OpenAI-compatible NewAPI Adapter、显式 enabled gate、0009 QuestionExtraction 持久化、ImageAnalysis queued worker、stale lease/稳定失败状态和提取读取合同已完成；NewAPI 仍默认关闭。
- [x] 10. 自用 Compose 交付边界已补齐：API/迁移镜像包含 Alembic 与 worker 入口，Compose 编排 PostgreSQL/Redis/MinIO/API/迁移、家长 Web 和默认 ImageAnalysis worker，配置样例与启动/升级/回滚文档已建立；完整启动、真实 NewAPI 联调、备份恢复和生产监控仍未验证。
- [x] 11. 优化本地开发体验：Flutter 首帧后提供有限时长启动过渡并与档案加载并行；ImageAnalysis worker 进入 Compose 默认 profile 且 Provider 关闭时安全空闲；API 镜像移除固定 amd64，验证 Linux/arm64 原生调试构建，同时保留 amd64 Paddle OCR 发布能力。

## Progress

- `2026-07-13` — `[done]` 为 OCR 边界增加 `read_object` 有界读取、声明大小/SHA-256 校验，以及 JPEG/PNG 容器头、尺寸、像素数和 JPEG EXIF 拒绝测试；完整像素解码和 EXIF 清理仍未宣称完成。
- `2026-07-13` — `[done]` 增加 PaddleOCR `rec_texts/rec_scores` 结果纯解析器；结果形状、置信度、控制字符和长度经校验，低置信度和空结果均保留人工确认路径。
- `2026-07-13` — `[done]` 增加本地 OCR 执行边界：安全输入仅写入临时文件供 `predict` 使用，调用结束后清理；引擎错误统一脱敏为 `OcrExecutionError`。
- `2026-07-13` — `[done]` 增加 Pillow `12.3.0` 显式锁定依赖；OCR 前对 JPEG/PNG 执行完整像素解码、EXIF 方向归一化和无元数据重编码，截断/无法解码的像素不会进入 PaddleOCR。linux/amd64 最终镜像无网络 synthetic PNG 烟测通过。
- `2026-07-13` — `[done]` 增加 `0005_ocr_result_persistence`、Provider-neutral 候选草稿和 PostgreSQL 事务仓储；保存候选文本及 Provider/模型/Schema 版本，空结果也保存，强制人工确认，支持幂等重放和 Household/Child 读取隔离，审计不保存候选原文。
- `2026-07-14` — `[done]` 增加 `evals/ocr_synthetic_v1.json` 与无 Provider/无网络的固定 OCR 合同评测 runner；6 个 cases 覆盖正常候选、低置信度、空结果、空行和拒绝路径，结果仅输出聚合摘要。
- `2026-07-14` — `[done]` 增加 `LocalOcrJob` Worker：已确认 Capture 才能进入有界对象读取、图片规范化、本地 OCR 和候选结果持久化；未确认上传、非法图片或 Provider 失败均不落库，Redis/外部 Worker 仍保留在后续范围。
- `2026-07-14` — `[done]` 增加 child-only 幂等 OCR 入队端点、`InMemoryOcrJobQueue`、PostgreSQL Job Ledger 和单次 `LocalOcrDispatcher`；成功只关联结果 ID，失败只记录稳定错误码，新的幂等键可重试，stale lease 可恢复。
- `2026-07-14` — `[done]` 将 OCR 失败接入 ADR-0011 生命周期：从失败发生时设置 `ocr_failure` 七天期限，重复失败不延长，到期清理继续复用现有行锁和可重试删除流程。
- `2026-07-14` — `[done]` 新增 `0006_ocr_job_ledger` 并完成 PostgreSQL 迁移/队列集成回归；完整 API 门槛为 64 项单元、15 项 PostgreSQL/MinIO 集成。
- `2026-07-14` — `[done]` 增加独立一次性 `run_ocr_worker.py` 入口；组装 PostgreSQL Queue、MinIO、预置 PaddleOCR 模型和 `LocalOcrJob`，启动/运行错误只输出稳定状态码。
- `2026-07-14` — `[done]` 增加 child-only OCR 结果读取路由与 `OcrResultWithCandidates` 合同；重新校验 Household/Child/Capture 绑定，候选结果只能进入人工确认流程；定向路由测试覆盖兄弟孩子、家长、跨家庭和 Capture 不匹配。
- `2026-07-14` — `[done]` 增加 child-only OCR 候选确认路由；只提交候选 ID 与 Capture 版本，复用 CaptureCorrection 追加写、版本冲突和幂等事务，OCR 结果保持不可变；PostgreSQL 组合回归覆盖候选确认。
- `2026-07-13` — `[done]` 增加按 Household/Child 边界原子认领 Capture 对象的级联删除编排；对象逐项删除，成功标记 `deleted`，失败标记 `failed` 并可重试，内存单元与 PostgreSQL 集成回归覆盖成功、失败重试、重复运行和错误 Household。
- `2026-07-14` — `[done]` 按客户端原型顺序实现 Flutter 第 1/2/3 张横屏 UI：学习桌、拍题输入页、OCR 题目确认页与分数思考提示页；加入 `image_picker 1.2.3` 相机/相册入口、iOS 权限声明、合成图片、候选文本编辑/确认、两级提示和思考状态交互，6 项 Widget 测试与静态分析通过。含原生插件的无签名 iOS `Runner.app` 已构建并重新安装到实体 iPad，用户已实机确认拍照、权限和“已选择题目照片”页通过。Flutter 不支持实体设备截图，目标 landscape QA 仍待 Xcode 设备查看器或手动截图。
- `2026-07-14` — `[done]` 增加 Flutter `CaptureApiClient`：使用 `crypto 3.0.7` 计算 SHA-256，按服务端合同完成预签名 PUT、确认和 OCR 幂等入队；本地 HTTP 合同测试覆盖请求顺序、图片头、上传字节和稳定幂等边界，Flutter 总测试数增至 8。真实设备接线仍等待有效 StudySession 和 iPad 可达的 MinIO 预签名地址。
- `2026-07-14` — `[done]` 将 `CaptureApiClient` 接入显式 `STUDY_CAPTURE_SESSION_ID` 调试开关；真实上传后页面只显示私有上传完成和 OCR 排队状态，不把合成候选当作真实结果。使用合成 StudySession 和 iPad 可达 MinIO 完成实体 smoke test，API 日志确认上传/确认/入队为 201/201/202。
- `2026-07-14` — `[done]` 增加 child-only OCR Job 状态读取路由和 OpenAPI 路径；Flutter 客户端可解析稳定 Job 状态和 `result_id`，跨孩子边界回归通过。
- `2026-07-14` — `[done]` Flutter 确认页接入有界 OCR Job 轮询、`result_id` 候选读取、人工确认和手工纠正；候选返回前保持等待，候选返回后不自动代答。客户端 HTTP 合同测试增至 3 项，Flutter 总测试数增至 9。
- `2026-07-14` — `[done]` 增加显式 local durable mode：API 的 Learning/Capture、OCR Job 和结果仓储可统一使用 PostgreSQL；Worker 增加可选 `--watch` 轮询模式，默认一次性命令保持不变。Ruff、Mypy、74 项 API 非集成测试和 `git diff --check` 通过。
- `2026-07-14` — `[done]` 完成 PostgreSQL/MinIO synthetic API + Worker 闭环回归：真实走签名对象上传、Job Ledger 领取/完成、`LocalOcrJob` 安全读取/规范化、候选结果持久化和 child-only 读取；Provider 使用 synthetic adapter，完整集成回归 17 项通过并清理对象。
- `2026-07-14` — `[done]` 增加 Ubuntu 24.04 CPU 真实模型评测预检；只检查 Linux/Ubuntu 24.04、x86_64、Python 3.12、Paddle 锁定版本和五个 SHA-256 模型目录，不读取图片、不下载模型。macOS 预检按预期阻塞。
- `2026-07-14` — `[done]` 增加 `ocr-model-synthetic-v1` 锁定模型 smoke runner；只在预检通过后生成内存 synthetic 数学题图、调用 PP-OCRv6 medium CPU Adapter，并输出 case 状态/延迟聚合，不接受图片路径或输出 OCR 原文。当前 macOS 预检阻塞，真实推理仍待 Ubuntu 环境。
- `2026-07-14` — `[done]` 优化 `LocalPaddleOcrAdapter` 的实例级引擎缓存：文本/公式引擎按需只初始化一次，重复使用前仍执行模型目录和 SHA-256 标记校验；新增复用回归测试，避免持久化 Worker 按图片重复加载模型。
- `2026-07-15` — `[done]` 补齐 `PP-FormulaNet_plus-M` 按需执行和 `rec_formula` 解析，公式无 Provider 置信度时固定走低置信度人工确认；锁定模型 smoke fixture 增加公式 case，真实推理继续受 Ubuntu 24.04 CPU 预检门禁保护。
- `2026-07-15` — `[done]` 将 OCR mode 以向后兼容的 `text` 默认值贯穿 OpenAPI、Flutter Capture 客户端、内存/PostgreSQL Job Ledger 和 Worker；新增 `0007_ocr_job_mode`、模式幂等冲突保护及普通/公式分流回归，旧客户端不发送请求体时行为不变。
- `2026-07-15` — `[done]` 完成 `0007_ocr_job_mode` 的本地 synthetic PostgreSQL downgrade/upgrade 往返验证；固定 `ocr-synthetic-v1` 评测 6/6 通过，当前 macOS 的真实模型 smoke 按预检稳定阻塞，未执行真实推理。
- `2026-07-15` — `[done]` 项目 Owner 将 OCR 定位改为本地脱敏、云端多模态解析；新增 ADR-0015 并将 ADR-0012 标记为被替代。为避免静默改写已实现行为，旧 OpenAPI/迁移/Worker/Flutter OCR 路线保持兼容。
- `2026-07-15` — `[done]` 新增 Provider-neutral PrivacySanitization/ImageAnalysisJob/QuestionExtraction/VerifiedQuestion Schema；实现本地 PrivacySanitizer 元数据清除、检测区域实色覆盖、不可逆重编码和不安全信号阻断，接入 OCR/规则敏感区域信号，6-case synthetic eval 通过。
- `2026-07-15` — `[done]` Flutter 拍题路径新增本地脱敏预览、手动涂抹、确认后不可逆 PNG 与 SHA-256；上传客户端只接收确认后的脱敏字节。Widget/analyze 通过，真实 iPad 渲染和手动涂抹仍需人工回归。
- `2026-07-15` — `[done]` Capture 上传确认新增私有对象实际 SHA-256 核验；对象存储、上传路由和 MinIO/PostgreSQL 集成回归通过，错误哈希会阻断状态推进。
- `2026-07-15` — `[done]` 新增 0008 receipt-only ImageAnalysis ledger/API；服务端绑定 Capture 版本和脱敏副本哈希，Provider 未启用时返回 `blocked/provider_not_enabled`，Flutter 新上传路径不再误启动旧 OCR。
- `2026-07-15` — `[done]` 完成 0008 receipt/API 到 queued/blocked 双态迁移，并新增 0009 QuestionExtraction 记录、PostgreSQL claim/complete/fail worker、失败稳定错误码和手工 review 读取路径；未确认提取不进入 Tutor。
- `2026-07-15` — `[done]` 新增无 Provider 的 `offline-tutor-policy.v1` 和 `tutor-hint.v1` Schema；固定输出 1～3 级提示、要求孩子回应、`direct_answer: null` 和 0 元成本，3-case synthetic eval 通过；Flutter 思考页同步支持第 3 级提示。
- `2026-07-15` — `[done]` 补齐自用 Compose 全栈部署：新增 `migrate`、API、家长 Web 和默认 ImageAnalysis worker，API 镜像复制迁移/脚本入口并保留构建期模型 SHA-256 门禁；新增 Web standalone Dockerfile、健康端点、`.env.example`、自动读取的 `.env` 与部署/升级/回滚说明。Compose 默认服务展开、Web 镜像构建和 Web 质量门槛通过，完整容器启动仍待本机执行。
- `2026-07-15` — `[done]` 按项目 Owner 的本机调试需求增加 Flutter 1.2 秒启动过渡（首页并行加载、减少动态效果时跳过）、将 ImageAnalysis worker 移入默认 Compose profile 并在 Provider 关闭时安全空闲；API 镜像改为宿主架构原生构建。Linux/arm64 无本地 Paddle OCR/模型/专用系统库的调试镜像已构建，amd64 继续保留锁定模型与旧 OCR 回滚能力。
- `2026-07-16` — `[done]` TASK-0006 代码闭环完成：人工确认接口生成 VerifiedQuestion，worker 成功/失败分支清理派生对象；synthetic NewAPI 联调、iPad 真实脱敏预览回归、备份级联和生产监控转为环境验收项。

## 不变量

- Capture 属于 Household、孩子和 StudySession；跨 Household 或未绑定孩子统一返回 404。
- 新 Capture 在 PrivacySanitizer/云视觉 Provider 未获准或不可用时必须保留重新裁剪、手工涂抹/录入和 `needs_correction` 路径；不得伪造可信解析结果或发送原图。
- 原始媒体、对象键、签名 URL、完整题目和校正文本不得进入审计、错误响应、日志或测试输出。
- 原图、对象键、签名 URL 和敏感 OCR 文本不得发送给云端；未通过安全门禁/用户确认的脱敏副本不得外发，同一图片不得自动广播给多个 Provider。
- Correction 追加写；同键同载荷重放原结果，同键异载荷冲突；派生版本由服务端控制。

## 回滚

保持 OpenAPI 兼容增量。发生安全问题时关闭云视觉/图片外发开关并降级为重新裁剪或手工录入；可显式启用已验证本地 OCR 作为不外发回滚 Provider，但不得重解释历史记录、发送原图、恢复已删除副本或删除校正/审计记录。

---

# PLANS.md — PLAN-0011 P1 核心闭环全仓收口

## 计划元数据

- 计划 ID：`PLAN-0011`
- 关联任务：`TASK-0009`、`TODO-009`、`TODO-010`、`PLAN-0007`、`PLAN-0008`、`PLAN-0010`
- 状态：`COMPLETE（非实体设备范围已全部交付并验证）`
- Owner：Codex（执行）；项目 Owner（用户，要求不依赖实体手机继续全仓完善）
- 创建/更新：`2026-07-17`

## 目标与边界

以当前可运行代码和测试为事实，对照 P1 PRD 收口不依赖实体设备的生产链路。优先修复会让客户端展示成功但业务事实未落库、让客户端提交可伪造事实、或在进程退出后丢失队列的缺口；随后补齐可自动运行的部署、恢复和核心 E2E 门槛。实体 iPad/iPhone/Nova 9 只保留最后的权限、横竖屏、弱网和真实拍题人工验收，不阻塞代码与 synthetic 自动验收。

## 阶段

- [x] 1. 全仓盘点 PRD、契约、迁移、客户端入口、部署和测试，区分已实现、只有骨架和未实现。
- [x] 2. 收紧 VerifiedQuestion → Tutor 信任边界：Tutor 只按服务端 ID 读取人工确认事实，并持久化可追溯 TutorTurn/提示级别和幂等结果。
- [x] 3. Flutter 将真实拍题确认结果接入 Tutor；移除生产路径硬编码题目/提示，补齐加载、失败、重试和无网络状态。
- [x] 4. 将端侧待同步 Attempt 队列改为 SQLite 持久化，实现进程重启恢复、有界批次、幂等确认和失败保留。
- [x] 5. 补齐任务完成、错题/复习、家长周报和家庭导出/删除的最小可追溯服务端/家长端闭环；不接入未批准内容或通知 Provider。
- [x] 6. 增加云视觉固定 synthetic eval、真实 NewAPI 合成大图验收、PostgreSQL/MinIO 备份恢复脚本和无密钥日志检查。
- [x] 7. 运行 API/Web/Flutter/契约/迁移/Compose 质量门槛，部署 Ubuntu并执行不读取真实题目内容的 synthetic smoke；同步 TASK/TESTING/RUNBOOK/CHANGELOG/AI_CONTEXT。

## 完成记录

- OpenAPI 前滚至 `0.8.0`，数据库前滚至 `0015_child_data_export`；新增追加写 `TutorTurn`、学习会话完成/复习状态、周报聚合、24 小时家庭数据导出快照和端到端级联删除。
- Flutter 生产首页改为读取真实任务/活动会话，拍题确认后只按 VerifiedQuestion ID 请求 Tutor；待同步 Attempt 使用按服务端/账号隔离的 SQLite 队列，同日新拍题不再错误复用已完成会话。
- 离线存储锁定 `sqflite 2.4.3`/`sqflite_common_ffi 2.4.2`（BSD-3-Clause、持续维护的 Flutter SQLite 插件）：只存结构化待同步事件，无服务端成本；相较 Drift 避免额外代码生成，相较键值库保留事务/查询语义。供应链与体积影响是新增 SQLite 原生插件和 iOS CocoaPods 集成，已由锁文件、两端 release 构建和重启恢复测试约束。
- Ubuntu Compose 已重建 API/Web/ImageAnalysis/DataLifecycle worker；健康版本 `0.8.0`，真实 NewAPI 仅用内存 synthetic 大图完成压缩、单 Provider、Extraction、人工确认、TutorTurn 和派生对象删除链路。
- 已生成 PostgreSQL custom dump 与 MinIO 快照并在隔离 PostgreSQL 16.10 容器恢复校验；自动生命周期 worker 已部署。实体设备相机、权限、横竖屏、弱网和重启仍按计划边界留作设备可用时人工验收。

## 不变量与回滚

- 客户端不能把自带的 VerifiedQuestion 当作 Tutor 事实；服务端必须按 Household、绑定孩子和持久化 ID 读取。
- Attempt、TutorTurn、错题依据和审计保持追加写；重试不得覆盖历史或制造重复副作用。
- 离线队列只保存必要结构化摘要，不保存图片、密码、会话或 Provider 原始响应；更换服务端/退出账号时按账号作用域隔离。
- 所有 AI/视觉自动验收只使用仓库生成的 synthetic 输入；真实儿童图片、题目原文、对象键和凭据不得进入输出或测试产物。
- 数据库变更只做向前兼容迁移；回滚应用时保留新增表和历史记录，优先前向修复，不以删库/清卷回滚。

---

# PLANS.md — PLAN-0007 自用账号密码与孩子账号管理

## 计划元数据

- 计划 ID：`PLAN-0007`
- 关联任务：`TODO-012` / `ADR-0017`；进入执行时建立 `TASK-0007`
- 状态：`IN_PROGRESS`
- 优先级：`P0（下一优先级）`
- Owner：Codex（执行）；项目 Owner（用户，方案批准）
- 创建/更新：`2026-07-16`

## 目标与边界

用 PostgreSQL 本地账号密码和可撤销不透明会话替换当前自用 HMAC 家庭 Token。家长 Web 提供登录、首次强制改密和孩子账号管理；Flutter 孩子端使用孩子账号登录并把会话保存在系统安全存储。保持单 Household 自用，不接入短信、邮箱、社交登录、OIDC 或 MFA。

本计划涉及 `services/api`、`packages/contracts`、`apps/web`、`apps/child_flutter`、数据库迁移和 `infra/compose`，必须分里程碑验收。`TASK-0006` 的代码闭环已完成，本计划按用户授权自动进入 `IN_PROGRESS`。

## 产品与安全不变量

- `admin/admin123456` 只在账号表为空时创建，是公开的一次性引导凭据，不是长期默认密码。
- 默认凭据有效时只允许本机引导；登录后只能改密/退出，所有家庭数据和管理 API 均返回 `password_change_required`。
- 密码只存 Argon2id 哈希；原始会话只交付客户端一次，服务端只存摘要。密码、哈希、会话、Cookie 不进入日志、错误、审计正文、测试夹具或客户端构建产物。
- Household 和角色授权仍在每个资源上服务端执行；孩子账号只能绑定同 Household 的一个 ChildProfile，跨 Household 继续统一 404。
- Web 使用 HttpOnly Cookie + CSRF；Flutter 使用 Keychain/Android Keystore。不得继续用 `STUDY_API_TOKEN` 或 `--dart-define` 注入长期凭据。
- 禁用账号、改密、管理员重置和退出必须撤销相应会话；恢复命令只能从服务器本机执行并审计。

## 实施阶段

- [x] 1. 契约与依赖评审：OpenAPI 已增加认证与账号管理合同；锁定 `argon2-cffi==25.1.0` 和 Flutter `flutter_secure_storage==9.2.4`，用途、替代和供应链影响已记录。
- [x] 2. 数据库与领域：新增 `0011_account_password_session`（因 `0010` 已用于 VerifiedQuestion），建立 Account/AuthSession、唯一约束、索引、并发空表初始化和兼容迁移边界。
- [x] 3. API 认证核心：已实现 Argon2id、统一登录错误、5 次失败/15 分钟锁定、256 bit 不透明会话摘要、30 天到期、退出/撤销、改密/禁用/重置联动、孩子账号管理的当前密码再验证和 Household/角色/ChildProfile 反向授权；认证生命周期已写入现有 `audit_events`，只保存稳定事件名与资源 UUID。
- [x] 4. 安全初始化：空账号库事务创建 `admin/admin123456`，设置 `must_change_password`；回环限制、改密前数据阻断和改密后会话轮换已实现并测试。
- [x] 5. 家长 Web：已增加 `/login`、首次改密、退出、账号列表、孩子账号创建/启停/重置；使用 HttpOnly/SameSite Cookie、CSRF 和服务端路由保护，孩子账号管理操作要求当前家长密码再验证。
- [x] 6. 孩子 Flutter：已增加用户名/密码登录，并使用 `flutter_secure_storage` 保存会话；Capture API 使用会话 Bearer。真实 iPad 生命周期/重启验证待执行。
- [x] 7. Compose 与迁移切换：Compose 已启用 password/postgres 认证和 Cookie 配置；随 TASK-0007 删除 auth mode、HMAC/Demo 兼容、静态 Web token 和 Web auth-required 开关。
- [ ] 8. 完整质量门槛：API/Web/Flutter 本地质量门槛、OpenAPI/Schema 解析和 18 项 PostgreSQL/MinIO 集成已通过；迁移 downgrade/upgrade 往返、浏览器 E2E、真实设备登录/退出、备份恢复和正式敏感信息扫描仍待执行。

## 验收标准

- [ ] 全新 Compose 在账号表为空时只创建一个 `admin`；使用临时密码登录后，在改密前无法读取任何 Household/孩子/学习/图片数据。
- [ ] 改密后临时密码和所有引导会话失效；数据库、日志和浏览器/客户端产物中没有明文密码或原始会话。
- [ ] 家长可以创建、查看状态、禁用/启用和重置同家庭孩子账号；不能查看既有密码，不能绑定其他家庭 ChildProfile。
- [ ] 孩子可以登录自己的 Flutter 学习桌，只能访问绑定孩子；兄弟孩子、家长 API、跨家庭和枚举 ID 均被拒绝。
- [ ] Web Cookie、CSRF、会话到期/撤销、失败锁定、退出、改密、账号禁用和管理员恢复均有正反向测试。
- [x] Compose 已移除 `STUDY_API_TOKEN`/长期 token 配置，Flutter 已移除长期 token 构建注入；TASK-0007 已删除 HMAC 签发脚本、Demo Header 和所有兼容开关。

## 发布与回滚

发布切换已完成：扩展数据库/合同、切换 Web/Flutter、再删除旧 HMAC/Demo。出现登录或授权问题时优先前向修复；回滚到含旧认证路径的版本需项目 Owner 单独批准并限于隔离环境。账号/会话表和审计保持不删，不得清空家庭数据或重写学习记录。

## 剩余风险

- 公开默认密码存在抢先登录风险，必须依赖回环引导和改密前数据阻断；如果未来要求开箱即用的局域网首次登录，应改为随机一次性密码/安装码并另行批准。
- 无邮箱/短信/MFA 时，超级管理员忘记密码只能使用本机恢复命令；服务器主机权限等同于超级管理员权限。
- 单家庭方案不解决公网多租户注册、账号恢复和身份合规；范围扩展必须新建 ADR。

## 2026-07-16 执行记录

- `[done]` TASK-0006 已完成代码闭环，PLAN-0007 自动启动。
- `[done]` API/Web/Flutter/Compose 认证主链路已实现；新增账号绑定反向校验和家长重置密码入口。
- `[done]` 认证生命周期审计已接入内存与 PostgreSQL 账号仓储：成功/失败/锁定/阻断登录、改密失败/成功、再认证失败、登出、孩子账号创建、启停和重置均只写稳定事件名、Household/资源 UUID 和时间；认证回归、Ruff、Mypy 通过。
- `[done]` TASK-0007 已完成唯一密码认证和 Flutter 登录前服务端地址配置；API 122 项非集成/18 项 PostgreSQL-MinIO 集成、OpenAPI/Schema、Web 与 Flutter 本地质量门槛通过。
- `[pending]` 仍需在 Compose、浏览器和 iPad 上完成迁移往返、Cookie/CSRF、真实登录退出与设备重启验收；未执行项不能报告为通过。

---

# PLANS.md — PLAN-0020 全局超级管理员与家长自有孩子

## 计划元数据

- 状态：`COMPLETE（Ubuntu 已备份、前滚 0028 并完成运行态验证）`
- 关联：`TASK-0010`、`ADR-0024`、`0028_super_admin_ownership`
- 创建/更新：`2026-07-28`

## 目标与验收

- [x] 将每家庭 `parent_admin` 收敛为唯一实例级 `super_admin`；新家庭仅创建普通 `parent`。
- [x] 为孩子档案增加所有者账号，家长只能列出、创建、编辑、删除及管理自己名下孩子和账号；教材、推荐入口复核该归属。
- [x] 保持登录名全局唯一及公开教材的私有指纹复用；不共享儿童资料、学习事实或审核决定。
- [x] 补充服务器控制台专用超级管理员密码恢复入口，不输出或传递明文密码。
- [x] 完成 API 定向单元测试、Ruff、Mypy、OpenAPI head、Web 定向测试/类型/格式检查。
- [x] 在 Ubuntu 备份后前滚 `0028`，验证唯一角色与历史孩子所有者回填；普通家长越权与真实 Web 流程仍作为后续浏览器验收，不影响本次部署健康结论。

---

# PLAN-0021 Web 拍题聚焦与家庭权限管理

## 目标

- [x] 从家长首页、教材页和孩子管理页移除手工任务、任务推荐和手工小节导入 UI，保留教材上传、知识图谱、错题与逐题记录。
- [x] 将跨家庭的“家庭权限”迁移至独立左侧导航页面，仅在 `super_admin` 已认证时显示；普通家长只能看到自己的孩子管理入口。
- [x] 超级管理员可开通“新家庭 + 首个普通家长”，查看各家庭的首个家长，并在该家长尚未拥有孩子时删除其账号；禁止删除超级管理员、普通家长越权及遗留无主孩子。
- [x] 更新 OpenAPI、鉴权回归、Web 页面测试和交付文档；不删除既有任务/推荐数据或后端学习闭环，仅停止 Web 家长端操作入口。

## 验收与回滚

- 普通家长的导航和直接访问均不显示或不可访问家庭权限数据；API 仍以 `super_admin` 再次授权。
- 家长删除成功后会撤销该账号会话；存在其拥有孩子的家长删除必须返回稳定冲突，不修改任何数据。
- 回滚优先通过前向修复恢复隐藏入口；本计划不执行任务、推荐、教材或学习事实的批量删除。

## 本地交付记录（2026-07-28）

- 已实现独立 `/family` 页面、同名 Web BFF 和 API 合同。仅超级管理员可读取家长列表、开通新家庭及其首个普通家长；直接访问与 API 均会再次做角色校验。
- 删除普通家长要求超级管理员重新输入当前密码；仅在该家长没有任何所属孩子时执行，删除后撤销其会话。存在孩子时返回稳定冲突，不会改变账号或孩子数据。
- 验证：API 鉴权相关 `34 passed`、Ruff、Mypy；Web `27` 项测试、Lint、TypeScript、Prettier 和生产构建通过。本机 Node `20.17`/pnpm `9.10` 低于锁定版本，仅作为本地验证并产生 engines warning。2026-07-28 已同步 Ubuntu 并以锁定 Node `24.18`/pnpm `11.7` 重建；API/Web 与四个 worker 健康，Alembic current/head 均为 `0028_super_admin_ownership`，未登录访问家长权限 API 返回 `401`。普通家长与超级管理员的浏览器人工流程仍待验收。

## 回滚

迁移后的角色与孩子所有者属于权限事实；部署失败优先前向修复。不得通过删除账户、孩子、教材或学习记录回滚。数据库备份只在项目 Owner 明确授权时用于隔离恢复。

---

# PLANS.md — PLAN-0008 Ubuntu x86_64 与自托管 NewAPI 环境验收

## 计划元数据

- 计划 ID：`PLAN-0008`
- 关联任务：`TASK-0006`、`PLAN-0007`、`TODO-008`、`TODO-012`、`ADR-0015`、`ADR-0016`、`ADR-0017`
- 状态：`IN_PROGRESS`
- Owner：Codex（执行）；项目 Owner（用户，Ubuntu/NewAPI 已提供）
- 创建/更新：`2026-07-16`

## 范围与安全边界

在用户提供的 Ubuntu VM `192.168.1.4:22`、账号 `syin`、`x86_64` 环境验证自托管 Compose、锁定模型构建和 NewAPI OpenAI-compatible Adapter。只使用 synthetic 图片和 synthetic 题目；真实儿童图片、真实学习记录和原始 Provider 响应不得上传、写入日志或进入仓库。NewAPI 只接受用户确认且哈希绑定的脱敏副本，失败不得切换 Provider。

`2026-07-16` 项目 Owner 进一步明确：运行时只保留“用户名+密码→可撤销会话”一种认证方式，删除 HMAC、Demo Header 和 Web 免登录开关；Flutter 必须在提交登录前允许验证、保存和更换服务端地址，地址变更时不得复用旧服务端会话。该收敛作为继续环境验收的前置增量，不扩大到短信、邮箱、MFA 或设备绑定。

## 阶段

- [x] 1. SSH、架构、Python 3.12、磁盘和 Docker 前置检查。
- [x] 2. 安装 Ubuntu 官方 Docker Engine/Compose v2，启用 daemon，并加入 `syin` 的 docker 用户组。
- [x] 3. 传输脱敏工作区、生成远程 `.env`、运行 Compose config 和 Alembic `0011` 前滚迁移。
- [x] 4. 构建 Linux x86_64 API/Web 镜像，确认五份模型构建期 SHA-256 校验和运行时不自动下载；容器预检已增加显式锁定 Debian 13 运行层选项，其他版本/架构/模型门禁仍保持严格。
- [ ] 5. 启动 PostgreSQL/Redis/MinIO/API/Web/worker，验证健康、账号首次改密、Cookie/CSRF 和孩子账号授权（Compose 健康、迁移和 LAN bootstrap login 已通过；Nova 9 已恢复真实孩子会话并进入首次改密页，提交新密码后的档案读取、Cookie/CSRF 和完整设备生命周期待验收）。
- [x] 5a. 在再次部署前收敛认证面：已删除 API HMAC/Demo 路径、旧签发脚本与相关配置，OpenAPI 和 Web/Flutter 只使用密码登录后的 Cookie/Bearer Session；Flutter 登录页已提供持久化服务端地址配置，并覆盖地址验证与跨服务端会话清理测试。
- [ ] 6. 使用 synthetic 脱敏图片配置 NewAPI 视觉模型，执行单 Provider `queued → extraction → VerifiedQuestion` 联调；不发送真实数据。`queued → extraction` 已通过；远端以家长/孩子会话调用人工确认生成 `VerifiedQuestion` 仍待验收。
- [x] 7. 做停止/重启、迁移、worker 失败清理和日志敏感信息审查；新增稳定 Provider 错误码和可清理 live eval，并同步任务/测试/安全/运行文档。

## 当前进度（2026-07-17）

- Ubuntu 宿主确认 `Ubuntu 24.04 LTS`、`x86_64`、Python `3.12.3`；Docker `29.1.3`、Compose `2.40.3` 已安装。按项目 Owner 要求关闭该 VM IPv6，并为 Docker daemon 配置 `socks5://192.168.1.100:7893` 出网代理。
- `/home/syin/study` 只接收排除 `.git`、依赖缓存、构建产物、`.env` 和图片的工作区；远端 `.env` 权限为 `600`，数据库/MinIO 密码由远端随机生成，NewAPI URL、Key 和 `gemini-3.1-flash-lite` 已配置并启用；Key 未写入仓库或输出。
- Compose 已在远端启动并重启恢复：PostgreSQL、Redis、MinIO、API、Web、迁移和 worker 均正常；API/Web `/healthz`、`0011` 迁移、loopback bootstrap login、模型预置目录、无网络运行时模型路径和内存 synthetic OCR smoke 已验证。Cloudflare 曾以 1010 拦截 Python `urllib` 默认 User-Agent；Adapter 改用受控的 `study-api/0.5` 后，synthetic NewAPI live eval 已成功完成 `queued → extraction`，返回 `needs_confirmation=true`，派生副本已删除且数据库残留 Job 为 0。未发送真实图片或输出原始 Provider 响应。
- 本次发现并修复 API Docker 构建上下文的 Python 缓存与 macOS AppleDouble 元数据排除，避免 Alembic 将 `*.pyc`/`._*.py` 当迁移脚本扫描。
- 已修复 OCR 预检无法识别自身锁定 Debian 13 镜像层的问题：宿主仍要求 Ubuntu 24.04，只有镜像声明的 `STUDY_OCR_CONTAINER_RUNTIME=true` 才允许 Debian 13；远端重建后预检 `ready`，完整 4-case synthetic OCR eval 通过。
- TASK-0007 认证收敛已在本地完成：OpenAPI `0.6.0`、API/Web/Flutter/Compose 只保留密码登录后的 Cookie/Bearer Session，Flutter 可在登录前配置服务端地址。API 122 项非集成/18 项 PostgreSQL-MinIO 集成、Web 完整质量命令和 Flutter 17 项测试通过；远端栈尚未用该增量重新部署。
- 2026-07-17：为华为 Nova 9 Android 调试复核 Flutter 3.44.6、Android SDK 36.1.0/JDK 21 和全部许可证，Flutter analyze/17 项测试及 176 MB Debug APK 构建通过。Nova 9（Android 12）现已由 ADB 识别，Debug APK 已通过 Flutter tooling 安装并在前台运行；设备至 Ubuntu API `192.168.1.4` 的局域网 ICMP 连通约 32 ms。待继续执行登录、相机/相册、脱敏预览、弱网和会话生命周期的人工交互验收。
- 2026-07-17：项目 Owner 授权移除引导家长账号的 loopback 登录限制，仅保留受信 LAN 首次改密用途、改密前数据阻断和既有锁定/会话/授权保护。Ubuntu 远端副本最初只有部分 API 文件更新，造成领域模型版本不一致并使新 API 容器重启；完整同步 `services/api` 运行目录和构建清单后重建成功，API healthy，`/healthz` 返回 `0.6.0`，容器内 LAN 引导登录回归通过。未调用远端真实账号或数据库做首次改密。
- 2026-07-17：定位 Nova 9 登录后“API 尚未连接”为孩子账号 `must_change_password` 被 API 正确阻断、Flutter 却丢弃该标志。Flutter 新增登录响应/`/auth/me` 恢复、首次改密 UI、会话轮换和安全存储；API 档案列表/详情只允许孩子读取绑定档案。API 129 项非集成/22 项集成、Flutter analyze/21 项测试和 Debug APK 通过；Ubuntu API 重建健康，实机完成改密与档案读取并显示在线学习桌，竖屏溢出修复后再次覆盖安装和截图验证。
- 2026-07-17：家长 Web 创建孩子账号时，中文用户名被拼入 `Idempotency-Key` Header，浏览器因 Header 非 ISO-8859-1 而在请求前阻断。Web 改为 ASCII 随机幂等键，并让账户页自动加载/绑定首个家庭孩子档案，多个档案可选择，不再要求家长手输 UUID。4 项 Web 单测、格式、Lint、类型和生产构建均通过；完整 Web 运行目录已同步并部署到 Ubuntu，Web/API 健康检查通过。
- 2026-07-17：补齐家长 Web 孩子档案新增、编辑和删除入口；新增/编辑代理此前遗漏 JSON `Content-Type`，导致 FastAPI 在解析请求体前返回 422，现已显式转发 `application/json` 并增加 POST/PATCH 回归测试。Web 镜像已重新部署到 Ubuntu，Web/API 容器与健康端点均正常；远端无会话 POST/PATCH smoke 均返回预期 401 而非 422，未写入数据。当前 Profile 仓储仍为进程内 synthetic 实现，API 重启后档案改动不会保留，持久化到 PostgreSQL 仍是后续工作。

## 回滚

只删除本次在 `/home/syin/study` 创建的部署目录和 Compose 项目（需用户明确授权后执行）；不删除 Docker Engine、系统包、其他容器或远程用户数据。NewAPI 异常时保持 `STUDY_NEWAPI_ENABLED=false` 并停止 worker，数据库迁移优先前向修复；Cloudflare 1010 的应用侧兼容修复只设置受限 User-Agent，不修改或绕过网关安全策略。

---

# PLANS.md — PLAN-0009 孩子档案 PostgreSQL 持久化

## 计划元数据

- 计划 ID：`PLAN-0009`
- 关联任务：`TASK-0008`、`PLAN-0008`、`ADR-0005`、`ADR-0009`、`ADR-0017`
- 状态：`COMPLETE（华为登录生命周期继续由 PLAN-0008 验收）`
- Owner：Codex（执行）；项目 Owner（用户，要求按生产标准持久化）
- 创建/更新：`2026-07-17`

## 范围

用 PostgreSQL 替换当前进程内 Profile/Device 事实源；公开 API 保持兼容。迁移必须保护 Household 边界、孩子账号反向绑定、幂等、审计与删除顺序，并在 Ubuntu Compose 上验证 API 重启后数据仍存在。内存实现仅保留给不依赖数据库的单元测试。

## 阶段

- [x] 1. 核对当前 Profile/Device 内存仓储、认证绑定、通用幂等表、Compose 开关和迁移链。
- [x] 2. 新增 `0012_profile_persistence`，建立孩子档案/设备表、索引、约束和旧账号绑定兼容数据。
- [x] 3. 实现 PostgreSQL ProfileRepository，并将 Learning/认证/路由依赖改为仓储协议。
- [x] 4. 覆盖创建、编辑、删除、重启重连、跨家庭、幂等冲突、账号级联和迁移往返测试。
- [x] 5. 更新 Compose 与文档，运行 API/Web/Flutter/契约门槛。
- [x] 6. 部署 Ubuntu，迁移前备份并前滚 `0012`，验证 API 重启持久化和 synthetic 清理；回滚保留数据表。华为已由 ADB 重新识别并冷启动到登录页，真实凭据登录/档案读取返回 `PLAN-0008`。

---

# PLANS.md — PLAN-0010 真机拍题视觉识别闭环

## 计划元数据

- 计划 ID：`PLAN-0010`
- 关联任务：`TASK-0009`、`PLAN-0008`、`ADR-0003`、`ADR-0015`、`ADR-0016`
- 状态：`IN_PROGRESS（代码、部署和 APK 安装完成；真实拍题状态验收待用户操作）`
- Owner：Codex（执行）；项目 Owner（用户，要求继续完善拍题识别）
- 创建/更新：`2026-07-17`

## 范围与发现

Nova 9 的相机/相册与本地脱敏预览已经可用，但 APK 只有在编译时注入 `STUDY_CAPTURE_SESSION_ID` 才会构建 Capture 客户端。远端 PostgreSQL 的任务、学习会话、Capture 和 ImageAnalysis Job 均为 0，证明此前没有发生上传。另一个真机阻塞是预签名 URL 使用 Compose 内部主机名 `minio:9000`，手机不可解析。

## 阶段

- [x] 1. 新增 `POST /households/{household_id}/capture-sessions`，由已认证孩子身份原子创建即时数学任务与活跃会话；客户端不能提交 child ID。
- [x] 2. 在内存/PostgreSQL 仓储实现同一幂等语义，并覆盖家长拒绝、跨 Household 不可枚举、重连与任务/会话唯一结果。
- [x] 3. Flutter 删除编译期会话开关，按孩子/日期创建或复用会话；上传后轮询 ImageAnalysis，并读取 QuestionExtraction。
- [x] 4. 识别结果进入可编辑人工确认；成功写入 VerifiedQuestion，失败/阻塞/超时提供可操作信息和手工填写兜底。
- [x] 5. 历史实现：对象存储增加独立公开签名端点，服务端内部读写仍走 `minio:9000`；Ubuntu 使用 LAN `9000`，Bucket 和密钥边界不变。该目标已于 2026-07-17 被 ADR-0018/PLAN-0012 替代，不再作为最终发布架构。
- [x] 6. 完成本机 API/Flutter/契约检查，部署 API/worker，覆盖安装 Nova 9 APK 并验证登录恢复。
- [ ] 7. 由用户在真机执行一次拍题，只核对生命周期状态和资源清理，不读取或输出真实题目内容。

## 回滚

本段是预签名直传的历史回滚记录。ADR-0018 迁移后的回滚必须使用匹配的 API/App 镜像，并只在隔离受信 LAN 临时恢复旧 `9000`/配置；不删除已创建任务、会话、Capture、Extraction 或 VerifiedQuestion。失败任务继续由既有保留/清理策略处理。
