# Changelog

- 2026-09-03：家长后台完成首轮视觉改版。侧栏升级为深石墨工作导航，顶部当前孩子/服务/账号信息和主内容区重新分层；学习记录页采用紧凑筛选带、记录汇总和独立空状态，修复“时间范围”文字被裁切及无记录时大面积空白。桌面 `1280×800` 与手机 `390×844` 登录态布局断言、完整 Chromium E2E、Web 37 项单元测试、格式、Lint、类型和生产构建通过。本轮仅提供本地 UI 预览，未提交或部署。

- 2026-08-30：简化家长首页，移除“语文技能报告”卡片和对应请求；保留后端 `skill-report` 接口以维持兼容。今日关注只显示上海自然日当天到期的开放错题，早于当天的逾期项目仍保留在学习记录/复习入口但不再占据首页。Web 日期回归、Vitest、格式、Lint、类型和生产构建通过；Ubuntu Web 已完成备份、legacy builder 构建、容器重建和健康核验。用户随后确认两个孩子，已依据 `/home/syin/study-backups/20260830T004506Z` 清理全部学习历史与已登记拍题对象；账号、孩子档案、教材/审核事实、设备设置和审计记录保留，API/Web/worker 健康。

- 2026-08-29/30：发布 `v0.17.1`（`e44a2b1`），修复语文“古诗抽查”把《剪窗花》等儿歌、童谣或现代韵文作为古诗的问题。Provider 分类仅作候选，服务端以 `classical-poem-catalog.v2` 验证标题、连续题干/答案和全部可见选项，并在发布、读取和提交处失败关闭。`0037` 前向退役 157 道错误题，`0038` 再替换 42 个童谣干扰项，不删除 Attempt、Review、教材或审核事实。Flutter 每次打开古诗抽查前重新读取当前题库。Ubuntu 已部署 `0.17.1/0038`；Nova 9 覆盖安装后 12 轮覆盖全部六首且未提交作答。GitHub `quality` 和 Android Actions 成功，Release 发布 3 个 ABI APK、`SHA256SUMS` 与 `BUILD-INFO.txt`。

- 2026-08-25：修复并部署语文教材分析的三类 Provider 兼容失败。`chinese-curriculum-page-visual.v3` 固定观察/练习字段并只丢弃不满足严格模型的可选观察；四页请求遇到 HTTP 413 时在同一 Provider 内递归二分，单页失败仍可见；`chinese-curriculum-book-consolidation.v3` 固定整书/章节/知识点字段并禁止已出现的替代字段。数学路径、固定 Schema、页码/练习引用和家长批准门禁均未放宽。运维显式重排既有作业后真实 118 页语文教材完成解析，初始状态为 `needs_review`，含 10 个章节、12 个 draft 知识点和 38 条古诗边界证据；未读取或保存 Provider 原始响应/教材正文。Ubuntu 备份隔离恢复、API/Web/worker、`0036`、NewAPI 路由、私有 MinIO 和运行源码通过。2026-08-26 最终复核显示外部审核已将知识图谱和 12 个知识点更新为 `approved`；费用、正式版权/教研、浏览器和设备验收仍未完成。

- 2026-08-24：根据 12 GB/4 核与 12 GB/8 核 Ubuntu 的本地 Qwen 视觉失败结果，将 `STUDY_LOCAL_MODEL_ENABLED` 恢复为 `false` 并停止本地模型容器，模型缓存保留供后续重新选型。API 和两个 AI worker 已显式恢复现有 NewAPI 云端路由，不含儿童数据的 synthetic 数学文本 Schema smoke 3.591 秒通过；完整测试结果和适用边界记录到 README 与 `docs/local-qwen-evaluation-report-2026-08-24.md`。

- 2026-08-24：在 12 GB/4 核 Ubuntu 自用服务器启用 Qwen3.5-4B Q4_K_M 本地路由。发布前备份 `/home/syin/study-backups/20260824T024445Z` 已隔离恢复验证（39 张 PostgreSQL public 表、353 个 MinIO 文件）；模型缓存持久化且支持断点续传，模型/API/Web/四个 worker、`0036`、health/models、`local_qwen` 运行时选择、文本 JSON smoke 和私有端口通过。模型初始空闲约 3.8 GiB，长视觉评测保留 prompt cache 后约 6.4 GiB，宿主仍约 6.5 GiB available。本地失败受 600 秒、2048 输出 token、单次尝试约束且不回退云端。`question-extraction.v1` synthetic 大图在 600 秒内输出不收敛，视觉质量门禁未通过；未使用真实儿童数据、PDF、浏览器账号或设备。

- 2026-08-23：新增 `ADR-0028` 可切换本地 AI 路由。Compose 增加内部 llama.cpp `local-model` 服务，默认配置 Qwen3.5-4B Q4_K_M GGUF/视觉 projector 和持久模型缓存；`STUDY_LOCAL_MODEL_ENABLED=true` 时 API、ImageAnalysis worker、CurriculumAnalysis worker 的所有当前 NewAPI-compatible 请求只走本地，关闭时回到现有 NewAPI 配置且不自动跨 Provider 回退。Qwen 本地结构化请求关闭 reasoning；本机 Linux ARM64 已完成镜像/权重加载和 synthetic text/vision/schema smoke，目标硬件质量/延迟、真实 Provider/PDF/设备验收仍未执行。

- 2026-08-23：从未提交的本地工作区部署 Ubuntu 自用 Compose `0.17.0`/`0036_task_session_progress`。备份 `/home/syin/study-backups/20260823T030248Z` 已隔离恢复校验（39 张 PostgreSQL public 表、359 个 MinIO 文件）；API/Web/worker、OpenAPI、容器源码、私有 MinIO 端口和局域网健康检查均通过。随后已提交、推送并创建 `v0.17.0`；真实 Provider/PDF、Ubuntu 真实账号浏览器和真机 E2E 仍待执行。

- 2026-08-23（未重新部署）：数学任务离线流程继续收口。确认作答、任务完成、复习收口和跳过现在使用同一受范围隔离的 SQLite 结构化队列；联网后先批量同步 Attempt，再按原幂等键重放完成/跳过，队列不保存图片、答案原文或令牌。服务端拒绝同一任务的第二个活动会话及终态任务重复启动。Flutter 回归 `67 passed`，API 非集成 `239 passed`，PostgreSQL 集成 `30 passed`。本轮未连接手机或平板。

- 2026-08-23：继续收口数学和语文孩子端。数学今日任务用端侧 SQLite 保存当前题号，进程退出后可从同一服务端/家庭/孩子范围内的未完成题继续；已确认作答在断网时只保存结构化事件（不保存图片、答案或令牌），联网后按最多 50 条批次幂等同步，任务最终完成/跳过仍要求在线确认。语文首页固定为“古诗抽查”和“看图写话”两项，尚未审核教材时保留古诗入口并说明开放条件。Flutter `64 passed`；本轮未连接手机或平板。

- 2026-08-22：继续收口数学与语文可用闭环。数学孩子端恢复“今日任务”，每道任务题必须带指定题干，并按顺序把当前题干与教材来源带入拍题/确认页；多题任务在同一会话内逐题完成，中间题追加作答、最后一题关闭任务，空题明确阻断；“稍后再做”现在以幂等 `skipped` 结果记录会话并刷新任务队列。语文新增拼音、生字、词语、句子、阅读、背诵、表达、古诗八类 deterministic scorer golden 覆盖，并把正式原创内容门禁落实为 Owner 审核、审核时间和权利凭证摘要；待审核内容不会进入孩子题库。古诗抽查现在先均匀抽取一首诗，再从该诗的相邻句题目中抽题，避免长诗因题目更多而被偏抽。PostgreSQL 集成测试夹具改用随机 Household/真实 Parent Owner，完整集成矩阵 `29 passed`；API 非集成 `238 passed`；Flutter `58 passed`。本轮未连接手机或平板，真实 Provider、正式内容签核、Ubuntu 真实账号浏览器和设备 E2E 仍待执行。

- 2026-08-16：发布 `v0.16.0`（`dbaa9b0`）到 Ubuntu 自用 Compose。升级前备份 `/home/syin/study-backups/20260816T091344Z` 已隔离恢复为 38 张 PostgreSQL public 表和 353 个 MinIO 文件；API/OpenAPI `0.16.0`、Web、迁移 `0035_chinese_poem_skill`、四个 worker、picture-writing OpenAPI 路径和容器源码哈希均通过。MinIO 未发布宿主机端口。使用无人物、无文字的合成图完成一次真实 Provider 的 `picture-writing-guide.v1` Schema 冒烟，不包含儿童图片或 Provider 原始响应；Nova 9 已安装 `0.16.0 (2)` 并配置家庭 LAN 地址，WLAN 可达 Ubuntu 且健康检测无连接失败。重装后无登录会话，登录后相机/相册/权限 E2E 仍待执行。

- 2026-08-16：发布修复版 `v0.15.1` 到 Ubuntu 自用 Compose。前置备份 `/home/syin/study-backups/20260816T072837Z` 已隔离恢复验证（38 张 PostgreSQL public 表、353 个 MinIO 文件）；API `0.15.0`、Web、四个 worker、`0032_chinese_original_content_pack` 迁移和私有 MinIO 端口均已运行验证。首次 `v0.15.0` 发布暴露历史 Alembic version 列为 `varchar(32)`，长 revision 写入失败且事务回滚；`v0.15.1` 先前向扩展为 `varchar(64)` 后成功迁移。Nova 9 保留登录态升级后加载数学、语文、锁定英语及新增语文内容；未提交答案、未读取或导出学习记录。

- 2026-08-16：本地 API/OpenAPI 前移至 `0.15.0`，新增语文到期复习读取、家长按技能汇总和孩子端同版本复习入口；拼音、生字、词语与古诗文积累仅作为待具名教研/版权审核的原创演示内容。语文教材分析改为 subject-aware 队列：数学保持 `curriculum-*.v1`，语文使用独立 `chinese-curriculum-*.v2` Schema/Prompt，并只记录短篇章边界证据，禁止复用数学提示或重建教材全文。正式签核、真实 PDF/Provider 和设备验收仍待完成。
- 2026-08-16：语文孩子端改为古诗抽查与看图写话。`0033` 仅退役六项旧演示内容并保留已有学习事实；经家长审核的教材古诗逐行自动生成“给上一句选下一句”的确定性题目，错答显示正确下一句并进入复习。`0034_picture_writing_guides` 和独立 `picture-writing-guide.v1` 只持久化已确认脱敏图的场景观察、启发问题和句式支架；该流程不复用数学题目提取/确认链路，不生成范文也不评分。真实 Provider、PostgreSQL 前滚和 Nova 9 图片联调尚未执行。

- 2026-08-16：语文 PostgreSQL 持久化增加并发安全的 Review upsert：两个不同幂等键提交同一内容时均保留追加 Attempt，并原子更新同一条 Review。新增随机 Household/Parent/Child 的集成测试，验证并发提交、导出字段和删除级联清理；本机数据库已前滚到 `0031`，未重新部署 Ubuntu。

- 2026-08-16：新增隔离 Chromium 登录态 E2E 与 GitHub Actions 门槛。真实 Next/API 链路覆盖首次强制改密、HttpOnly/SameSite Cookie、CSRF 拒绝、Session 轮换/退出撤销、超级管理员开通家庭、普通家长角色/跨家庭拒绝、双孩子聚合创建、`math/chinese` 学科差异和当前孩子切换；只使用运行时 synthetic 凭据，不读取 Ubuntu 家庭数据或上传浏览器 Trace/视频/截图。Ubuntu 真实账号/PostgreSQL 浏览器与设备生命周期仍待验收。

- 2026-08-15：发布 `v0.14.0` 多学科与语文首个纵向切片。孩子档案、教材和契约支持 `math/chinese`；语文采用版本化原创/授权内容、服务端 AnswerSpec、`chinese-score.v1` 确定性评分及追加写 Attempt/Review，英语继续排最后并保持 Provider 关闭。Ubuntu 已从 `0.13.0/0030` 前滚至 `0.14.0/0031_multisubject_chinese`；发布前 PostgreSQL/MinIO 备份通过隔离恢复，API/Web、迁移、旧教材数学回填、三张语文表/复合主键/seed、四个 worker、未认证保护、MinIO 私有端口和容器源码通过。正式语文内容、语文教材分析、并发/导出集成、登录态浏览器、真实 Provider/PDF 和设备验收仍待完成。

- 2026-07-31：家长工作台的“待复习错题”现在直接显示每道题的题干和到期日；最近学习记录迁移到独立导航页，默认近 30 个上海自然日，并可选择 180 天窗口内的单日。API/OpenAPI `0.13.0` 与迁移 `0030_learning_history_retention` 已部署 Ubuntu；DataLifecycle worker 固定清理超过 180 天且不被开放错题引用的详细题目、讲解和已结束复习链路。开放错题、Attempt、AuditEvent、账号和教材不在本次清理范围。升级前 PostgreSQL/MinIO 备份已隔离恢复验证，API/Web/四个常驻 worker、迁移服务、OpenAPI、数据库索引和运行源码通过复核；英语实时 Provider 保持关闭。

- 2026-07-29：孩子端第 3 级“查看完整解答”不再因没有可靠命中已发布教材知识点而显示阻断错误。确认题目和作答状态仍是前置条件；命中教材时继续严格使用其批准范围，未命中时改用适龄基础方法完整讲解，并明确不附或伪造教材来源。Ubuntu API 已部署健康，修复版 iPad Release 已覆盖安装并启动；真实 Provider 的题目质量仍待设备侧复核。

- 2026-07-29：本地新增数学/英语学科首页与供应商中立的英语口语练习框架。英语包含三个有界情景、家长逐孩子等级/同意设置、隐私最小化摘要和 Bearer Session WebSocket；按下即开麦、松开结束输入，断网/后台/权限失败立即关麦。`fake` 只能由测试依赖注入，不包含 Gemini 或真实 Provider，默认开关保持关闭。Android/iOS release 构建已通过；本轮未部署 Ubuntu，真实 PostgreSQL、语音质量和实体设备验收未完成。

- 2026-07-29：最新 iPad Release 包已用 Ubuntu API 地址构建、自动签名并覆盖安装到已配对的 iPad mini 6，Xcode 已成功启动 `Study Child 0.1.0 (1)`。本次只验证安装与启动，不读取设备账号或学习数据；登录、拍题和局域网实际流程仍待人工验收。

- 2026-07-28：家长 Web 调整为拍题解答与教材范围优先：移除首页的今日学习任务/本周目标、教材页的手工小节与任务推荐，以及孩子管理页的今日安排；既有任务和推荐数据未删除。新增仅超级管理员可见的“家庭权限”导航，可开通“新家庭 + 首个普通家长”、查看家长账号，并在目标家长没有所属孩子、且超级管理员重新验证密码后删除其账号和会话。已部署 Ubuntu：API/Web、迁移与四个 worker 健康，未认证家庭权限 API 返回 `401`。

- 2026-07-28：部署当前 API/Web/迁移与五个 worker 到 Ubuntu，健康版本为 `0.11.0`、Alembic `0028_super_admin_ownership`。前滚前完成 PostgreSQL/MinIO 备份并通过隔离恢复验证；API/Web `/healthz`、迁移 current/head、唯一超级管理员及孩子所有者约束通过。最新 Flutter iPad Release 包已使用 Ubuntu 地址构建并安装到无线 iPad；首次启动需在 iPad 上显式信任开发者 Team `VZ59988J63`，因此设备启动和真实拍题闭环仍待复核。

- 2026-07-28：修复 Ubuntu 家长 Web 未呈现账号管理能力的问题。此前 `/curriculum` 缺少 Next.js Suspense 边界，生产 Web 构建失败而旧镜像继续运行，导致新会话身份代理未上线。现已修复构建并部署：顶部显示当前用户名和角色，账户菜单提供“家庭与账号管理”与“退出登录”，超级管理员页面明确展示并优先放置“开通独立家庭”表单。浏览器已验证 `admin` 会话及菜单、账户权限区和独立家庭入口；未创建测试家庭或账号。

- 2026-07-27：修复孩子端“我会了，完成本题”后无法稳定返回学习桌的问题。完成状态现在显示“返回学习桌”，并关闭讲解、题目确认和拍题中间页直达学习桌；完整解答的返回操作同步采用该行为。新增完成后返回根页面 Widget 回归。APK 已构建，待 Nova 9 重新连接后安装。
- 2026-07-27：修复孩子端在 A→B→A 切换已保存账号后继续显示 B 的档案/用户名状态。认证上下文的服务端地址、Session 或用户名变化时，档案页现在重新加载目标账号数据，不复用前一账号的内存 Future。新增 A→B→A Widget 回归；release APK 已于 `17:36:38` 覆盖安装 Nova 9，待设备界面复核。
- 2026-07-27：根据 Nova 9 实际体验，暂时隐藏孩子端“今日任务”。此前多个已分配任务会同时堆叠，且进入教材计算任务后仍退化为通用拍题，不能代表指定题目的学习流程。学习桌现不再请求或展示任务列表，保留错题讲解和复习错题；家长端推荐记录、审批与既有任务数据不受影响。重新开放前必须完成单任务直接执行流。
- 2026-07-27：修复家长批准未来日期的推荐计划后，孩子端看似“没有读取题目”的误导。孩子端继续只让当天和待补做任务可开始，但在没有当前任务时会只读显示最近未来计划及计划日；家长端批准/已批准状态同步明确该日期。不会提前暴露或启动未来题目。Flutter 45 项、Web 20 项、类型、Lint 和格式通过；Ubuntu Node 24 Web 已重建健康，修复版 APK 已覆盖安装 Nova 9，仍待设备界面人工验收。
- 2026-07-27：修复孩子端 Android release APK 无法访问家庭 API：将 `INTERNET` 权限从仅 debug/profile 变体移至发布清单，并为用户显式配置的家庭 LAN HTTP 地址启用 Android 明文流量。会话恢复现在从已认证 `/auth/me` 读取并安全保存孩子用户名，账号页显示真实用户名；连接失败页显示可操作的地址/网络错误并可直接更改服务端地址。Flutter 43 项回归与 Analyze 通过，release APK 经 `aapt` 校验并已覆盖安装至 Nova 9；启动日志无权限/明文 HTTP 拒绝，账户与学习桌 UI 仍待设备侧人工确认。

本文件只记录用户可感知、运维可感知或兼容性相关的已发布变化，格式参考 Keep a Changelog，版本计划遵循 Semantic Versioning。

## [Unreleased]

- 语文教材页现在对数学和语文使用同一套家长审核动作；语文上传和发布会明确提示独立分析 v2，并在批准知识图谱后自动开放古诗抽查。
- 看图写话引导要求孩子先写出第一句再补充细节；图片入口或 Provider 暂时不可用时，可进入不包含图片判断的通用观察问题引导。
- 增加“批准教材后自动生成古诗相邻句选择题”的 API 回归，以及 Web 审核动作和看图写话边界测试。当前本地验证：API 非集成 `244 passed`、PostgreSQL 集成 `32 passed`、Flutter `70 passed`、Web `35 passed`。
- 本轮代码已部署 Ubuntu，并已提交、推送和创建 `v0.17.0`；没有连接真机或调用真实 Provider。

- 数学今日任务新增服务端会话下一题号（迁移 `0036_task_session_progress`），跨设备恢复时以服务端进度为准；每个孩子每天最多 3 项任务，未来任务不可提前开始，过期任务仍可补做；家长可幂等撤销任务并关闭活动会话。
- Flutter 任务客户端提交题号到在线/离线 Attempt，保留本机 SQLite 位置并优先采用服务端位置；新增 API、PostgreSQL 和 Widget 回归。当前本地和 Ubuntu API/OpenAPI 均为 `0.17.0`，已由 `v0.17.0` 固化发布。

- 2026-08-15：完成多学科与语文改造。本地 API/OpenAPI 升至 `0.14.0`，`Subject`、孩子档案、任务与教材支持 `math/chinese`；additive `0031_multisubject_chinese` 将旧教材回填为数学并新增版本化语文内容、确定性 Attempt/Review。家长可逐孩子启用语文并选择教材学科，孩子端按档案显示语文入口，首个原创 synthetic 纵向切片支持句子排序和“回答 + 文中依据”。答案规范只留在服务端，评分固定为 `chinese-score.v1` 且不调用 AI。语文教材分析新 Schema 完成前拒绝复用数学 Prompt；英语保持最后、默认锁定。Ubuntu 发布事实见本文件顶部 `v0.14.0` 条目；正式教研内容、并发/导出集成、设备和语文教材分析仍待完成。

- 2026-08-10：修复 GitHub 发布链路：`v*` 标签构建通过后自动创建同名 Release，并上传三个 ABI APK、`SHA256SUMS` 与 `BUILD-INFO.txt`；手动构建继续保留 Actions Artifact。API CI 同步执行仓库正式的 `mypy src` 范围，Ruff 格式化全仓 Python，并修复超级管理员确认题目被误判为孩子角色、孩子删除成功后幂等重放返回 `404` 两个既有回归；删除回执按发起家长账号隔离。

- 2026-08-10：新增 `Build Android APK` GitHub Actions，可手动运行或由 `v*` 标签触发；固定 Flutter `3.44.6`/Java 17，先执行格式、Analyze 和 50 项测试，再生成 ARM32、ARM64、x86_64 分架构 APK、SHA-256 清单和构建信息 Artifact。Android Gradle 支持从 GitHub Secrets 注入稳定签名；无 Secrets 时明确生成仅供侧载验证的 evaluation 包。新增完整构建/部署/签名/安装/升级回滚文档，并将独立 MIT 工具 `tchMaterial-parser` 作为合法取得教材后的可选本地辅助工具说明，不引入其代码、Token 或教材内容。

- 2026-08-10：撤回并删除从未部署的成人英语/Gemini 增量，包括服务端 Adapter、成人授权、环境变量、直接依赖、专属测试和部署文档。孩子英语学科入口、家长逐孩子设置、三个有界情景、Provider 中立 WebSocket/PCM 框架、摘要和安全 Policy 完整保留且默认锁定。同时补齐 GitHub README 与 Apache-2.0 许可证，修正学习记录 `422` 的 OpenAPI 响应引用；教材、模型权重、用户数据和第三方组件仍按各自权利与许可证处理。

- 2026-07-28：账号体系收敛为唯一实例级超级管理员。`admin` 已迁移为唯一 `super_admin`，可为亲戚创建“新家庭 + 普通家长账号”；每个新家庭只有普通家长和孩子，不再有家庭管理员。孩子用户名保持全局唯一，孩子档案绑定创建它的家长，家长只能管理自己名下孩子。新增仅服务器控制台可运行的超级管理员密码恢复命令，恢复会撤销旧会话并要求下次改密。Ubuntu 已完成备份、隔离恢复、`0028` 前滚和健康验证。

- 2026-07-28：新增多家庭自托管基础能力（权限模型随后已由本版本的 `0028` 收敛方案取代）。初始方案以每家庭管理员开通新家庭；现行方案仅保留实例级 `super_admin` 开通“新家庭 + 普通家长账号”。Web 和孩子端按登录会话的家庭作用域读取数据。教材上传新增“国家公开教材可跨家庭复用”显式声明：只有完整文件指纹匹配且来源知识图谱已审核的教材才复用私有文件和派生草稿，目标家庭仍须独立审核发布。真实多家庭浏览器和设备验收仍待完成。

- 2026-07-28：修复家长 Web“教材与任务”页切换孩子后仍显示前一孩子教材、知识图谱和推荐的问题。页面现以有效的 `?child=` 作为当前孩子来源；切换时清空旧视图并忽略迟到的旧请求，上传、审核、发布、推荐和原页预览均使用同一已授权孩子作用域。多家庭开放和跨家庭教材去重未启用；家庭内教材原件复用与安全删除进入 PLAN-0019。

- 2026-07-27：孩子端“还没完全会，加入复习”现在只有在题目和作答状态已确认、服务端原子创建错题/复习计划并返回错题记录后才会成功；随后直接返回学习桌。未确认状态会明确提示先完成题目确认，不再把仅结束会话显示成“已加入复习”。完整解答改为只使用当前孩子已批准知识图谱中的可靠匹配知识点：模型仅接收该点的学习目标、先修范围和来源页；无可靠匹配时系统拒绝生成完整解答，要求家长核对教材范围或题目。该变更已部署 Ubuntu；最新 iPad 包已安装，设备信任后再做启动验收。

- 2026-07-27：PDF 教材上传不再复用“手工导入小节”的默认教材版本和学期。系统先显示带文件名的待识别标题，解析后仅在封面/前页明确识别数学、年级和册别时本地回填教材名；显式家长填写的名称保持不变。整书教材归纳升级至 `curriculum-book-consolidation.v5`，兼容封面/目录/过渡章节的空知识点、非数组可选练习/先修引用，以及模型返回超过既有上限的目标、先修项和练习引用；系统只截取现有 Schema 允许的有界前缀，不会补造知识、页码或练习来源。缺少非空学习目标的知识点仍会被丢弃，无效页码或虚构来源的输出仍被拒绝。API、Web 与两个教材 Worker 已部署到 Ubuntu；既有失败任务继续要求家长手动重试。

- 2026-07-26：修复整书知识图谱将封面、目录和空白页强制归入知识章节而导致有效汇总失败的问题。章节范围和知识点页码仍只能引用已分析页面，但不再要求知识章节精确覆盖每一页；整书提示升级为 `curriculum-book-consolidation.v2`。

- 2026-07-26：修复 NewAPI 一次临时 `5xx` 使整本教材理解立即失败、失败状态又被页面显示为“AI 理解准备中”的问题。单次调用只对 `429`、`5xx`、网络错误和超时按 1 秒、2 秒退避重试，最多三次；最终失败保持可见并由家长显式重新理解。Ubuntu API、教材分析 worker 和 Web 已重建并健康。

- 2026-07-26：教材长任务在排队/分析中会每 8 秒自动刷新服务端状态，并显示全文处理中而非未落库的 `0/N` 页数；完成或失败不再依赖手工刷新，轮询不会重新提交任务。

- 2026-07-26：修复已批准的教材知识图谱仍显示“AI 理解准备中”并隐藏发布入口的问题。知识图谱存在时不再以旧解析占位小节覆盖状态；家长可继续审核发布，再用于讲解和任务推荐。

- 2026-07-26：修复已完成页级解析、知识图谱已批准的教材仍显示“已发布 · 未解析正文”的问题。发布状态和任务推荐改按已批准的分析页判断，实际可用教材显示“已发布 · 知识图谱已启用”。

- 2026-07-26：修复教材页级中间分析遗漏 `learning_objectives` 使整本任务失败的问题。页级提示升级为 `curriculum-page-visual.v5`，页级观察允许该字段为空，避免在没有可靠页面依据时编造学习目标；最终全书知识图谱中的知识点仍要求非空学习目标并保持家长审核。Ubuntu API/教材分析 worker 已重建，并以合成缺字段响应验证；既有真实教材不自动重试。

- 2026-07-24：修复教材页分析缺少有效 `section_title` 导致的 Schema 失败。页级提示升级为 `curriculum-page-visual.v4`；仅当同页章节标题有效时，服务端以它回填缺失/空小节标题，否则继续拒绝。Ubuntu API/教材分析 worker 已重建，并以合成空小节标题验证运行时行为；既有真实教材不自动重试。

- 2026-07-24：修复教材页和整书归纳中 Provider 以百分比、分值或 0–100 标度返回 `confidence` 导致的 Schema 失败。页级提示升级为 `curriculum-page-visual.v3`，两类提示都明确要求 0–1 JSON 数值；服务端只将确定标度归一化，其他内容仍拒绝。Ubuntu API/教材分析 worker 已重建，并以合成 `91`、`90分`、`92%` 验证为 `0.91`、`0.90`、`0.92`；既有真实教材不自动重试。

- 2026-07-24：修复教材页分析中 Provider 返回中文或同义难度标签导致的 Schema 失败。提示升级至 `curriculum-page-visual.v2` 并要求 `basic`、`medium`、`advanced`；服务端仅对明确中英文别名做内存归一化，未知值继续拒绝。Ubuntu API/教材分析 worker 已重建，并验证运行时将合成“基础题”收敛为 `basic`；既有真实教材不自动重试。

- 2026-07-24：修复 Ubuntu 教材分析通过 NewAPI 时的结构化响应兼容性。教材页/全书分析优先请求 JSON Schema；网关返回 HTTP 400 时依次降级为 JSON object 和不发送格式参数，结果仍须通过服务端固定 Schema，失败日志只含 Schema 元数据而不含教材内容。已重建 API 与教材分析 worker，并用不含教材数据的 1 像素合成图验证当前 `gemini-3.1-flash-lite` 的页级链路；已上传教材不会自动重试。

- 2026-07-24：将教材知识图谱链路成对部署到 Ubuntu 自用 Compose。前滚前生成并隔离恢复验证 PostgreSQL/MinIO 备份；API/Web/迁移与五个 worker 重建后，API 为 `0.11.0`、Alembic current/head 为 `0025_curriculum_knowledge_map`，教材分析/原页 OpenAPI 路径和 MinIO 私有端口边界均通过无数据烟雾。备份脚本现会冻结并直接恢复全部实际存在的教材写入 worker，避免 completed migrate 依赖阻止恢复。未上传真实教材，真实 Provider/浏览器/设备验收仍待完成。

- 2026-07-23：教材链路前滚至本地 API/OpenAPI `0.11.0` 与迁移 `0025_curriculum_knowledge_map`。PDF 逐页生成私有 JPEG，NewAPI 以最多 4 页一批理解图形与文字并归纳全书知识图谱；家长 Web 以原页为主审核章节、知识点、目标和练习并批准。任务推荐不再从 `CurriculumChunk.text` 正则抽题，只消费已批准知识点、具体来源题和全部开放错题；图形题保存视觉描述和来源页，孩子端可用登录 Session 打开对应私有教材原页。新增默认 Compose `curriculum-analysis-worker`。本轮未部署 Ubuntu，真实 118 页教材及 Provider 费用/质量仍待验收。

- 2026-07-23：家长教材工作台不再在列表中堆叠整页解析正文或全部推荐题干。教材快照现在可点击打开带页码切换、段落排版和置信度的阅读视图；任务推荐可打开单条计划查看来源、题目、页码、理由并批准或忽略。新增 parent-only 分页解析合同，不暴露原始 PDF、对象键或对象存储 URL。PDF 解析 worker 会过滤已知灰度图形操作数兼容警告，保留真实失败诊断。本项为本地实现，尚未部署 Ubuntu。

- 2026-07-23：修复教材 PDF 的可用性闭环。单文件大小统一为 50 MiB（52,428,800 字节），47.8 MiB 文件不再因十进制上限错误返回 413；本地解析 worker 改为只读取私有 `curriculum/` 文件，不再误用拍题图片的 8 MB `captures/` 读取边界。家长工作台可删除教材源文件及其派生解析结果，并会明确标出旧“已发布但未解析正文”的范围，提示重新上传实际 PDF 后再生成具体题推荐。孩子端完整解答显示后，操作入口改为“返回首页”。

- 2026-07-23：将本地最新工作区通过 `rsync` 部署到 Ubuntu 单家庭 Compose，排除并保留远端 `.env`、Git 和本地缓存，保留 PostgreSQL/MinIO/Redis 数据卷；API/Web/迁移和四个 worker 重建成功，API 返回 `0.10.0`，Alembic current/head 均为 `0024_intelligent_recommendations`，API/Web 健康检查通过。

- 2026-07-23：按真实 iPad 体验整改 Tutor 与任务推荐。L1/L2 在 NewAPI 启用时改为消费已确认题目文字和最小教材片段的递进生成，L2 绑定实际 L1，并新增答案泄露、重复、脚手架和题意相关门禁；“多人同时经历同一段时间”不再落入平均分模板。复习入口在暂无到期项时自动展示全部开放错题。任务推荐改为本地遍历全部开放错题与已发布 PDF 页级解析块，统计薄弱知识点、抽取具体教材题，只把最多 30 个带不透明来源键的候选交给 NewAPI 规划；未知来源、忽略已有错题/教材、到期错题未排当天和每日超限会整体拒绝。OpenAPI 前滚至 `0.10.0`，新增迁移 `0024_intelligent_recommendations`；家长端显示题目/页码/日期/时长，批准后孩子端展示当天全部来源任务。代码与 Ubuntu 部署现已完成，真实 PDF/NewAPI/iPad 质量验收仍待执行。

- 2026-07-23：完成 PLAN-0016 代码收口：拍题完成通过已确认题目/作答证据原子创建错题和复习计划；复习展示真实题目、追加 `ReviewAttempt`，服务端使用 `review-policy.v2` 的 1/3/7/14/30 天策略；教材上传收缩为多 PDF，文本 PDF 进入隔离本地解析并生成页级来源，扫描 PDF 进入待 OCR；Tutor 保存教材来源与 L1/L2 递进元数据。新增迁移 `0021`～`0023`、解析 worker 和 parser-backend internal network。真实 Ubuntu/设备/E2E 仍待发布前验收。

- 2026-07-23：将 PLAN-0016/ADR-0021 的教材范围收窄为 PDF-only：Web/OpenAPI/API 只接受 PDF，文本 PDF 本地隔离解析、扫描 PDF 标记待 OCR；Word/PPT/Excel 返回稳定错误，既有非 PDF 对象不解析、不发布。

- 2026-07-23：修正家长 Web 后台的信息架构：孩子切换移到全局顶栏并在工作台、教材和孩子管理页面保持当前孩子；侧栏移除与工作台内容重复的今日任务、待复习、最近学习和学习周报。教材页不再把上传文件误称为可用教材：PDF/Word/PPT/Excel 在真实正文解析完成前标记“待解析 · 尚未使用”且禁止发布；已审核的小节范围会把小节标题、学习目标和快照 ID 带入家长审批任务推荐，Tutor 教材正文引用仍明确标记为未启用。修正已部署 Ubuntu，API/Web 健康且两个后台 worker 正常运行。

- 2026-07-22：家长 Web 端按简洁明亮的现代后台方案完成整体重构：新增固定分组导航、当前孩子与服务状态、今日优先事项、本周学习趋势、可展开逐题学习记录，以及统一的孩子账号和教材任务管理页面。多孩子、任务、作答四态、提示/完整解答、教材上传与推荐审批继续使用真实 API 数据；新增响应式窄屏布局、键盘焦点和可访问图标按钮。Web 14 项测试、Lint、类型、生产构建和合成登录浏览器视觉 QA 通过。

- 2026-07-20：拍题视觉结果新增自动作答四态候选、置信度和可见步骤，确认页会自动选中并允许校正；练习页只读取服务端已确认状态，不再要求再次手点。`worked/blank` 分别按已有作答/无思路分支提示，第三级返回完整步骤、最终答案和验算；`unclear/answer_area_missing` 不再误判为空白。单题页移除硬编码“第 2/4 题”，家长端新增最近逐题题目、作答状态、分级提示和完整解答详情。API/OpenAPI 前滚为 `0.9.0`，数据库迁移为 `0020_answer_evidence`；Ubuntu 备份、rsync、重建、迁移和合成 NewAPI 解答验收通过，iPad profile App 已安装启动。

- 2026-07-20：修复孩子端数学练习仍显示原型名“小禾”的问题，标题现在使用当前登录用户名；真实题目进入练习页会自动获取首条提示，本地零成本 Tutor 会依据已确认题目的数量变化、比较、分组、求总量或分数结构给出相关分级提示。修复视觉人工确认后因 Capture 仍为 `needs_correction` 而被 Tutor 错误拒绝的 409，并将提示失败文案与照片上传错误分离。Ubuntu API 已更新健康，iPad 已热重启。
- 2026-07-20：修复拍题照片在脱敏后因 PNG 体积膨胀而被上传页拒绝的问题；客户端会等比缩小并重新生成不可逆脱敏副本，确保上传前不超过 7.5 MB，同时保持遮挡区域与图片同步缩放。仍无法满足限制时会提示只裁剪题目区域，而不再显示含糊的大小错误。Flutter 38 项回归通过。
- 2026-07-20：优化孩子端拍题流程：脱敏后进入独立上传进度页并显示转圈状态，完成后自动进入题目确认；上传失败可在当前页重新上传或返回拍题。题目确认框改为大尺寸可上下拖动的多行编辑区。
- 2026-07-20：孩子端登录后移除服务端切换入口，新增账号页，支持安全会话切换、添加账号和注销当前账号；不保存密码，服务端地址仅在登录流程使用。Flutter 37 项回归通过。
- 2026-07-20：修复点击“确认题目”后因服务端请求无界等待而卡住的问题；Capture 请求增加连接/响应超时，确认失败会恢复按钮并显示可重试提示。
- 2026-07-20：修复中文题目确认请求因客户端按 Latin-1 写 JSON 而失败的问题；Capture、登录和改密请求现在统一使用 UTF-8 编码。
- 2026-07-20：修复同一照片重新识别时复用已被服务端清理对象的问题；重试现在创建新的 Capture 和识别任务，并区分 Provider 配额/配置失败与照片质量问题。
- 2026-07-20：修复教材上传在非安全浏览器上下文中因 `crypto.randomUUID()` 不可用而失败的问题；幂等键改为兼容 `crypto.getRandomValues` 的实现，Ubuntu Web 已重建验证。
- 2026-07-20：修复教材上传返回 `403 csrf token required` 的问题；教材页所有写请求现在会把登录 Cookie 中的 CSRF Token 发送到 Web/API 代理，并新增回归测试。
- 2026-07-20：iPhone 11 真机调试已恢复；修复登录卡片在紧凑窗口中的底部布局溢出，登录表单现在可滚动。
- 2026-07-20：补齐 iOS 家庭局域网连接声明：增加本地网络用途说明和仅限本地网络的 ATS 例外，不开放任意公网明文 HTTP；登录页增加真实服务健康检测、手动重试和安全网络错误提示。Flutter 32 项回归通过；当前 iPhone 仍被设备本地网络/路由层以 `errno 65` 阻断，服务端没有收到请求。
- 2026-07-20：iPad mini 6 已通过 Flutter 工具重新安装、启动和热重启；服务健康检查成功到达 Ubuntu API 并返回 200，iPad 网络链路可用。
- 2026-07-20：拍题识别失败页增加“重新识别当前照片”和“重新拍题”，重试保留当前脱敏照片并使用新的幂等键创建识别任务；同时修复从拍题返回学习桌时的异步 `setState` 运行时错误。Flutter 33 项回归通过。

尚无产品发布；已完成不含真实儿童数据的 Ubuntu 自用 Compose 环境验收。当前本地与 Ubuntu 代码/迁移头为 `0.11.0`/`0025_curriculum_knowledge_map`。

- 2026-07-18：教材工作台增加多文档选择与上传队列，支持 PDF、DOC/DOCX、PPT/PPTX、XLS/XLSX；API 对单文件/批次大小、扩展名和 SHA-256 做有界校验，通过 boto3 S3 兼容接口写入私有 MinIO，并为每个文件生成待解析草稿。真实文档解析仍待后续接入。

- 2026-07-18：完成 PLAN-0014 首版纵向切片：家长可导入带授权声明和 SHA-256 的教材 manifest，形成草稿并审核发布 `CurriculumSnapshot`；Attempt 增加 `worked/blank/unclear/answer_area_missing` 与确认标记；Flutter 增加错题讲解/复习错题/今日任务三入口；TaskRecommendation 默认待家长审批，批准后幂等创建数学任务。真实 PDF 二进制解析、教材 grounding、完整错题本和最终设备/Provider 联调仍待完成。

- 2026-07-18：完成 ADR-0018 流式拍题上传的 Ubuntu 成对部署。API/Flutter 只使用 Session 上传到 API，服务端通过 boto3 multipart 写入内部私有 MinIO，宿主/LAN 不暴露 `9000`；清理远端残留公开对象存储配置。真实 NewAPI synthetic 请求已到达 Provider，但返回 HTTP `402`，客户端现显示余额/模型额度的可操作提示。
- 2026-07-18：完成 PLAN-0013 首版孩子管理聚合。家长一次提交事务创建孩子档案和唯一绑定账号，支持聚合列表/编辑/删除、账号管理以及首页 `?child=` 选择和服务端任务过滤；新增 `0016_child_account_uniqueness`，浏览器 E2E 和双孩子设备回归仍待执行。

- 项目 Owner 接受 ADR-0018：Capture 上传改为 App 携带 Session 只访问 API，API 有界流式校验并通过内部地址写入私有 MinIO；OpenAPI 已删除 `upload_url`/独立确认，Compose 已删除 `OBJECT_STORAGE_PUBLIC_ENDPOINT_URL`/`MINIO_API_PORT` 并取消 LAN `9000`，Ubuntu 已完成成对部署。
- 项目 Owner 批准 PLAN-0013 的 Web 体验方向：创建孩子以一次事务同时创建档案和唯一绑定账号，管理页按每个孩子一张聚合卡呈现；家长首页增加当前孩子选择，并统一过滤问候、任务、档案和周报。`Account`/`ChildProfile` 仍按安全职责分表；首版代码和 Ubuntu 部署已完成，浏览器 E2E 仍待执行。
- 项目 Owner 接受 ADR-0020/PLAN-0014：数学首科主线调整为“家长发布年级/学期/教材知识范围 → 孩子选择错题讲解/复习错题/今日任务 → 错题证据与完整讲解 → 正式错题本/到期复习 → 家长可控任务建议”。拍题目标同时包含题目和孩子解答：有作答时针对首个可验证错步讲解，答题区确认空白时记录“没有思路”并从头讲解；未拍到答题区或不清不得自动当空白。系统建议默认须家长批准。TODO-016～019 已建立；后续 0017/0018 已落地错题复习最小闭环、教材 manifest/发布、三入口、四态分支和推荐审批，真实文件/grounding/最终联调仍待完成。

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
- 2026-07-27：教材发布改为并行范围，发布新 PDF 不再将同一孩子旧教材标为“已替换”。每份教材可独立查看和删除；推荐同时遍历所有已发布且已批准的知识图谱，并保留题目所属教材和页码。`0026_parallel_curriculum` 已在备份后部署 Ubuntu，恢复此前自动替换导致的两份 `rejected` 教材为 `published`；API/Web 健康通过。
