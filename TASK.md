# TASK.md — TASK-0012 多学科基础与语文首个纵向切片

## 当前任务元数据

- 状态：`IN_PROGRESS（数学/语文本地可用闭环与 PostgreSQL 集成已补齐；正式内容、真实 Provider 和设备验收继续）`
- 类型：`FEATURE / AUTH / BROWSER E2E / CHILD UI`
- 优先级：`P0`
- Owner：Codex（执行）；项目 Owner（2026-08-15 明确要求先多学科、再语文、英语最后）
- 关联：`PLAN-0034`、`PLAN-0031`、`PLAN-0030`、`PLAN-0007`、`ADR-0017`、`ADR-0027`、`ADR-0028`、`docs/deep-research-report.md`

## 2026-09-03 家长后台视觉改版与学习记录布局修复

- [x] 统一重做家长后台的基础视觉层：侧栏改为深石墨导航与绿色选中标识，品牌区、导航分组、顶部当前孩子/账号区和主内容区建立更清楚的层级；保留原路由、角色导航和孩子作用域行为。
- [x] 学习记录页改为紧凑的“页面标题 → 时间筛选 → 记录汇总 → 明细/空状态”结构；“时间范围”获得明确内边距、行高和左侧标识，不再被面板 `overflow` 裁切。日期字段在窄屏换行，空状态不再撑满大块空白。
- [x] 登录态 Chromium 增加桌面 `1280×800` 标签边界断言和手机 `390×844` 无横向溢出断言；完整 Cookie/CSRF、多家庭、双孩子与切换流程 `1 passed`。Web `37 passed`，Prettier、ESLint、TypeScript 和 Next production build 通过。
- [x] 使用隔离内存 API 和 synthetic 账号完成 `1280×720` 桌面浏览器视觉复核；预览图只保存在本机临时目录，不包含真实账号、儿童数据或学习记录。

- [x] 代码提交 `be3bd70` 已推送 `origin/master`；Ubuntu 白名单同步 8 个文件并使用锁定 Node `24.18.0`/pnpm `11.7.0` 的 legacy builder 成功构建，只以 `--no-deps --force-recreate` 替换 Web。Web/API 本机和 LAN health、运行 CSS 标识、远端源码 SHA-256 及其他服务容器 ID 通过。

未执行：未使用 Ubuntu 真实账号做浏览器登录，也未进行设备回归；本轮没有数据库、API、迁移或对象存储变更，因此未停止 writer 或创建数据备份。远端旧源文件保存在 `/home/syin/study-source-backups/20260903T022940Z`，可恢复后重建 Web。当前本机 Node `22.23.0` 低于仓库锁定的 `>=24.18.0 <25`，本地命令有 engine warning；远端正式构建已使用锁定 Node 24。

## 2026-08-30 家长首页简化与历史记录清理

- [x] 首页移除“语文技能报告”卡片及对应 `skill-report` 请求；保留后端接口，避免影响既有导出和其他家长工具。
- [x] “今日需要关注”改为只显示上海自然日当天到期的开放错题；昨天以前已到期的项目不再出现在首页，未来项目也不进入今日关注。
- [x] Web 日期边界回归、全量 Vitest `37 passed`、Prettier、ESLint、TypeScript 和 Next production build 通过；本机 Node `20.17.0` 低于项目锁定的 `>=24.18.0 <25`，命令产生 engine warning，未改变测试结果。
- [x] Ubuntu 已完成受控 Web 部署：备份 `/home/syin/study-backups/20260830T004506Z` 隔离恢复为 39 张 PostgreSQL public 表/528 个 MinIO 文件；Web legacy builder 构建、容器重建、API/Web health 和 3 个运行源码哈希通过。
- [x] 用户确认清理两个孩子后，使用已验证备份 `/home/syin/study-backups/20260830T004506Z`（39 张 PostgreSQL public 表、528 个 MinIO 文件）执行有界运维清理。删除 4 条 Attempt、18 个 StudySession、21 个 StudyTask、23 个 Capture/私有拍题对象、5 条 ChineseAttempt、5 条 ChineseReviewItem、1 条 MistakeRecord、1 条 ReviewSchedule、10 条 TaskRecommendation、35 条 TutorTurn、15 条 VerifiedQuestion、18 条 QuestionExtraction、22 条 ImageAnalysisJob、2 条 PictureWritingGuide，以及关联的 OCR/导出/幂等记录；全部目标历史表复核为 0。保留 2 个 ChildProfile、3 个 Account、3 份 LearningMaterial、3 个 CurriculumSnapshot、184 条 ChineseContentItem 和 149 条 AuditEvent；API/Web/全部 worker 恢复健康。孤立且无法关联目标 Capture 行的对象未做递归删除。

回滚：首页可恢复语文技能报告展示和原 `due_only` 计数；不通过代码回滚恢复已删除数据，数据清理必须使用经验证备份。

## 2026-08-29 Nova 9 古诗抽查错误内容修复

- [x] 截图和 Ubuntu 数据确认：《剪窗花》被 Provider 作为宽泛 `poem` 候选，教材批准路径自动把所有该类候选编译为相邻句题；当前 38 条候选中混有大量儿歌/韵文，错误不在 Flutter 随机算法。
- [x] 只读核对当前六首明确古诗及其页级连续诗句证据；《剪窗花》已有 7 道 approved 派生题，当前没有 Attempt/Review 引用，但修复仍按保留所有历史事实设计。
- [x] 完成确定性古诗签名门禁、旧派生题退役/重建、Provider 提示收窄及回归测试；孩子读取和提交入口还会再次校验题干/答案连续签名，旧错误题即使未迁移也失败关闭。
- [x] 完成本地质量门槛及 Ubuntu 两次备份/隔离恢复、`0037`/`0038` 迁移、`0.17.1` 部署和真实题库核验；157 道错误题退役，只保留咏鹅、画、悯农（其二）、江南、古朗月行、风共 21 道，42 个童谣干扰项替换为古诗句，Attempt/Review 全程均保持 1。
- [x] Nova 9 首次重连后从驻留页面打开“日积月累 / 种瓜得瓜”，客户端因此改为每次点击古诗入口都重新读取 API；随后又发现保留题含童谣干扰项，服务端 v2 门禁和 `0038` 要求所有选项也属于古诗目录。修复版 APK 覆盖安装并保留登录态，迁移后连续 12 轮抽查覆盖全部六首，题干/下一句连续且所有选项都是古诗句；未选择答案，Attempt/Review 未增加。
- [x] 已提交 `ee5e226`、`13dc800`、`e44a2b1`，创建并推送指向 `e44a2b1` 的 annotated tag `v0.17.1`。远端 `master`/tag refs 已核验；GitHub `quality` run `33278258569` 与 Android run `33278259768` 均为 `success`，公开 Release 含 3 个 ABI APK、`SHA256SUMS` 和 `BUILD-INFO.txt`。

回滚：不 downgrade `0037`/`0038` 或重新批准错误题/童谣选项；保留 Attempt、Review、教材和审核事实，以匹配应用前向修复。设备验收未提交答案。

## 2026-08-25 语文教材分析 Schema 与批次兼容修复

- [x] 根据 CurriculumAnalysis worker 的安全字段路径日志定位：语文 v2 页级提示没有明确列出 `knowledge_observations` 的完整字段，当前 Provider 连续返回 `observation` 或 `type`/`description` 等替代结构并漏掉标题、摘要和置信度，导致整批严格校验失败。
- [x] 页级提示升级为 `chinese-curriculum-page-visual.v3`，逐项固定观察/练习字段、枚举、数组和 `0`～`1` 置信度，并禁止额外页码及替代字段名。
- [x] 语文页级观察属于可为空的中间证据；服务端现在只丢弃无法通过既有 `ProviderKnowledgeObservation` 严格校验的观察，不从页面字段补造标题、目标或置信度。页面摘要、可审核篇章/古诗边界及最终知识图谱严格校验和家长批准门禁保持不变；数学路径不放宽。
- [x] 合成回归覆盖日志中的两类漂移对象，确认保留古诗行、丢弃计数可观测且日志不包含教材内容。真实重试进一步暴露四页请求的 `provider_http_413`；worker 现在只在同一 Provider 上递归二分当前批次，单页仍为 413 时保持失败可见，不跨 Provider 回退，也不记录页内容。
- [x] 真实页级分析完成后，整书 Provider 连续返回 `chapter_title`、`pages`、`page_references`、`knowledge_observations` 等替代字段。整书提示升级为 `chinese-curriculum-book-consolidation.v3`，明确顶层、章节和知识点的精确字段、数量上限、页码/练习引用约束，并禁止这些替代字段；服务端固定 `chinese-curriculum-book-analysis.v2` Schema 和家长审核门禁未放宽。
- [x] Provider/教材作业定向 `30 passed`、API 非集成全量 `254 passed`、Ruff 和 Mypy（62 source files）通过。
- [x] 已定向部署 Ubuntu API 与 CurriculumAnalysis worker。发布前备份 `/home/syin/study-backups/20260825T141449Z` 隔离恢复验证为 39 张 PostgreSQL public 表和 363 个 MinIO 文件；首次验证临时 PostgreSQL 容器发生启动竞态，复跑通过后才继续发布。远端旧源码另存于 `/home/syin/study-source-backups/20260825T142000Z`。
- [x] Docker BuildKit 因 Docker Hub IPv6 token 请求超时失败且未替换运行容器，随后使用已验证的 legacy builder 和本地缓存构建；API/CurriculumAnalysis worker 重新创建后，API/Web LAN health、`0036` current/head、`newapi` 路由、MinIO 私有端口、容器源码哈希、Prompt v3 和 synthetic 丢弃逻辑均通过。
- [x] 在不读取或记录 Provider 原始响应、教材正文和儿童数据的前提下，运维显式重排既有失败作业；第 4 次尝试完成 `118/118` 页并进入 `needs_review`，生成 10 个章节、12 个全部为 draft 的知识点和 38 条古诗边界证据，错误字段为空。
- [x] 2026-08-26 最终部署后只读复核显示审核事实已由外部操作更新为知识图谱 `approved`、12 个知识点全部 `approved`；系统没有在解析或部署中自动批准。118 页、10 个章节和 38 条古诗边界证据保持不变。
- [ ] 本次真实解析和批准状态不代表 token/费用、正式版权/教研签核、浏览器账号或设备验收通过；这些仍需独立证据。

回滚：停止 CurriculumAnalysis worker，恢复 `chinese-curriculum-page-visual.v2`、`chinese-curriculum-book-consolidation.v2` 和旧批次调用；保留现有教材对象及已批准审核事实，不删除、降级或重新自动运行知识图谱。

## 2026-08-24 本地 Qwen 模型路由与 Ubuntu 部署记录

- [x] Compose 增加可切换的 llama.cpp `local-model` 服务，默认加载 Qwen3.5-4B Q4_K_M GGUF 及视觉 projector；本地服务不发布宿主/LAN 推理端口并持久化模型缓存。
- [x] `STUDY_LOCAL_MODEL_ENABLED=true` 时 API、ImageAnalysis worker、CurriculumAnalysis worker 统一选择 `local_qwen` 配置并忽略云端 NewAPI；关闭时保持现有 NewAPI 路径，不自动跨 Provider 回退。
- [x] Provider/model 记录、环境样例、ADR-0028、Compose/运维/安全说明和本地/云端路由单元测试已补齐；Provider 定向测试 `24 passed`，非集成 API `249 passed, 32 deselected`，Ruff/Mypy 和远端 Compose 展开通过。
- [x] 本机 Linux ARM64 已实际拉取 llama.cpp 镜像和 Q4_K_M 权重/vision projector；`local-model` health、`/v1/models`、synthetic text 和 vision/schema 请求通过，且 Qwen 结构化请求关闭 reasoning。
- [x] 12 GB/4 核 Ubuntu 已启用本地模型；发布前备份 `/home/syin/study-backups/20260824T024445Z` 已隔离恢复为 39 张 PostgreSQL public 表和 353 个 MinIO 文件。模型/API/Web/四个 worker 健康，路由为 `local_qwen`，文本 JSON smoke 通过，模型/MinIO 均无宿主端口。模型初始空闲约 3.8 GiB，长视觉评测后保留 prompt cache 时约 6.4 GiB，宿主仍有约 6.5 GiB available。
- [x] 目标硬件暴露的失败已设为有界：本地专用超时 600 秒、最多 2048 输出 token、超时/网络错误不自动重复推理，且永不自动切换云端。
- [ ] Ubuntu `question-extraction.v1` synthetic 大图在 600 秒内生成超过合理 Schema 长度仍未收敛，视觉质量门禁未通过；真实 PDF、真实设备和儿童数据均未执行。文本路由可用不代表视觉/Tutor/教材质量验收通过。
- [ ] Ubuntu 升级到 12 GB/8 核后复测：模型确认使用 8 个线程，短文本 JSON 为 1.387 秒；完整 synthetic 大图耗时 373.128 秒，生成 2048 tokens 后以 `provider_response_schema_invalid` 失败。增加 CPU 改善吞吐但未解决视觉 Schema 质量，当前模型不可作为统一本地 Provider；完整证据和重新选型问题见 `docs/local-qwen-evaluation-report-2026-08-24.md`。
- [x] 根据两轮失败结果将 Ubuntu `STUDY_LOCAL_MODEL_ENABLED` 恢复为 `false`，停止本地模型容器并保留模型缓存；API 与两个 AI worker 重新创建后运行时为 `newapi`，不含儿童数据的 synthetic 数学文本 Schema smoke 3.591 秒通过。API/Web/四个 worker 健康，停模后宿主约 10 GiB available、Swap 为 0；远端回滚前 `.env` 备份为 `infra/compose/.env.before-cloud-20260824T140816`。

## 2026-08-22 继续实现记录

- [x] 修复 PostgreSQL 集成测试夹具：每个测试创建随机 Household、真实 Parent/Child Owner 外键并在子数据清理后删除，完整集成矩阵 `30 passed`。
- [x] 语文确定性 scorer 为拼音、生字、词语、句子、阅读、背诵、表达、古诗八类技能补齐 golden 覆盖；失败选择题返回正确答案，待审核原创内容不会进入孩子题库。
- [x] 数学恢复“今日任务”孩子入口；启动前要求每道任务题都有指定题干，并按顺序把题干/教材来源带入拍题与题目确认页；空题任务明确阻断，不退化成通用拍题。
- [x] 数学多题任务在同一会话内逐题执行：中间题追加 Attempt 并保留会话，最后一题才关闭任务；返回或加入复习会停止当前任务序列。
- [x] 数学今日任务的“稍后再做”改为幂等服务端 `skipped` 完成，会话/任务状态和孩子端任务队列同步刷新。
- [ ] 正式教研/版权具名签核、真实 Provider/PDF 质量与成本评测、Ubuntu 真实账号浏览器和相机/相册/弱网/重启等设备 E2E 仍未执行；本轮按约定未连接手机或平板。

## 2026-08-23 继续实现记录

- [x] 数学今日任务增加端侧 SQLite 题号记录；同一服务端/家庭/孩子范围内，进程退出后重新进入任务会从上次未完成的题继续，且不保存题目图片、答案或 Session Token。
- [x] 数学已确认作答在网络不可用时写入端侧 SQLite 结构化队列；恢复联网后按最多 50 条批次调用既有 `/sync-batches`，服务端按事件幂等处理并只确认已返回的事件。
- [x] 数学任务完成、复习收口和“稍后再做”在断网时也写入同一结构化队列；联网后先同步 Attempt，再按顺序重放完成/跳过，幂等键保持不变。
- [x] 服务端拒绝同一任务的第二个活动会话和已结束任务的再次启动；孩子端可在另一台设备通过活动会话继续任务。
- [x] `0036_task_session_progress` 将会话的下一题号保存到 PostgreSQL；Attempt/离线同步只能单步推进，Flutter 启动任务时取服务端与本机位置的较大值，支持另一台设备继续。
- [x] 服务端限制每个孩子每天最多 3 个非撤销任务；未来日期任务提前开始返回明确冲突，过期任务仍可补做；家长可幂等撤销任务，活动会话变为 `revoked` 且后续 Attempt/完成被拒绝，撤销会释放当天名额。
- [x] 语文首页固定为“古诗抽查”和“看图写话”两项；无已审核古诗时仍显示入口和原因，不再展示旧的字词/句子/阅读入口说明。
- [x] Flutter 全量回归增至 `68 passed`，包含 SQLite 任务位置跨进程重开、服务端位置优先、离线作答/完成/跳过入队与重放、任务恢复和空古诗题库入口。
- [ ] 正式教研/版权签核、真实 Provider/PDF 评测、Ubuntu 真实账号浏览器和真机 E2E 留待后续；本轮未连接手机或平板。`0.17.0/0036` 已部署 Ubuntu，并已提交、推送和创建 tag `v0.17.0`。

## 2026-08-23 本地闭环收口记录

- [x] 家长 Web 教材页对数学和语文统一提供“重新理解”“批准知识图谱”和“审核发布”；语文上传/发布提示明确教材分析 v2 和批准后自动开放古诗抽查，不再把语文误显示为未接入分析。
- [x] 看图写话第 2 步没有第一句时不能进入补细节；Provider、网络或图片入口失败时提供不包含图片判断的通用观察问题降级，不复用数学题目提取链路。
- [x] 增加 API 回归：批准语文知识图谱后，已提取的相邻诗句会自动生成孩子端选择题；Web 审核动作和看图写话边界均有单元/Widget 覆盖。
- [x] 本地质量门槛：API 非集成 `244 passed, 32 deselected`，PostgreSQL 集成 `32 passed`，Flutter `70 passed`，Web `35 passed`；Ruff、Mypy（62 files）、OpenAPI `0.17.0`/67 paths、Alembic `0036` 和 `git diff --check` 通过。
- [ ] 正式教研/版权签核、真实 Provider/PDF 质量与成本评测、Ubuntu 真实账号浏览器、Nova 9/iPad/Windows/iPhone 设备 E2E 仍未执行；`0.17.0/0036` 已部署 Ubuntu，并已提交、推送和创建 tag `v0.17.0`。

## 当前目标与验收

- [x] `Subject`、孩子档案、任务和 OpenAPI 支持 `math/chinese`；旧客户端继续默认 `math`。
- [x] `0031_multisubject_chinese` 为教材 Material/Snapshot 增加 subject 并回填旧数据为 `math`，新增语文内容、Attempt、Review 表；单 head 和从零离线 SQL 通过。
- [x] 语文内容保存 grade/skill/task group/revision/source/license；孩子响应不包含服务端 `AnswerSpec`。
- [x] `exact_choice`、`ordered_tokens`、`normalized_text_set`、`concept_evidence` 使用 `chinese-score.v1` 确定性评分，不调用 Provider；提交幂等且追加 Attempt/更新 Review。
- [x] Household/Owner/绑定孩子/已启用学科反向授权；只有绑定孩子可提交，家长只读内容并控制学科开关。
- [x] Flutter 按档案学科显示语文入口；孩子端当前只提供古诗抽查和看图写话，英语仍排最后且保持原禁用门禁。
- [x] 家长 Web 可逐孩子启用语文、按学科上传教材；语文使用独立 subject-aware 教材分析 v2，批准后自动提取古诗题。
- [x] Ubuntu PostgreSQL `0030 → 0031` 前滚和旧教材/快照 `math` 回填；发布前备份隔离恢复、迁移 current/head、表/主键/种子和运行源码通过。
- [x] 本机 PostgreSQL 语文并发提交与导出集成：两条不同幂等键 Attempt 均追加、Review 原子合并、导出和 child cascade 清理通过；随机 Household/Parent/Child synthetic 行均已删除。
- [x] 语文 scorer 的拼音/字词/古诗等确定性类型、到期 ReviewItem API/Flutter 页面、语文教材分析 v2 和家长技能报告代码已实现并有本地/集成覆盖；孩子端 MVP 已以古诗抽查/看图写话替换旧六项演示内容。
- [ ] 正式教研/版权审核内容、真实 Provider/PDF 质量与成本评测、Ubuntu 真实账号浏览器和设备 E2E；公开教材仍须经过具名审核和权利凭证记录后才可作为正式课程发布。
- [x] 登录态 Chromium E2E：首次改密、Cookie/CSRF/撤销、跨家庭角色、双孩子聚合创建与当前孩子切换，并接入 GitHub Actions。

历史验收记录：API Ruff/Mypy（60 source files）与定向测试通过，全量非集成 `229 passed, 28 deselected`；Flutter Analyze 和 52 项测试通过；Web 32 项、TypeScript、ESLint、Prettier、production build 通过。后续 2026-08-22 记录已更新为 API 非集成 `238 passed, 29 deselected`、完整 PostgreSQL `29 passed` 和 Flutter `58 passed`；2026-08-23 Flutter 增至 `67 passed`。OpenAPI `0.16.0` 62 paths/本地引用闭合，Alembic 单 head 和从零离线 SQL 通过。Ubuntu 发布前备份 `/home/syin/study-backups/20260815T144358Z` 隔离恢复为 35 个 public 表/353 个 MinIO 文件；API/Web、`0031` current/head、三张语文表、复合主键、3 条 synthetic seed、旧教材/快照 `math` 回填、四个 worker、英语关闭态、私有 MinIO 端口和容器源码均通过。2026-08-16 新增隔离 synthetic Chromium 登录态 E2E，Web 32 项/构建、认证与档案 API 25 项及 E2E `1 passed`；本机 PostgreSQL 从 `0025` 前滚到 `0031` 后，语文并发/导出集成 `1 passed`。同日 Xcode 已确认 iPad mini 6 在线、开发者模式启用且安装 `Study Child 0.1.0 (1)`，但 `devicectl` 两次远程启动均被 macOS `CoreDeviceService` 初始化超时阻断；随后带 Ubuntu 地址的 Release 构建在签名阶段因 Xcode 没有登录账号及 Team `VZ59988J63` 缺少开发描述文件失败，未产出或安装新包。Nova 9 已由 ADB 识别为 Android 12 的 `NAM-AL00`；设备侧历史记录未完成相机/相册、弱网、重启、账号切换和真实到期复习。当前本地 Flutter 已实现到期 ReviewItem UI、数学指定题目串行入口和任务跳过状态；Ubuntu 真实账号/PostgreSQL 浏览器链路、真实 Provider/PDF 和设备仍未运行。

2026-08-16 PLAN-0032 实现增量：语文内容响应加入待项目 Owner 审核的来源/权利凭证摘要，`docs/chinese-content-review.md` 建立不可伪造的签核台账；新增拼音、生字、词语和原创古诗文积累样例的确定性题型。孩子端可读取到期 ReviewItem 并以相同内容版本重做，家长首页按当前孩子汇总拼音/生字/词语/句子/阅读/背诵技能的 Attempt、正确数与到期数；本机 PostgreSQL 集成 `1 passed` 覆盖并发、导出、复习队列和报告。教材分析现按 Material subject 分派：数学继续 `curriculum-*.v1`，语文使用独立 `chinese-curriculum-*.v2` schema/prompt 和短篇章边界证据，保留既有父母审核与私有页图边界；定向 API `21 passed`、Ruff/Mypy 通过，未上传真实 PDF 或调用 Provider。正式具名教研/版权签核、Ubuntu 发布、真实账号浏览器和四设备完整 E2E 仍未完成。

2026-08-16 PLAN-0033 实现增量：旧六项原创演示内容通过 `0033` 前向退役而不删除 Attempt/Review；已审核语文教材的逐行古诗自动生成相邻句选择题，错答返回正确下一句并进入确定性 Review。看图写话新增 `0034_picture_writing_guides`、独立 `picture-writing-guide.v1` Provider Schema 与 child-scoped `/picture-writing-guides` API；它只保存有界场景观察、提问和句式支架，不复用数学 `ImageAnalysisJob`/`QuestionExtraction`，也不生成范文或评分。`0035` 将语文内容技能约束前向扩展为 `poem`。Flutter 提供拍照/相册、脱敏确认后的“观察-说一句-补细节”页面。API 定向 `27 passed`、Ruff/Mypy、OpenAPI YAML 与 Alembic 单 head、Flutter Analyze/`53 passed` 通过；本机 PostgreSQL 已前滚至 `0035`，古诗并发 Attempt/Review/导出集成 `1 passed`。`v0.16.0` 已推送并前向部署 Ubuntu，备份隔离恢复、API/Web/worker、`0035`、OpenAPI 路径、私有 MinIO 端口和容器源码均复核。真实 NewAPI Adapter 对无人物/无文字的合成图返回合规 Schema；Nova 9 已安装 `0.16.0 (2)` 并配置 LAN 地址，WLAN 可达 Ubuntu 且健康检测未再报连接错误。重装后无会话，真实登录、相机/相册、权限、上传、复习和弱网 E2E 未执行。

2026-08-17 Nova 9 相册联调增量：登录态恢复后进入语文看图写话，使用无人物/无文字的合成图完成系统相册选择、脱敏确认和上传；Ubuntu picture-writing API 返回 `201`，设备展示第 1 步的观察与提问。相机、句子输入/细节第 2～3 步和完成返回因 USB 调试在下一步点击时断开而继续待验收。

2026-08-16 发布/设备记录：`1b5ecc1` 和 `v0.15.0` 已推送；首次 Ubuntu 迁移因历史 `alembic_version.version_num varchar(32)` 不能写入长 `0032` revision 而事务回滚，随后 `4b95757`/`v0.15.1` 前向扩展该列至 `varchar(64)` 并成功发布。备份 `/home/syin/study-backups/20260816T072837Z` 已隔离恢复为 38 张 public 表和 353 个 MinIO 文件；Ubuntu API `0.15.0`、Web、四个 worker、`0032` current/head、语文 v2 运行时常量和 MinIO 非宿主暴露均通过。Nova 9（Android 12）以 `adb install -r` 保留会话升级并实际显示学习桌的数学/语文/锁定英语及语文的生字、拼音、古诗文、句子、词语内容；未作答或写入 Attempt。当前账号无到期 ReviewItem，故空状态不显示复习卡，真实到期复习提交、相机/相册、弱网、重启、切换账号，以及 iPad mini 6/iPhone 11/Windows E2E 仍未执行。

回滚：隐藏语文入口并继续只发送 `math`；保留 `0031` 新列/表和已追加学习事实，以前向修复恢复。禁止删除语文 Attempt/Review 或降级数据库作为回滚。

---

## 保留任务：TASK-0011 英语学科与合规口语练习框架

## 当前任务元数据

- 状态：`IN_PROGRESS（框架、自动化、双平台 release 和 Ubuntu 禁用态部署已完成；PostgreSQL 并发/级联集成与实体设备验收待完成）`
- 类型：`FEATURE / API CONTRACT / PRIVACY / DEVICE`
- 优先级：`P1`
- Owner：Codex（执行）；项目 Owner（批准 2026-07-29 实施计划）
- 创建/更新：`2026-07-29`
- 关联：`PLAN-0022`、`ADR-0025`、`TODO-218`

## 当前目标与验收

- [x] 首页固定显示数学与英语，数学路由和模型不变；英语锁定态始终可见。
- [x] 家长逐孩子设置启用、`Pre-A1/A1/A2` 与同意版本；Provider 不可用时不能开启。
- [x] API/OpenAPI `0.12.0`、`0029`、摘要导出/删除、Bearer WebSocket 与 PCM16 合同已实现。
- [x] Flutter 三情景、摘要、按住说话、打断和后台/销毁关麦；`record 7.1.1`、`flutter_soloud 4.0.13` 与权限已锁定。
- [x] 不包含 Gemini SDK/Adapter/Key；默认 `disabled`，`fake` 仅测试。
- [x] API 定向、Flutter 全量、Web 全量、契约引用、迁移静态 SQL、双平台 release 与固定英语安全 eval 已通过。
- [ ] PostgreSQL 集成、API 全量两个既有失败的后续修复，以及 iPad/Nova 9 实体验收。
- [ ] 合规 Provider、正式同意文本和真实质量/成本/儿童安全评测未批准；入口不得开放。

回滚：关闭全局英语开关并保留附加表/摘要；禁止为回滚删除儿童记录。Ubuntu 运行态已确认为关闭、Provider 为 `disabled`。

## 2026-08-10 用户明确增量：GitHub Actions APK 与部署文档

- 状态：`COMPLETE（本地与 GitHub runner/Release 远端验收通过）`
- [x] 新增手动及 `v*` 标签触发的 Android APK workflow，固定 Flutter `3.44.6`/Java 17，并在构建前执行格式、Analyze 和测试。
- [x] 生成 ARM32、ARM64、x86_64 release APK、`SHA256SUMS` 和 `BUILD-INFO.txt`；手动触发保留 Actions Artifact，`v*` 标签触发额外自动创建同名 GitHub Release 并上传附件。
- [x] Android Gradle 支持可选稳定 release keystore；无 Secrets 时保留明确标注的 evaluation debug 签名路径，正式 application ID/商店签名仍未完成。
- [x] 新增 `docs/DEPLOYMENT.md`，覆盖 GitHub、签名、下载校验、侧载、Compose、首次账号、网络、备份升级和回滚；README/RUNBOOK 已链接。
- [x] 将 `tchMaterial-parser` 作为独立外部教材下载工具说明；不引入代码或依赖，不接收 Token，不分发教材，上传前继续要求权利与个人信息确认。
- [x] 修复 API CI：全仓 Ruff 格式/检查、正式 `mypy src` 范围和非集成测试通过；修复题目确认角色判断与孩子删除幂等重放两个既有失败。
- [x] 本地 Flutter 依赖、格式、Analyze、50 项测试和三个 ABI release 构建通过；YAML 解析、文档链接和差异检查通过。
- [x] GitHub Quality run `31388975526` 成功；`v0.1.1` Android run `31389022670` 的构建和发布 Job 均成功。公开 Release 含三个 APK、`SHA256SUMS`、`BUILD-INFO.txt`，构建提交为 `56260c2`、Flutter `3.44.6`、签名模式为 `evaluation`。

未执行：稳定 keystore 路径的真实签名、Nova 9 安装、Play Store 和 Ubuntu 重新部署。回滚时关闭自动 Release Job，仍保留可下载 Artifact；API 采用前向修复，不删除设备或服务端数据。

## 2026-08-10 用户明确增量：移除成人英语并准备 GitHub 开源

- 状态：`COMPLETE（未提交、未推送、未部署）`
- 范围：删除未部署的家长本人英语练习、成人 Gemini Provider/授权/配置/依赖/测试/文档；孩子英语学科、家长逐孩子设置和全部供应商中立合同必须保留。
- [x] 建立 `PLAN-0028`，明确不删除 `0029` 表、孩子摘要、Flutter 英语页面、家长设置或通用实时打断逻辑。
- [x] 完成成人增量代码、配置、契约说明和 ADR 清理；孩子会话、WebSocket 打断、家长逐孩子设置、摘要、导出/删除、迁移和 Flutter 英语页面均保留。
- [x] 采用 Apache-2.0，增加 `LICENSE`/`NOTICE`，更新根 README、项目状态、开源边界和目标 GitHub 地址；本地 `origin` 已配置为 `git@github.com:yubinhong/AIStudy.git`。
- [x] API 英语 `16 passed`、相关 Ruff/Mypy、英语安全 eval `7/7`、Flutter `50 passed`/Analyze、Web `32 passed`/类型/格式、OpenAPI/JSON、Compose、锁文件、README 链接、密钥特征和 `git diff --check` 通过。

未执行：API 全量/集成、Web build/lint、Flutter release、实体设备、Ubuntu 部署、Git commit/push 和 GitHub 远程连通性。本轮未修改数据库结构或孩子 UI；`TASK-0011` 的 PostgreSQL 并发/级联、真实 Provider 合规和设备验收仍按原状态未完成。

回滚：只允许恢复孩子供应商中立框架；不得恢复成人 Provider、成人授权或任何云端语音密钥配置。数据库不降级、不删除英语摘要。

## 2026-07-30 用户明确增量：家长学习记录

- 状态：`COMPLETE（本地交付并已部署 Ubuntu 0.13.0/0030）`
- 结果：工作台直接显示每道到期错题的题干与到期日；新增独立“学习记录”页，默认最近 30 个上海自然日，可选择 180 天窗口内单日。API/OpenAPI 增加带时区半开区间、31 天/500 条上限和 Household/Child 授权。
- 生命周期：`0030_learning_history_retention` 增加清理索引；DataLifecycle worker 固定清理超过 180 天且不再被开放错题引用的 VerifiedQuestion/TutorTurn 和已结束复习链路。Attempt、AuditEvent、账号、教材和开放错题不删除；可用 `LEARNING_HISTORY_CLEANUP_ENABLED=false` 暂停后续清理。
- 验证：API 定向 `9 passed`、PostgreSQL 生命周期集成 `1 passed`、Mypy 58 files；Web `32 passed`、Lint、TypeScript、Prettier 和生产构建；Alembic 单 head/离线 SQL、OpenAPI 解析与 `git diff --check` 通过。API 全量非集成为 `218 passed, 2 failed, 28 deselected`，两个失败与本轮前已记录的 Owner 作用域/孩子删除幂等回归一致。
- 发布/风险：2026-07-31 已在 Ubuntu 备份并隔离恢复 PostgreSQL/MinIO，备份路径为 `/home/syin/study-backups/20260731T020739Z`；远端已前滚到 API/OpenAPI `0.13.0` 与 `0030`，API/Web/四个常驻 worker 健康、迁移服务成功退出，生命周期 worker 首轮清理计数均为 0。仍未执行浏览器登录态 E2E；本地 PostgreSQL 未前滚，集成测试只写入并清理独立 synthetic 行。已经按策略删除的数据不能通过应用回滚恢复。
- 回滚：关闭生命周期开关并回退 API/Web；保留 `0030` 的附加索引，采用前向修复，不执行破坏性 downgrade。

## 2026-07-29 本地交付记录

- 结果：完成两学科首页、家长设置、三情景英语页、Bearer WebSocket、供应商中立流式 Provider 会话、PCM16 分片、终态不可变摘要、导出/删除和英语安全 Policy；`fake` 只能由测试依赖注入，部署环境无法启用。未加入 Google SDK、Gemini Adapter、密钥或 Provider URL。
- 验证：英语/导出定向 `20 passed`，Ruff、Mypy（58 source files）、英语安全 eval `7/7`；OpenAPI `0.12.0` 为 60 paths/92 refs，8 个 JSON Schema 可解析，Alembic head/`0028 → 0029` 离线 SQL 通过；Web `29 passed`、Lint、TypeScript、Prettier、生产构建；Flutter `50 passed`、Analyze、格式、Android release APK（64.1 MB）和 iOS 无签名 `Runner.app`（24.0 MB）通过。
- 未执行：本机无 Docker daemon 或 PostgreSQL 16，故 `0029` 真实前滚/从零建库/并发与级联集成测试未运行；实体设备连接检查未获授权，iPad mini 6/Nova 9 麦克风、扬声器、弱网、打断和后台生命周期未验收。
- 既有失败：API 非集成全量为 `214 passed, 2 failed, 27 deselected`；失败仍是拍题确认 Owner 作用域 `404` 和孩子删除幂等重放 `404`，均来自本轮开始前的多家庭/所有者改动，本轮未扩大范围修复。
- 回滚：保持 `STUDY_ENGLISH_LIVE_ENABLED=false`、`STUDY_ENGLISH_LIVE_PROVIDER=disabled` 并保留摘要表。2026-07-31 已随 `0.13.0`/`0030` 部署 Ubuntu，运行态仍为关闭且 Provider 为 `disabled`；不得为回滚删除附加表或摘要。

---

## 保留任务：TASK-0010 教材原页、知识图谱与可用任务整改

### TASK-0010 元数据

- 状态：`IN_PROGRESS（PLAN-0018 已随 Ubuntu 0.13.0/0030 运行；最新 iPad 包已安装，设备信任与真实教材/NewAPI/E2E 待验收）`
- 类型：`FEATURE / API CONTRACT / DEVICE`
- 优先级：`P0`
- Owner：Codex（执行）；项目 Owner（用户，要求教材图片语义、整本知识归纳和错题任务立即可用）
- 创建/更新：`2026-07-18`
- 关联：`PLAN-0018`、`ADR-0020`、`ADR-0021`、`ADR-0022`、`ADR-0023`

### TASK-0010 目标与验收

修复教材 PDF 丢失图片语义和任务推荐使用残缺文字的问题：保留受鉴权原页，云端分批理解页面并归纳整本知识图谱，家长批准后才允许发布和推荐；推荐只使用开放错题与已批准知识点/具体练习。

- [x] PDF 逐页生成有界私有 JPEG，原件/页图不返回对象键、MinIO URL 或预签名地址。
- [x] NewAPI 每批最多 4 页多模态理解，再以严格 Schema 归纳整本章节、知识点、目标、先修关系和练习来源。
- [x] `0025` 保存页图、页级分析、知识图谱、知识点和 AI 版本/指纹/延迟/token/成本字段。
- [x] Web 以原页为主、文字为辅助，展示知识图谱并提供家长批准；批准前 PDF 不可发布。
- [x] 推荐不再读取 `CurriculumChunk.text` 抽题，只使用批准知识点中的来源题与全部开放错题。
- [x] OpenAPI `0.11.0`、API 非集成测试、mypy/相关 ruff、Web test/build、Flutter test/analyze、迁移 offline SQL 和本机 PostgreSQL 前滚已通过。
- [x] 依赖教材图片的任务在 Flutter 显示视觉说明，并通过孩子 Session 受鉴权打开对应原页；客户端限制 JPEG/2 MiB。
- [x] `needs_review` 只在 `mistake-closeout` 返回错题记录后完成并回学习桌；题目/作答未确认时不伪造“已加入复习”。完整解答可靠匹配已批准知识图谱时只使用该知识点范围；无匹配仍在确认门禁后给出适龄基础解法，响应不附教材来源也不伪造知识点。
- [x] 教材与任务页的顶栏孩子切换以有效 `?child=` 为唯一当前孩子来源；切换时清除旧孩子的教材、知识图谱、推荐和预览瞬态数据，过期请求不得回写覆盖新孩子页面。
- [ ] 真实 118 页 PDF/NewAPI 输出质量、费用和失败重试验收；浏览器/设备 E2E。
- [x] 多家庭会话作用域、唯一超级管理员和显式公开教材复用：`0028` 将最早 `parent_admin` 迁移为唯一 `super_admin`，其余迁移为普通家长；孩子档案绑定创建它的家长，普通家长只能管理自己的孩子。超级管理员可创建新家庭的普通家长，其他家庭不再有管理员角色。教材复用仍只发生在显式公开、精确内容指纹匹配且来源已批准的 PDF，目标仍独立审核。2026-07-28 已完成 Ubuntu 备份、隔离恢复、迁移与运行态验证；真实普通家长越权和浏览器流程待后续验收。
- [x] 家长 Web 的管理员可发现性：修复 `/curriculum` 缺失 Suspense 导致生产构建失败、旧 Web 镜像继续运行的问题；通过会话代理读取当前账号，顶栏显示用户名/角色并提供账户管理与注销入口。Ubuntu Web 已无缓存后重建，浏览器以 `admin` 会话验证当前身份、退出登录入口、家长账号与独立家庭表单；未创建测试家庭或账号。

回滚：停止 `curriculum-analysis-worker` 并禁用知识图谱推荐；保留原 PDF、已生成私有页图和既有学习事实。`0025` 只新增表/可空外键，可在无新引用时 downgrade；不得恢复残缺文字抽题。

## 2026-07-28 Web 拍题聚焦与家庭权限整改记录

- 结果：家长首页已移除今日学习任务与本周学习目标；教材页仅保留上传、知识图谱审核/发布和教材快照，移除手工小节与任务推荐；孩子管理页仅保留孩子档案和账号管理，移除今日安排。
- 权限：新增超级管理员专属的 `/family` 页面与导航。服务端新增家长列表和删除合同，普通家长直接请求仍被拒绝。开通仍创建“新家庭 + 首个普通家长”；删除仅允许目标为普通家长、没有所属孩子且超级管理员重新验证当前密码时执行，成功会撤销目标会话。
- 数据与回滚：没有删除既有任务、推荐、教材或学习事实，也未更改孩子端错题/复习闭环。恢复入口应通过前向修复，禁止用删除用户或孩子来回滚。
- 验证：API 定向 `34 passed`、Ruff、Mypy（56 source files）；Web `27` 项测试、Lint、TypeScript、Prettier、生产构建通过。本机 Node `20.17`/pnpm `9.10` 不满足锁定引擎，仅作为带 warning 的本地验证。2026-07-28 已部署 Ubuntu，锁定 Node `24.18`/pnpm `11.7` 的 Web 构建通过；API/Web 与四个 worker 健康，Alembic current/head 为 `0028_super_admin_ownership`，未认证家庭权限 API 返回 `401`，`/family` 返回 `200`。普通家长/超级管理员浏览器人工流程待执行。

## 2026-07-29 iPad Release 覆盖安装记录

- 设备：iPad mini 6（iPad14,1）已配对、开发者模式启用。通过 Flutter `3.44.6` 生成 21.2 MB 的 Release `Runner.app`，并注入首次服务地址 `http://192.168.1.4:8000`。
- 交付：使用项目 Team `VZ59988J63` 自动签名构建，`devicectl` 覆盖安装并启动 `com.example.studyChild`；设备应用列表确认 `Study Child 0.1.0 (1)`。
- 未执行：不读取设备上的账号或学习数据；真实登录、相机/相册权限、局域网连接、拍题、错题 closeout 与复习闭环仍需用户在设备上操作验收。

## 2026-07-29 完整解答教材匹配降级记录

- 结果：第 3 级完整解答不再把知识图谱未命中作为 `409` 阻断。可靠命中时仍仅使用批准知识点的最小范围；未命中时 Provider 只收到已确认题目、作答证据和 `not_matched` 标记，必须使用适龄基础方法，且 API 返回空教材来源与独立策略版本。
- 验证：API Tutor/NewAPI 定向 `23 passed`、相关 Ruff 与 Mypy（58 source files）通过；Flutter `capture_api_client_test.dart` `15 passed`、全量 `50 passed`、Analyze、Dart 格式化与 `git diff --check` 通过。Ubuntu API 与教材分析 worker 已重建健康，运行态已确认加载 `not_matched` 降级策略；修复版已自动签名、覆盖安装并启动 iPad。未做真实题目或 Provider 输出质量验证。
- 回滚：若出现安全或教学质量问题，使用前向修复；不得删除已有 TutorTurn、VerifiedQuestion、错题或复习事实。

- 部署修正：首次发布把 `routes/tutor.py` 错同步到远端包根目录，导致运行中的旧路由仍以 `409` 阻断未匹配的完整解答；L1/L2 的 `200` 与 L3 的 `409` 日志证实该差异。已将文件同步到正确路由目录、删除该未引用副本并仅重建 API；健康检查和容器内路由源码确认 `general-solution-policy.v1` 已加载。未读取题目、作答或账号内容。

## 2026-07-24 Ubuntu 前滚记录

## 2026-07-28 多孩子教材范围整改记录

- 结果：定位到 `/curriculum` 为客户端页面，只在初次挂载读取 URL `child` 参数，顶栏切换虽然更新 URL 但不会更新页面的 `childId`。现在该页由 `?child=` 与已授权孩子列表直接推导当前孩子，切换时使旧网络请求失效并清空旧教材、知识图谱、推荐和预览状态，再加载新孩子作用域的数据。
- 教材复用审计：当前 PDF 对象键包含 `household_id` 和 `child_id`，同一家庭不同孩子上传相同 PDF 会保存、渲染和分析两次，尚无复用。已建立 PLAN-0019 和 Proposed ADR-0024：先做同 Household 不可见原件引用复用与最后引用删除；孩子审核/发布/任务事实不共用；跨家庭去重、多家庭注册/邀请与公网开放不在当前单家庭认证范围。
- 验证：新增 URL 选择回归；Web 定向 `4` 项、TypeScript、ESLint 和 Prettier 通过。本机 Node `20.17`/pnpm `9.10` 低于锁定 Node `24.18`/pnpm `11.7`，命令仅产生 engine warning，Ubuntu 构建仍使用锁定版本。

## 2026-07-28 多家庭与公开教材复用记录

## 2026-07-28 超级管理员与孩子归属整改记录

- 结果：按项目 Owner 最新确认，取消“每个家庭一个管理员”。新增 `0028_super_admin_ownership`：最早 `parent_admin` 升级为唯一 `super_admin`，其他既有家庭管理员降为普通 `parent`；新家庭仅创建普通家长。孩子档案新增不可空 `owner_account_id`，历史数据按家庭内最早可用成人回填；孩子用户名继续全局唯一。家长管理、孩子档案、孩子账号、教材和推荐入口按所有者重新校验，越权返回不可枚举的 `404`。
- 恢复：新增 `services/api/scripts/reset_super_admin_password.py`，仅能在受信 API 容器/服务器控制台使用，要求交互式二次输入密码并撤销旧会话；本轮没有读取或重置任何真实密码。
- 验证：API 定向 `33 passed`、Ruff、Mypy、Python compile、Alembic head 与从零生成静态 SQL；Web 会话/家庭代理/账号菜单 `3 passed`、TypeScript 与 Prettier通过。Ubuntu 备份 `/home/syin/study-backups/20260728T082318Z` 已通过隔离恢复（32 个 PostgreSQL public 表、341 个 MinIO 文件）；`0028_super_admin_ownership`、`admin=super_admin`、全库 1 个超级管理员、0 个未归属孩子及 API/Web 健康均已验证。PostgreSQL 本机集成与真实普通家长浏览器越权流程仍待后续验收。

- 结果：首次 `admin` 迁移为 `parent_admin`，每个家庭管理员可创建普通家长，也可为亲戚开通完全隔离的新家庭及其首个管理员。用户名在自托管实例中全局唯一，普通家长和孩子不能创建家长或家庭；Web BFF 与孩子 Flutter 从已认证 `/auth/me` 获取当前 Household，不再写死默认家庭。
- 教材：默认保持私有且不复用。只有家长在上传时显式声明国家公开教材可复用，并完整匹配 SHA-256、MIME、字节数且来源知识图谱已批准时，系统才复用私有 PDF/页图和派生解析为目标家庭的待审核草稿；不会返回来源家庭、对象键或命中信息。删除会保留仍被其他材料/Snapshot 引用的对象。
- 验证：API 定向 `25` 项、Ruff、Mypy、迁移 head；Web `23` 项、TypeScript、Prettier；Flutter `48` 项和 Analyze 通过。未部署 Ubuntu，未在真实 PostgreSQL、浏览器或设备上验收本项。

## 2026-07-28 Ubuntu 与 iPad 交付记录

- 结果：保留 Ubuntu `infra/compose/.env`、PostgreSQL/MinIO/Redis 数据卷和远端配置，使用 `rsync` 同步当前工作区后以 `DOCKER_BUILDKIT=0 docker compose ... up -d --build` 成对重建 API、Web、迁移和五个 worker。所有服务运行中，API `/healthz` 返回 `0.11.0`，Alembic current 为 `0026_parallel_curriculum`。
- iPad：无线设备 `00008110-0011356E0E41801E` 已识别；Release `Runner.app` 使用 Xcode 自动签名并安装到设备，构建时注入初始服务地址 `http://192.168.1.4:8000`。设备服务列出 `Study Child 0.1.0 (1)`，但首次启动被 iOS 拒绝，原因是开发者签名尚未在该 iPad 上显式信任；需在 iPad“设置 → 通用 → VPN 与设备管理”信任 Team `VZ59988J63` 后再启动验证。
- 未执行：真实教材/Provider 质量、费用和设备拍题闭环；本次 Flutter `run` 的编译成功，安装成功，启动因设备信任门禁未完成。

- 结果：在不读取家庭或教材内容的前提下，Ubuntu 单家庭 Compose 已从 API `0.10.0`/Alembic `0024_intelligent_recommendations` 成对前滚到 API `0.11.0`/`0025_curriculum_knowledge_map`；API、Web、ImageAnalysis、MaterialParse、CurriculumAnalysis 和 DataLifecycle worker 均健康，MinIO `9000` 仍无宿主端口映射。
- 发布前：修复备份脚本遗漏教材 worker 且使用 `docker compose start` 无法满足已完成 migrate 依赖的问题。脚本现在冻结所有实际存在的写入 worker，并直接恢复其原容器；`/home/syin/study-backups/20260724T015356Z` 已通过 SHA-256、隔离 PostgreSQL 恢复（28 张 public 表）和 29 个 MinIO 文件快照校验。
- 烟雾：远端 API `/healthz` 返回 `0.11.0`，Alembic current/head 都是 `0025_curriculum_knowledge_map`；教材分析和受鉴权原页 OpenAPI 路径存在，所有 Compose 服务健康。未上传、解析或发送真实教材。
- 本地复核：API 非集成 `189 passed, 24 deselected`、迁移表结构断言、从初始版本到 `0025` 的 Alembic 静态 SQL、Mypy（56 source files）、教材相关 Ruff lint/format、Tutor Policy synthetic eval（5 cases）、Flutter `43` 项和 Analyze、OpenAPI/JSON Schema 结构检查均通过。Web 复跑受本机缺少锁定 Node `24.18`（仅有 Node 16/20/22）阻塞，未把 Node 20 的 engine warning 结果计为通过。
- 2026-07-24 教材分析兼容修复：一个已解析的 110 页 PDF 在 NewAPI 返回 `provider_curriculum_page_schema_invalid` 后暴露网关兼容问题。API 现在依次尝试 `json_schema`、`json_object`、无 `response_format`，每次仍在服务端以固定 Pydantic Schema 校验；Schema 无效只记录版本/字段路径，不记录教材内容，并在同一 Provider 上最多重试一次。Ubuntu API/教材 worker 已重建，1 像素合成图经当前 `gemini-3.1-flash-lite` 实测在 `json_object` 回退后通过页级 Schema。真实 PDF 未自动重试，需家长从页面点击“重新理解”；仍待人工核对知识图谱质量、费用和浏览器/设备验收。
- 2026-07-24 难度枚举修复：真实 Provider 对第 4 页两个练习返回了不在 `basic/medium/advanced` 中的难度标签。页级提示升级为 `curriculum-page-visual.v2` 并明确这三个值；服务端只将明确中英文同义词归一化，未知值仍严格拒绝。Ubuntu API/教材 worker 已重建；运行中 Worker 用合成“基础题”响应验证为 `basic`，未读取或重试真实教材。
- 2026-07-24 置信度标度修复：后续 Provider 响应在页、知识观察和练习层返回了百分比/分值形式的 `confidence`，不满足 `[0,1]` Schema。页级提示升级为 `curriculum-page-visual.v3`，全书提示也明确只接受 JSON 数值 `0`～`1`；服务端只将有限的百分比、`分` 和 `0`～`100` 数值标度归一化，文字/超范围/非有限值仍拒绝。Ubuntu API/教材 worker 已重建；运行中 Worker 用合成 `91`、`90分`、`92%` 验证为 `0.91`、`0.90`、`0.92`，未读取或重试真实教材。
- 2026-07-24 小节标题修复：Provider 对首个页面返回了无效 `section_title`。页级提示升级为 `curriculum-page-visual.v4`，并要求没有独立小节时重复章节标题；服务端仅在同页 `chapter_title` 非空时回填该值，否则仍拒绝。Ubuntu API/教材 worker 已重建；运行中 Worker 用合成空小节标题验证回填为同页章节标题，未读取或重试真实教材。
- 2026-07-26 稀疏页证据修复：真实 Provider 在第 4 页知识观察中遗漏 `learning_objectives`。该字段在页级中间证据改为可为空，提示升级为 `curriculum-page-visual.v5`，要求没有可靠依据时保留空数组而非编造目标；整书 `ProviderBookKnowledgePoint` 仍要求至少一个学习目标，家长批准门禁不变。Ubuntu API/教材 worker 已重建，运行中 Worker 用合成缺字段响应验证接受为空；既有真实教材不自动重试。
- 2026-07-26 临时网关失败修复：真实 98 页教材的第 4 次人工尝试在前三个页批次完成 JSON object 回退后，因 NewAPI `provider_http_5xx` 失败；该失败此前会立即终止整本作业。现在同一请求只对 `429`/`5xx`/网络/超时按 1 秒、2 秒退避，最多三次；失败状态继续可见，页面准确显示“AI 理解失败 · 可安全重试”，不会刷新即自动重试。Ubuntu API、教材 worker 与 Web 已重建并健康，运行中 Worker 已验证三次上限；真实教材未自动重试。
- 2026-07-26 长任务状态修复：Worker 只在整本图谱完成时写入 `analyzed_page_count`，此前 Web 不轮询，`0/98` 会持续到刷新而看似卡住。分析中现在显示“全文处理中（共 N 页）”，每 8 秒读取一次服务端状态；完成或失败自动反映，当前作业不会因前端轮询重新入队。Ubuntu Web 已重建并健康。
- 2026-07-26 整书范围修复：第 5 次真实 98 页尝试已完成页级批次和整书 Provider 调用，却在服务端把整书章节范围要求为精确覆盖全部页面时失败为 `curriculum_analysis_invalid`。该约束错误地将封面、目录和空白页当作必须归属知识章节；现在只拒绝章节范围或知识点页码引用未分析页面，并将此类失败码细化为 `curriculum_book_reference_invalid`。整书 Prompt 升级为 `curriculum-book-consolidation.v2`，明确非知识页可省略。真实教材未自动重试。
- 2026-07-26 审核发布状态修复：真实教材知识图谱已批准并有 8 个知识点，但 Web 继续依据旧“待审核知识图谱”占位小节显示“AI 理解准备中”，从而隐藏“审核发布”。占位判断现在只在没有知识图谱时生效；已批准图谱会显示发布按钮，发布后知识范围可供讲解和来源受限任务推荐使用。Ubuntu Web 已重建并健康。
- 2026-07-26 发布解析状态修复：已发布教材仍显示“未解析正文”，但远端元数据已确认其有 98 条正文片段、98 张私有原页、98 页分析和已批准知识图谱。Web 现以已批准且有分析页的知识图谱判断解析可用性，发布状态显示“已发布 · 知识图谱已启用”，任务推荐也据此区分真实无题与旧未解析范围。Ubuntu Web 已重建并健康。
- 2026-07-27 教材名称与一年级整书兼容修复：PDF 上传不再读取手工小节的“数学教材-本地版/上学期”默认值，而先显示按文件名生成的待识别名；本地解析仅在前四页明确匹配数学、年级和上/下册时回填如“数学一年级上册”，显式 API 家长名称不被替换。整书 Prompt 升级为 `curriculum-book-consolidation.v3`，封面/目录/单元过渡章节可为空，`exercise_keys`/`prerequisites` 的 `null` 仅规范为 `[]`；知识点的目标、页码、来源边界和批准门禁不放宽。定向 Provider/解析/上传 37 项、完整 API 非集成 197 项、Ruff/Mypy 和 Web `tsc`/20 项测试通过；Ubuntu API、Web、MaterialParse/CurriculumAnalysis Worker 已重建且 healthy，当前失败作业仍需家长显式“重新理解”才会以新规则重试。
- 2026-07-27 一年级整书二次兼容修复：真实 Provider 仍会把 `exercise_keys` 返回为非数组，或为少数不确定知识点遗漏 `learning_objectives`。整书 Prompt 升级为 `curriculum-book-consolidation.v4`；服务端把任何非数组的可选练习/先修引用丢弃为空数组，并过滤所有缺失、为空或含空字符串目标的知识点，不补造学习目标。若过滤后整书没有完整知识点仍失败并要求家长重试；否则保留完整点进入审核。完整 API 非集成 197 项、Ruff/Mypy 通过；Ubuntu API 与 CurriculumAnalysis Worker 已重建且健康，运行容器确认 Prompt v4，家长可显式重试当前失败作业。
- 2026-07-27 一年级整书三次兼容修复：真实 Provider 可返回合法字符串数组但超过 `ProviderBookAnalysis` 的固定集合上限，导致 `exercise_keys` 等字段在最终 Schema 校验失败。整书 Prompt 升级为 `curriculum-book-consolidation.v5`；服务端仅对已有有效项截取既有上限（章节/知识点 `40`、目标/先修项 `10`、练习引用 `30`），不补造事实；缺失目标、无效页码和未知练习来源的拒绝路径不放宽。新增 `31` 条练习引用、`11` 条目标和先修项的回归测试。验证通过：Provider/分析定向 19 项、API 非集成全量、Ruff、Mypy（56 个源文件）；Ubuntu API 与 CurriculumAnalysis Worker 已重建，API health 正常且运行容器确认 Prompt v5。既有失败任务不自动重跑，须由家长明确“重新理解”。
- 2026-07-27 多教材并行发布修复：旧发布操作会把同一孩子已有 `published` 快照静默改为 `rejected`，页面因此显示“已替换”，推荐也只读取最新一份教材。发布仓储现保留全部已发布快照；推荐聚合每一份已发布且已批准知识图谱的知识点，并继续按 `snapshot_id` 绑定来源。新增 `0026_parallel_curriculum` 将旧自动替换造成的 `rejected` 快照恢复为 `published`，不删除或改写教材内容。API 定向 14 项、API 非集成全量、Ruff/Mypy、迁移离线 SQL、Web 20 项测试/类型/格式/Lint 通过；Ubuntu 已在备份后前滚，API/Web 健康且教材状态汇总为两份 `published`。首次超长 Alembic revision ID 在提交前整体回滚，无数据修改；短 ID 修正后迁移成功。回滚采取匹配 API/Web 回退，保留 `0026` 的已恢复发布状态，禁止再引入自动停用旧教材的逻辑。
- 2026-07-27 Nova 9 客户端连接/账号修复：定位 release APK 的 `INTERNET` 权限只存在于 debug/profile 清单，生产 APK 因而不能访问 Ubuntu API；发布清单现声明该权限，并允许用户显式配置的家庭 LAN HTTP 地址。旧安全会话恢复时会从 `/auth/me` 读取、保存并显示实际孩子用户名，连接错误页面保留服务端地址/网络原因且可返回改地址。Flutter `43` 项、Analyze、格式和 release APK 合并清单检查通过；`aapt` 确认权限和 `usesCleartextTraffic` 生效。Ubuntu API 本机健康为 `0.11.0`，不需服务端发布；release APK 已于 `2026-07-27 16:21:21` 覆盖安装并启动 Nova 9，Android 日志未见网络权限/明文 HTTP 拒绝，近端 API 日志有初始化认证/档案请求。设备侧仍须确认真实用户名和学习桌已加载。
- 2026-07-27 推荐计划日可见性修复：截图中的批准计划日期为 `2026-08-01`，孩子端原实现仅渲染 `scheduled_for == 今天`，所以未来题目并未丢失而是没有当前可开始入口。孩子端现在读取最近未来 `assigned` 计划并只读提示标题/日期；当天和过期未完成的 `assigned/in_progress` 任务可开始，未来任务仍不能提前启动。Web 批准消息和已批准标签明确“将在计划日的今日任务显示”。不变更 API、任务数据、来源题或授权。Flutter `45` 项/Analyze、Web `20` 项/类型/Lint/格式通过；Ubuntu Node `24.18`/pnpm `11.7` Web 已重建并通过 `/healthz`，release APK SHA-256 为 `b182359d70cee99ab7bf7dad70f31d5e242ec0c8b7ca7d3a0e3cb85985e5d273`，已于 `2026-07-27 16:47:48` 覆盖安装 Nova 9。仍待用未来计划/过期计划做设备界面人工验收。
- 2026-07-27 任务入口临时隐藏：Nova 9 体验确认“今日任务”会堆叠多个已分配计划，且进入“计算题”仍跳转通用拍题，说明来源题已入库但没有孩子端任务执行流。学习桌现不请求或渲染任务列表、未来计划提示、今日任务按钮和“稍后再做”，保留错题讲解/复习错题；不删除 Task、Recommendation、来源题、家长审批或 API 合同。Flutter `44` 项与 Analyze 通过，包含任务隐藏和账号切换修复的 release APK 已于 `2026-07-27 17:36:38` 覆盖安装 Nova 9。任务重新开放前须完成 `TODO-215` 的单任务直接执行、完成/跳过和离线状态设计。
- 2026-07-27 账号切换显示修复：孩子端 `ChildAuthGate` 在账号切换时已正确更换 Session/用户名，但 `ChildProfileScreen` 只在 `initState` 获取孩子档案，导致 A→B→A 可能继续复用 B 的内存档案和显示状态。档案页现在在服务端地址、授权 Session 或用户名变化时重新调用目标账号的加载器；不改写已保存账号、服务端会话或任何学习数据。新增 A→B→A Widget 回归，Flutter `44` 项/Analyze 和 release APK 构建通过；APK 已于 `2026-07-27 17:36:38` 覆盖安装 Nova 9，待设备侧完成 A→B→A 手工复核。
- 2026-07-27 题目完成返回修复：`TutorHintScreen` 在“我会了，完成本题”后只显示完成消息，完整解答的“返回首页”也仅 `pop()` 一层；拍题链路有多个中间页时不能回学习桌。完成状态现在展示“返回学习桌”，并与完整解答共用 `Navigator.popUntil(route.isFirst)` 返回根学习桌，不修改 Attempt、Session 或 MistakeRecord 写入。新增“完成题目后返回学习桌” Widget 回归，Flutter `45` 项/Analyze 和 release APK 构建通过；安装时 Nova 9 未保持 ADB 连接，待重新连接后覆盖安装。
- 2026-07-27 复习 closeout 与教材范围解题修复：孩子端“还没完全会，加入复习”此前未确认服务端是否实际创建复习事实，成功后也停留在讲解页。现在客户端只有在已确认 `worked/blank` 作答且 `mistake-closeout` 返回 `mistake` 后才视为成功，并立即回学习桌；未确认题目或作答状态会显示可操作提示。Tutor 不再以旧页级文字片段作为完整解答依据：服务端从当前孩子全部已批准知识图谱选择可靠匹配点，向 NewAPI 仅传该点的标题、目标、先修范围和来源页；没有匹配点时完整解答返回 `409`，不会外发给 Provider。API Tutor/NewAPI 定向 `22` 项、Flutter 全量 `48` 项、Flutter Analyze、Mypy 和相关 Ruff 已通过；API 全量非集成套件在本机两次于约 `72%` 后无结果结束，未计为通过。尚未部署 Ubuntu 或安装 Nova 9，真实教材匹配质量和设备验证仍待执行。

## 2026-07-23 PLAN-0018 本地完成记录

- 结果：本地实现已满足“原页视觉 → 页级多模态理解 → 整本知识图谱 → 家长批准 → 错题/知识点任务 → 孩子原页”的代码验收；本机开发 PostgreSQL 已从 `0023` 前滚至 `0025` 并通过实际表结构测试。Ubuntu 未部署。
- 验证：API 非集成 188 项、教材/Provider/推荐定向 31 项、迁移表结构 1 项、Mypy 56 source files、相关 Ruff/格式通过；Web 20 项、Lint、类型、格式和 Next production build 通过；Flutter 43 项、Analyze 和格式通过；OpenAPI `0.11.0` 共 51 paths/81 refs 闭合，6 个 JSON Schema 可解析。
- 未执行：真实 118 页教材/NewAPI 多模态调用、全书知识点人工质量评分、token/费用基线、浏览器 E2E、iPad/Nova 9 原页查看与弱网回归、教材个人信息自动检测和依赖/镜像安全扫描。
- 剩余风险：真实教材可能超出模型上下文或产生章节合并偏差；当前用家长“无个人信息”声明阻断教材批注风险，自动门禁由 TODO-213 跟踪；Compose 本机缺少被忽略的 `infra/compose/.env`，本轮只更新配置未完整展开或启动。
- 回滚：停止 `curriculum-analysis-worker`，回退匹配 API/Web/App 并保留 `0025` 新表、私有原件/预览和既有审批事实；不得恢复旧文本规则抽题。

## 历史任务记录

- [x] 新增孩子绑定的即时拍题会话 API，并覆盖内存/PostgreSQL 幂等、事务和反向越权。
- [x] Flutter 自动取得会话，完成流式上传、视觉任务轮询、错误/超时兜底和人工确认；旧预签名传输仅作为历史实现事实保留。
- [x] 按 ADR-0018 将图片传输收敛为 App 携带 Session 只上传到 API，API 有界流式校验并写入内部私有 MinIO；生产 Flutter 删除预签名 URL/确认流程。
- [x] 本地 Compose 不再向宿主/LAN 暴露 `9000`，示例配置删除 `OBJECT_STORAGE_PUBLIC_ENDPOINT_URL`/`MINIO_API_PORT`；OpenAPI 不返回 `upload_url` 并合并为单一上传操作。
- [x] API/OpenAPI/Flutter 单元、格式、Lint、类型和 PostgreSQL/MinIO 集成门槛通过。
- [x] Ubuntu API/Web/worker 已部署，健康版本 `0.10.0`、迁移 `0024_intelligent_recommendations`；教材解析 worker 已稳定运行，Nova 9 既有登录验证保持有效。
- [x] 使用 synthetic 大图在 Ubuntu 完成真实 NewAPI `upload → analysis → extraction → verify → tutor`，确认有界压缩、人工确认、TutorTurn 持久化和派生对象删除。
- [x] PostgreSQL/MinIO 备份已生成并在隔离 PostgreSQL 16.10 容器恢复校验；数据生命周期 worker 已部署。
- [ ] 由 iPad 验证 `capture-session → API streaming upload → image-analysis（自动四态候选）→ 人工确认 → 状态分支提示 → 完整解答`；现有预签名直传不再作为最终发布验收。
- [x] 修复 L1/L2 题意无关问题：云端生成受约束提示，L2 基于实际 L1 递进，同时关系题固定回归且两级不泄露答案（本地代码/自动化通过，真实 Provider 待验收）。
- [x] 刚形成但尚未到期的开放错题可以从“复习错题”入口提前复习，不再显示成“没有错题”（Flutter 回归通过，真机待验收）。
- [x] 任务推荐遍历已发布 PDF 和全部开放错题，生成带具体教材题、页码、知识点、题量、预计时间和未来日期的待审批计划；批准后孩子端显示同样内容（本地代码/自动化通过，真实 PDF/Provider 待验收）。

## 2026-07-23 PLAN-0017 整改记录

- Tutor：L1/L2 改为 NewAPI 文本生成，L2 必须绑定持久化 L1；增加答案泄露、重复、结构递进和题意相关校验。针对“多人同时经历同一段时间”建立本地安全回退与固定回归，题意无关的“增加/减少/平均分”提示会被拒绝。
- 复习：Flutter 先请求到期错题；若为空则请求全部开放错题，并明确提示“可提前复习”，重新作答和 ReviewAttempt 路径保持不变。
- 推荐：API 本地遍历已发布 Snapshot 的全部 CurriculumChunk 和全部开放错题，统计薄弱知识点频次、抽取具体教材题并排序；只把最多 30 个候选及不透明来源键交给 NewAPI。计划引用未知来源、忽略已有错题/教材、未把到期错题排到当天或超过每日 3 项时整体失败。
- 下发：新增 `0024_intelligent_recommendations` 和 OpenAPI `0.10.0`；推荐/Task 保存来源类型、原始具体题、教材页码、知识点、预计时长和未来日期。Web 审核页展示同样依据，Flutter 今日任务显示当天全部任务而非第一条。
- 本地验证：API 178 项非集成测试通过；本轮 Tutor/推荐定向 30 项通过；Mypy、相关 Ruff、OpenAPI/JSON Schema、Alembic offline SQL、5-case Tutor eval 通过；Web 16 项测试、Lint、类型、格式和 production build 通过；Flutter 全量 40 项测试与 analyze 通过。
- 已执行：使用 `rsync` 同步最新工作区，排除 `.env`、`.git` 和本地缓存；Ubuntu Compose 以 `DOCKER_BUILDKIT=0` 重建，保留 PostgreSQL/MinIO/Redis 数据卷；API/Web `/healthz` 通过，API 返回 `0.10.0`，Alembic current/head 均为 `0024_intelligent_recommendations`，API/Web/四个 worker 重启次数均为 0。
- 未执行：真实 NewAPI L1/L2/推荐、真实已上传 PDF 选章/抽题、iPad 立即复习与多任务页面、浏览器 E2E，以及 planner 的 token/延迟/成本完整审计。回滚需保持 API/Web/App/迁移成对；`0024` 新列不删除既有任务/推荐事实。

## 2026-07-23 本轮实现记录

- [x] M1：新增 `/mistake-closeout`，PostgreSQL 事务内校验活动 StudySession、已确认 VerifiedQuestion 和 `worked/blank` AttemptEvidence，完成会话并幂等创建 MistakeRecord/ReviewSchedule。
- [x] M2：复习接口返回实际题目；Flutter 提交作答文本与确认标记；服务端写入 ReviewAttempt，并按 `review-policy.v2` 与 1/3/7/14/30 天间隔确定结果，客户端不再直接决定掌握状态。
- [x] M3：教材上传合同收缩为 PDF-only；新增 `0021`～`0023`、pdfplumber 解析 worker、扫描 PDF `needs_ocr`、危险/加密文件隔离、页级 CurriculumChunk 和已发布 Snapshot 来源检索。
- [x] M4：TutorTurn 保存教材来源、L1/L2 目标、递进来源、孩子动作和答案暴露级别；Flutter 展示下一步可执行动作。
- [x] 自动验证：API 全量测试在本机 PostgreSQL/MinIO 前滚到 0023 后通过；Ruff/Mypy/compileall、PDF parser synthetic、Flutter analyze/test、Web test/lint/typecheck/format/build 通过。
- [x] 远端/设备验证：使用 rsync 同步并在 Ubuntu 重建 Compose，迁移头为 `0024_intelligent_recommendations`，API/Web 健康检查通过，ImageAnalysis/DataLifecycle/MaterialParse worker 修复后稳定运行；iPad mini 6 已安装 Xcode 自动签名调试包并成功启动。
- [ ] 未执行：真实 PDF/扫描 PDF 上传、iPad/Nova 9 相机闭环、浏览器 E2E、固定 Tutor/教材 eval、四设备弱网/权限回归、SBOM/镜像扫描。Ubuntu 已完成前滚与重建；剩余风险与回滚见 `RUNBOOK.md` 和 ADR-0021。

## 兼容、回滚与风险

## 2026-07-23 教材解析与客户端收口修复

- [x] 将教材单文件上限统一为 `50 MiB`（`52,428,800` 字节），修复原先后端/解析器使用十进制 `50,000,000` 字节而使 47.8 MiB 文件被 `413` 拒绝的问题；Web 在选择与失败响应中均显示同一精确上限。
- [x] 修复教材解析 worker 错用仅允许 `captures/`、最多 8 MB 的对象读取接口；worker 现仅能以受限 `curriculum/` 前缀和同一 50 MiB 上限读取私有 PDF，解析页块可进入审核发布和具体题推荐。
- [x] 家长工作台增加教材删除：删除一个快照时级联移除其私有 PDF、解析任务/页块和失效推荐引用；删除请求有会话、CSRF、家庭/孩子授权和幂等保护。旧“已发布但未解析正文”的范围会明确标记，需删除并重新上传实际 PDF 才能用于具体题推荐。
- [x] 孩子端完整解答出现后将第二操作改为“返回首页”，不再继续显示“查看完整解答”。
- [x] 回归与部署：教材 API/私有对象读取/PDF parser `27` 项、API 全量 `181` 项/Mypy、Web `17` 项/Lint/类型/格式/production build、Flutter 全量 `41` 项与 analyze 通过；已安全 rsync 到 Ubuntu 并重建。API/Web/三类 worker/数据服务均 healthy，运行容器确认 `curriculum_limit=52428800`、`read_document=True` 和删除 OpenAPI 路径存在；真实家庭 PDF 上传/解析/发布/推荐仍待用户现场验收。

## 2026-07-23 家长教材阅读与推荐详情

- [x] 教材快照列表不再直接渲染页级全文；新增仅限家长、同家庭/孩子授权的分页解析阅读接口，返回页码、标题、正文和置信度，不返回原始 PDF、对象键或 MinIO URL。
- [x] Web 教材审核改为摘要卡片后显式打开分页阅读器；长文本按段落排版、可切换页码，草稿和已发布快照均可在发布前后审阅。
- [x] 推荐列表改为摘要，点击“查看计划”才展示每道题、教材页码/错题来源、推荐理由及批准/忽略操作，避免在工作台堆叠完整题干。
- [x] PDF 解析器仅过滤 `pdfminer.pdfinterp` 已知的灰度图形操作数兼容警告（`/P0` 等），保留其他警告与所有真实解析失败状态，避免 worker 日志被无关噪声淹没。
- [x] 本地验证：API 定向 14 项与完整非集成 183 项、Mypy/Ruff；Web 18 项测试、Lint、类型、格式和 production build；OpenAPI YAML 解析与差异空白检查通过。
- [ ] 未执行：本批可读性改动尚未部署 Ubuntu，真实家庭 PDF 的阅读版式和浏览器 E2E 待部署后现场验收。

- Ubuntu API/Web/worker 已切换到 ADR-0018 的单一流式合同；已部署 Flutter 仍需在设备可用时重新验收。正式 OpenAPI 不再暴露预签名入口，旧实现仅保留为代码级受控回滚材料。
- 回滚应用/API 不删除已创建任务、会话、Capture 或确认题目；新链路异常时只允许整体回滚匹配的 API/App，并在隔离受信 LAN 临时恢复旧 `9000`/配置，不得公开 Bucket 或下发密钥。
- ImageAnalysis 仍依赖用户确认后的脱敏副本和单一 NewAPI Provider；超时/失败允许手工填写，不把未确认提取作为 Tutor 事实。

## 本轮全仓收口记录

- `2026-07-23`：项目 Owner 将教材首版范围进一步收窄为“只支持 PDF 上传，DOCX/PPT 暂不支持”。PLAN-0016/ADR-0021 现要求 Web/OpenAPI/API 同步收缩 allowlist，Word/PPT/Excel 返回稳定不支持错误；文本 PDF 进入隔离解析，扫描 PDF 进入待 OCR。既有非 PDF 对象只保留用于兼容/删除，不解析、不发布、不进入 Tutor/推荐。本轮仍仅修改规划文档，当前运行时代码尚未执行合同收缩。

- `2026-07-23`：项目 Owner 指出三项尚不可用能力：拍题记录未进入真实复习、上传教材未解析并用于讲解/推荐、Tutor 第 1/2 级提示过浅。代码审计确认：Flutter 完成拍题会话时未创建 MistakeRecord，复习页只提交客户端“会了/不会”而没有 Question/ReviewAttempt；教材路由只写入 MinIO 和占位草稿；多数 L1/L2 模板没有稳定递进语义。已建立 PLAN-0016、TODO-020 和 Proposed ADR-0021，明确原子错题 closeout、证据化复习、隔离教材解析/审核发布、两类教材消费和 Tutor Hint 新版本；教材格式随后由上一条记录进一步收窄为 PDF-only。本轮仅完成规划，没有修改运行时代码。

- `2026-07-20`：OpenAPI/API 前滚为 `0.9.0`，新增 `0020_answer_evidence`。视觉提取现在必须返回四态候选、置信度和可见作答步骤；确认后写入 VerifiedQuestion，Tutor 不再信任客户端临时状态。`worked/blank` 在第三级通过已配置 NewAPI 仅传已确认文字生成完整步骤、答案和验算并持久化；`unclear/answer_area_missing` 明确要求确认或补拍。Flutter 去除硬编码 `2/4` 和练习页二次手选，家长 Web 增加 Household-scoped 逐题详情。Ubuntu 已在备份后 rsync、重建并健康前滚到 `0020`；合成题现场返回正确 3 步、答案 17 只和验算。iPad 已安装 profile App 并完成账号/档案/任务 200 启动 smoke，实际相机闭环仍待人工操作。

- `0013_tutor_turn_persistence`～`0015_child_data_export` 已部署：Tutor 只读取服务端 VerifiedQuestion，TutorTurn 追加写；会话完成/复习和周报可追溯；导出为 24 小时不可变 JSON 快照并随孩子删除级联。
- Flutter 使用真实任务与活动会话，确认题目后进入真实 Tutor；离线 Attempt 与任务终态队列使用 SQLite 并按服务端/账号隔离。同一天重复拍题使用新的流程幂等 nonce，避免复用已完成会话。
- 家长 Web 可创建当天数学任务、查看周报摘要、下载孩子数据导出；API 删除孩子档案会按依赖顺序清理学习、Capture/OCR、视觉、VerifiedQuestion、Tutor 和导出数据。
- 自动验证：API 162 项非集成测试、Ruff/Mypy；Web 14 项测试/类型/Lint/生产构建；Flutter 39 项测试/analyze、Android release APK 和 iOS release 无签名构建（以 `TESTING.md` 最新记录为准）。
- 未执行：用户当前不在实体设备旁，Nova 9/iPad 的最终相机、权限拒绝/允许、弱网、横竖屏和重启人工回归保留。自动视觉检测器仍未实现，当前外发门禁依赖规则信号、手动涂抹和用户确认，不得宣传为绝对匿名。
- `2026-07-17` 架构变更：项目 Owner 接受 ADR-0018，要求 App 不再直连 MinIO；随后完成 API/Flutter/契约/Compose 迁移，关闭 Compose 的 MinIO `9000` 宿主入口。
- `2026-07-18` PLAN-0012 远端收口：Ubuntu API/Web/两个 worker 已重建并运行，迁移到 `0016_child_account_uniqueness`；旧 `.env` 中残留的公开 MinIO 地址已清除，worker 使用 `http://minio:9000` 内部地址。synthetic 请求已到达 NewAPI，但 Provider 返回 HTTP `402`，属于额度/余额配置问题，不是上传链路失败。
- `2026-07-18` 并行规划说明：项目 Owner 要求 Web 将孩子档案/账号合并为一个创建与管理体验，并支持首页当前孩子选择；PLAN-0013 已完成 API/Web 首版、唯一约束迁移和 Ubuntu 部署，浏览器 E2E 与双孩子实体验收仍待执行。
- `2026-07-18` 产品主线规划：项目 Owner 批准“教材范围 → 错题讲解 → 错题沉淀 → 到期复习 → 今日任务”方向及详细建议，已建立 Accepted ADR-0020、PLAN-0014 和 TODO-016～019。随后先实现错题/复习最小闭环：`MistakeRecord`/`ReviewSchedule`、`0017`、到期查询、确定性复习、导出覆盖和 Web/Flutter 调用，并部署 Ubuntu；教材、作答四态和三入口仍待后续阶段。
- `2026-07-18` 错题讲解规划补充：Owner 确认拍题会包含孩子解答，答题区确认空白表示“没有思路”并允许从头讲解。ADR-0020/PLAN-0014 已改为四态作答 Schema：`worked/blank/unclear/answer_area_missing`；空白必须用户确认，未拍入/不清不得自动当空白。当前 `MistakeRecord` 只接受服务端已确认 `VerifiedQuestion` 与会话引用，未伪造四态作答证据。
- `2026-07-18` PLAN-0012 实现与部署：新增 Session 鉴权的单一 API 原始流上传，服务端用 boto3 S3 multipart 有界写入私有 MinIO，增量校验大小/SHA-256，完成后重新读取并完整解码图片，失败清理 multipart/对象；API/Flutter/契约/Compose 相关回归通过，Ubuntu 已成对部署。未完成：Nova 9/iPad 新链路人工验收、并发/断连现场压测和 Provider 额度恢复后的真实识别。
- `2026-07-18` PLAN-0014 最小闭环：新增错题创建/列表/到期过滤/复习提交 API，使用 `0017_mistake_review` 和 PostgreSQL 事实源，连续三次正确关闭错题，非正确结果按确定性策略回退；导出包含错题/复习计划，Web 显示到期错题，Flutter 客户端可读取并提交复习结果。API 159 项非集成、Web 11 项、Flutter 29 项回归通过，Ubuntu 已前滚到 `0017`。
- `2026-07-18` PLAN-0014 纵向实现：新增 `0018_curriculum_answer_recommendations`，教材授权 manifest 导入/草稿/家长发布快照、Attempt 四态与 Tutor 分支、Flutter 数学三入口、任务推荐审批及批准后 Task 创建；新增 API/Web/Flutter 回归。真实 PDF 二进制解析、Provider 识别额度恢复后的联调、浏览器 E2E 和设备回归保留为最后验收。
- `2026-07-18` Ubuntu 部署收口：使用 rsync 同步 API/Web/迁移/契约/Compose，修正 Alembic revision 长度后将远端 PostgreSQL 前滚到 `0018_curriculum_recommendations`；API、Web、两个 worker、PostgreSQL、MinIO、Redis 均 healthy，OpenAPI 已暴露教材/推荐新路径，远端 `.env` 未覆盖。
- `2026-07-18` 教材上传增量：新增 `0019_curriculum_documents`、`python-multipart` 和多文档 multipart API；Web 支持多选 PDF/DOC/DOCX/PPT/PPTX/XLS/XLSX，逐文件流式写入私有 MinIO 并生成 `uploaded` 草稿。Ubuntu 已备份后前滚、重建并验证健康和 OpenAPI 路径；真实文档解析仍待完成。
- `2026-07-20` 教材上传修复：浏览器在非安全上下文中不提供 `crypto.randomUUID()`，导致选择教材后点击上传立即抛出 TypeError；已改用 `crypto.getRandomValues` 并保留无 Web Crypto 时的随机回退，Web 12 项测试通过，Ubuntu Web 已重建并健康。
- `2026-07-20` 教材上传 CSRF 修复：教材页面写请求补齐登录 Cookie 对应的 `X-CSRF-Token`，覆盖手工导入、文档上传、发布和任务推荐；新增 CSRF Cookie/header 回归，Web 14 项测试通过，待 Ubuntu Web 重建后复测上传。
- `2026-07-20` iPhone 11 真机调试：Xcode 26.6/CoreDevice 识别 iOS 17.5.1 设备，开发者模式和 DDI 服务已启用；Flutter Debug App 已安装启动。真机发现登录卡片在紧凑窗口发生 58px 底部溢出，已改为可滚动布局，新增回归后 Flutter 30 项测试通过并热重载验证。
- `2026-07-20` iPhone 局域网连接修复：确认 Mac 可访问 Ubuntu `3000/8000` 且 API 健康，但 iPhone 请求未到达服务端；定位到 Runner 缺少 `NSLocalNetworkUsageDescription` 与 iOS 17 局域网 IP 的 ATS 声明。已加入用途说明及 `NSAllowsLocalNetworking`，校验编译产物并重新安装真机；等待用户允许系统本地网络权限后复测登录。
- `2026-07-20` iPhone 局域网诊断：经用户授权卸载 `com.example.studyChild` 清除本地权限/会话状态后重新安装，并在登录页增加 `/healthz` 检测、手动重试和不含凭据的安全网络错误信息；Flutter 真机返回 `errno 65: No route to host`，Ubuntu API 没有收到请求。iPhone Safari 对 Ubuntu `192.168.1.4:8000` 以及同 Wi-Fi 网段 Mac `192.168.100.158:18080` 的请求也均未到达，当前阻塞定位为 iPhone 本地网络权限状态、VPN/过滤器或 Wi-Fi 客户端隔离，不是 Flutter HTTP、账号或 API 故障。临时 HTTP 端口和 RVI 诊断接口已关闭。
- `2026-07-20` iPad mini 6 真机回归：Flutter 识别 `00008110-0011356E0E41801E`，完成构建、安装、启动和热重启；启动期间 API 收到来自局域网 `192.168.1.100` 的 `/healthz` 并返回 200，证明同一客户端版本在 iPad 网络链路可用。登录、相机/相册权限及拍题人工确认仍待设备端点击验收。
- `2026-07-20` 拍题失败恢复优化：识别失败页保留已确认脱敏照片，新增“重新识别当前照片”和“重新拍题”；重新识别使用新的幂等键创建新 OCR/ImageAnalysis 任务，不复用失败任务；同时修复从拍题返回学习桌时把异步刷新误放入 `setState` 的 iPad 真机运行时错误。Flutter 33 项测试/analyze 通过，已热重启到 iPad。
- `2026-07-20` 拍题体验优化：脱敏完成后立即进入独立上传进度页，上传期间保持题目照片和转圈状态，不再回到拍题页；成功后自动进入题目确认，失败可在原页重新上传或返回拍题。确认题目改为大尺寸多行编辑框，可在框内上下拖动查看长文本。新增 3 项 Flutter Widget 与安全会话存储回归，Flutter 共 37 项通过。
- `2026-07-20` 孩子端账号体验优化：登录后隐藏服务端切换入口，学习桌顶部增加账号入口；账号页支持安全保存的会话切换、添加账号和注销当前账号，不保存密码，服务端地址仍只在登录流程中配置。已在 iPad 热重启验证启动无运行时异常。
- `2026-07-20` 修复确认题目点击后可能一直卡住：Capture HTTP 请求增加 8 秒连接与 20 秒响应上限，确认流程补齐非业务异常兜底并恢复按钮状态，按钮在请求期间显示“正在确认题目……”。Flutter 37 项测试/analyze 继续通过。
- `2026-07-20` 根因修复：Flutter `HttpClientRequest.write()` 默认 Latin-1，中文题目序列化时抛出非法字符异常；Capture、登录和改密 JSON 请求统一改为 UTF-8 字节写入，并用中文题目回归验证确认请求。
- `2026-07-20` 修复同一照片重试失败：首次 ImageAnalysis 失败后服务端会清理派生对象，重试不再复用原 Capture 上传幂等键，而是使用新的上传键创建新 Capture/对象/识别任务；错误提示不再把 Provider/配置失败误报为照片不清晰。Ubuntu 数据库确认原问题为旧重试任务的 `image_analysis_failed`，首个任务为 `provider_http_402`。
- `2026-07-20` 修复脱敏后进入上传页提示照片大小不合规：相机 JPEG 经不可逆 PNG 重编码后可能膨胀超过 API 的 8 MB 上限；PrivacySanitizer 现在按 1800/1500/1200/960/720 像素上限逐级等比缩放、同步换算遮挡区域并重新编码，上传副本控制在 7.5 MB 内，仍超限时要求用户只裁剪题目区域。Flutter 38 项测试/analyze 通过。
- `2026-07-20` 修复真机练习页身份和提示链路：标题改用当前安全会话对应的登录用户名，不再使用原型默认“小禾”；真实题目进入练习页自动请求第一级 Tutor 提示，零成本本地策略按“减少/剩余、比较、平均分组、求总量、分数”等已确认题目结构生成分级提示。视觉确认形成的 `VerifiedQuestion` 可在 Capture `needs_correction` 状态进入 Tutor，不再被旧 OCR `corrected` 门禁误拒绝为 409；Flutter 使用提示专属错误信息。API 162 项、Flutter 39 项及静态检查通过，Ubuntu API 已重建健康，iPad 已热重启。
- `2026-07-22` 家长 Web 按已选“方案 1”完成后台化重构：统一固定分组导航、当前孩子上下文、今日优先事项、本周趋势、可展开逐题详情、孩子/账号聚合管理和教材/推荐工作区；统计继续读取 Household-scoped API，没有写入演示数据或认证旁路。新增 Phosphor Icons `2.1.10` 与 Recharts `3.10.0`（MIT、精确锁定），14 项 Web 单测、Lint、类型和 Next 生产构建通过；使用独立合成 API 在真实登录流程中完成 1280 桌面与 736 窄屏视觉/交互 QA，结果记录于 `design-qa.md`。Web 已通过 rsync 同步 Ubuntu、使用锁定 Node 24.18/pnpm 11.7 重建并健康启动；Nova 9 安装因本轮 ADB 本机访问授权被拒绝未执行，release APK 已就绪。
- `2026-07-23` 修正家长后台信息架构：孩子切换移到所有页面共用的顶栏，下拉选择通过 `?child=` 保持工作台、教材和孩子管理作用域；侧栏删除与工作台卡片重复的今日任务、待复习、最近学习和学习周报，只保留三个顶层目的地。教材链路审计确认已发布小节仅用于生成带 `snapshot_id`、小节标题和学习目标的家长审批任务推荐，Tutor 尚未消费教材正文；上传 PDF/Word/PPT/Excel 仍只是私有存储和待解析草稿。为避免误用，待解析文档现在不能发布，Web 明确显示“待解析 · 尚未使用”。Web 16 项测试、Lint、类型、格式和生产构建及 API 教材定向 5 项测试通过；同尺寸参考图/实现图浏览器对照记录于 `design-qa.md`。相关 Web/API/worker 已 rsync 到 Ubuntu 并重建，API `0.9.0`、Web 和两个 worker 运行正常，API/Web healthcheck 均通过。

---

# 历史任务：TASK-0008 孩子档案 PostgreSQL 持久化

## 当前任务元数据

- 状态：`COMPLETE（代码、迁移与 Ubuntu 持久化验收完成；华为登录生命周期继续由 PLAN-0008 跟踪）`
- 类型：`FEATURE / DATA MIGRATION`
- 优先级：`P0`
- Owner：Codex（执行）；项目 Owner（用户，明确要求生产标准持久化）
- 创建/更新：`2026-07-17`
- 关联：`PLAN-0009`、`ADR-0005`、`ADR-0009`、`ADR-0017`

## 当前目标与验收

将孩子档案和设备登记从进程内 synthetic 仓储切换到 PostgreSQL 业务事实源，保持现有 OpenAPI 字段与 Household/角色授权不变。新增/编辑/删除必须事务化且支持幂等重放；孩子账号与档案的 Household 绑定由数据库约束保护；Compose 重启后档案仍存在。

- [x] 新增可前滚的 Profile/Device 数据库迁移，并兼容现有账号绑定和旧合成默认档案。
- [x] 新增 PostgreSQL ProfileRepository，覆盖读取、新增、编辑、删除、设备登记、审计、并发与幂等冲突。
- [x] Compose 默认启用 PostgreSQL ProfileRepository；内存仓储只保留给 unit/local synthetic 测试。
- [x] API 单元/集成、迁移往返、OpenAPI/Web/Flutter 兼容检查通过。
- [x] Ubuntu 应用迁移并重启后验证档案持久化；不输出凭据或真实儿童数据。

## 兼容、迁移与回滚

- OpenAPI 请求/响应保持兼容，不要求 Web 或 Flutter 修改字段。
- 迁移优先前向修复；部署前记录 Alembic 版本和表计数。不得为回滚删除现有档案、账号、学习记录或图片。
- 旧内存档案无法从进程外可靠读取；迁移使用既有确定性默认档案及已持久化孩子账号绑定生成兼容行，部署后以 PostgreSQL 为唯一事实源。

## 完成记录

- `0012_profile_persistence` 建立 `child_profiles`/`devices`、Household 查询索引、字段约束，以及 `accounts(child_id, household_id)` 到档案的级联复合外键；旧确定性档案和已持久化孩子账号绑定被前向兼容。
- PostgreSQL 仓储使用事务、通用幂等表和稳定审计事件实现档案/设备 CRUD；并发同键创建只产生一个资源，跨 Household 返回不可枚举结果，删除档案级联孩子账号和会话。
- 本机 127 项 API 单元、21 项 PostgreSQL/MinIO 集成、`0012 → 0011 → 0012` 往返、Ruff、Mypy 40 源文件、OpenAPI、Web 6 项测试/类型/构建、Flutter analyze/17 项测试通过。
- Ubuntu 部署前生成权限 600 的 PostgreSQL 压缩备份；远端从 `0011` 前滚 `0012`，API/PostgreSQL/Web healthy，孤儿孩子账号绑定为 0。临时 synthetic 档案经 API 重启后可重新读取，随后档案、幂等和审计测试记录已清理，正式档案计数恢复为 1。
- 修复 PostgreSQL 重复孩子用户名触发未处理 `IntegrityError` 的缺陷：只识别账号 Household/用户名唯一约束并转换为领域冲突，API 返回 409，Web 提供可操作提示；本机 128 项非集成、22 项集成、Web 7 项测试及生产构建通过。Ubuntu API/Web 重建后，对现有用户名的只回滚 smoke 返回 `duplicate_conflict=ok`，所有基础容器保持运行且健康，未修改现有账号。
- 修复 Flutter 把首次改密门禁误显示为“API 尚未连接”的缺陷：登录响应和 `/auth/me` 会话恢复均识别 `must_change_password`，新增孩子首次改密、Token 轮换和安全存储 UI；API 将孩子档案列表/详情限制到账号绑定档案。本机 API 129 项非集成/22 项集成、Flutter analyze/21 项测试及 176 MB Debug APK 通过；Ubuntu API 已重建并健康，Nova 9 实机完成改密与档案读取，显示“小汤圆”学习桌和“在线”。手机竖屏标题溢出亦已修复并覆盖安装验证。
- 华为 Nova 9 已重新由 ADB 稳定识别，App 冷启动到登录页，服务端地址正确且手机可达 API，日志无 Flutter 崩溃；真实密码登录和档案读取需用户在设备输入凭据，继续由 `PLAN-0008` 跟踪。

---

# 历史任务：TASK-0007 认证面收敛与 Flutter 服务端地址配置

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
- `2026-07-17`：家长 Web 增加孩子档案新增、编辑和删除入口；修复 POST/PATCH 代理遗漏 `application/json` 导致 FastAPI 返回 422，并增加代理 Header 回归测试。Web 镜像已部署到 Ubuntu，API/Web 容器及健康端点正常。Profile 仍使用进程内 synthetic 仓储，API 重启后改动不会保留，不把本轮描述为 PostgreSQL 持久化完成。
- 下一步：继续执行 `PLAN-0008` 的远端人工确认、Cookie/CSRF、iPad 会话生命周期和备份恢复验收；真实视觉检测器和固定视觉评测仍作为后续实现项。
