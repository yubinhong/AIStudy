# AI_CONTEXT.md

> 面向 AI 的项目入口与当前快照。稳定详情以对应主文档为准；本文件只保留摘要、状态和导航。

## 1. 项目快照

- 项目：家庭 AI 学习助手
- 一句话目标：复用家庭现有设备，以数学错题闭环为主线，并通过显式多学科核心逐步增加语文确定性练习。
- 当前阶段：`P1 MULTISUBJECT FOUNDATION / CHINESE MVP / GATED ENGLISH LAST`
- 主要用户：小学阶段孩子与家长/监护人；辅助角色为家庭内容维护者和项目维护者。
- 生产状态：`SELF_HOSTED_DEPLOYED`（Ubuntu 自用 Compose 运行 API/OpenAPI `0.17.0`/`0036_task_session_progress`；API/Web、迁移和四个常驻 worker 健康；不等同于公网/商业生产批准）
- 当前版本：本地和 Ubuntu API/OpenAPI 均为 `0.17.0`、迁移头 `0036_task_session_progress`；Ubuntu 于 2026-08-23 完成部署，当前可追溯标签为 `v0.17.0`。
- 最近更新：`2026-08-23`

## 2. 当前工作状态

- 2026-08-23 继续实现：数学“今日任务”每道题仍必须有指定题干并将当前题目和教材来源传入拍题/确认页；多题任务在同一会话内按序执行，中间题追加 Attempt、最后一题关闭任务；端侧 SQLite 保存服务端/家庭/孩子范围内的下一题号，进程重开后可继续；已确认作答、任务完成、复习收口和跳过在断网时进入结构化 SQLite 队列，联网后先按最多 50 条批次幂等同步 Attempt，再按顺序重放终态事件；服务端拒绝第二个活动会话。语文首页只保留“古诗抽查”和“看图写话”，古诗题库为空时也显示受限入口。语文 scorer golden 覆盖八类技能，正式原创内容必须有项目 Owner 审核、审核时间和权利凭证摘要才可被孩子读取；古诗抽查先均匀抽取诗目再抽相邻句题；服务端已持久化跨设备题号、每日容量、未来日期/逾期边界和家长撤销规则；教材批准自动生成古诗题、看图写话空句阻断和安全通用降级已补回归；完整 PostgreSQL 集成为 `32 passed`，API 非集成为 `244 passed`，Flutter 为 `70 passed`，Web 为 `35 passed`。本轮不连接手机/平板；真实 Provider/PDF、正式签核、Ubuntu 真实账号浏览器和设备 E2E 仍未完成。

- 活动计划：`TASK-0012` / `PLAN-0031` 的隔离 Chromium 登录态 E2E 已完成，覆盖首次改密、Cookie/CSRF/撤销、跨家庭角色和双孩子学科/切换，并加入 CI；`PLAN-0030` 多学科/语文切片和 Ubuntu `0.17.0/0036` 已发布，本机 PostgreSQL 语文并发 Attempt/Review 合并、导出和级联清理已通过。`PLAN-0032`/`PLAN-0033` 的本地代码已扩展到语文到期复习、技能报告、古诗抽查和看图写话，历史原创演示已在 `0033` 退役，但正式教研/版权签核仍未完成。英语保持供应商中立锁定框架并排最后。语文真实 Provider/PDF、Ubuntu 真实账号浏览器和设备 E2E 待完成。
- 任务状态：ADR-0018/PLAN-0012 已完成本地与 Ubuntu API/Flutter/Compose/契约迁移；Ubuntu 不再依赖预签名直传，MinIO `9000` 未向宿主/LAN 暴露。最终真机仍未回归。
- 当前分支：`master`；本地 API/OpenAPI `0.17.0` 和 `0036_task_session_progress` 已完成代码与本机验证，并已部署 Ubuntu、提交、推送和打 tag `v0.17.0`。
- 当前重点：完成正式语文内容具名教研/版权签核、真实 Provider/PDF 质量与成本评测、Ubuntu 真实账号浏览器和设备 E2E。本轮按约定不连接手机或平板，设备回归留到代码完成后。英语继续排最后。既有数学教材原页/知识审核、推荐详情和学习记录继续按已部署合同运行。
- 已完成：本地与 Ubuntu 已部署的既有 OpenAPI/迁移、视觉四态候选与确认、可信 VerifiedQuestion → 云端递进 L1/L2 → 完整步骤/答案/验算、Mistake/Review closeout、语文确定性 Content/Attempt/Review、古诗抽查和看图写话引导，以及 PDF 私有原页、分批多模态教材理解、全书知识图谱、家长批准、“批准知识点 + 全部开放错题”的来源受限推荐和 180 天详细学习历史策略；本地新增任务会话位置、容量/未来日期/撤销保护。
- 2026-08-16 语文 `v0.16.0` 已部署：`0033` 退役六项语文演示并从已审核教材逐行古诗生成抽查；`0034` 增加独立 `picture_writing_guides` 与 `picture-writing-guide.v1`。看图写话只消耗用户确认的脱敏派生图，Provider 只返回观察/提问/句式支架，绝不走数学抽题、生成范文或评分。Ubuntu 对无人物、无文字的合成花园图完成一次真实 Provider Schema 冒烟；不代表儿童图片、质量、成本或完整设备验收。
- 当前未完成：真实 118 页 PDF 多模态知识质量/费用/重试验收、Ubuntu 真实账号/PostgreSQL 浏览器链路、实际相机四态闭环、教材个人信息自动门禁、自动视觉检测器、四设备回归、正式依赖/镜像安全扫描、监控告警和已批准的 RPO/RTO。NewAPI 合成完整解答和隔离登录态浏览器 E2E 已通过；云端教材分析、L1/L2 和推荐 planner 尚未进行真实 Provider 质量/成本验收。PLAN-0032 本地实现已补齐语文到期复习、家长技能汇总及 `chinese-curriculum-*.v2` 独立 Schema/Prompt/短边界证据；内容仍为待具名教研和版权签核的原创演示包，不能作为正式课程或部署验收。
- 新产品主线已完成代码收口：ADR-0020/PLAN-0014 的错题、复习、教材和 Tutor 关键事实链已接通；PLAN-0016 进入设备/E2E/发布验收阶段，ADR-0021 已接受。
- Web 多孩子/多家庭现状：账号与档案已由孩子管理聚合 API/Web 统一创建、列表和删除；全局顶栏通过 `?child=` 切换并保持当前孩子作用域。`0028` 已将最早 `parent_admin` 收敛为唯一 `super_admin`，其可创建新家庭的普通家长；普通家长只管理自己创建的孩子，当前不支持匿名注册、邀请或账号跨家庭切换。家长显式声明的国家公开 PDF 可按完整内容指纹复用已审核的私有 PDF/页图/知识图谱草稿，目标家庭仍须审核发布；儿童数据和学习事实不共享。2026-07-28 已在 Ubuntu PostgreSQL 前滚并完成 API/Web 健康、角色/孩子归属和备份恢复验证；跨家庭浏览器流程与真机验收仍待执行。
- 2026-07-28 Web 收口（已部署 Ubuntu）：家长首页不再展示今日学习任务或本周任务目标；教材页不再提供手工小节和任务推荐；孩子管理只管理孩子。超级管理员左侧导航新增“家庭权限”，可开通新家庭及首个普通家长、列出家长，并只删除没有所属孩子的普通家长，删除需重新验证超级管理员密码。任务/推荐后端记录与孩子端错题、复习闭环均未删除。API/Web/四个 worker 健康，未认证访问家长权限 API 返回 `401`；浏览器角色流程仍待人工验收。
- 2026-07-31 Web 学习记录（已部署 Ubuntu）：工作台的待复习区域直接列出题干和到期日；完整逐题记录迁移到独立“学习记录”页，默认近 30 个上海自然日并支持 180 天窗口内单日筛选。OpenAPI `0.13.0` 增加有界时间参数，`0030` 增加生命周期索引；DataLifecycle worker 固定清理超过 180 天且不被开放错题引用的详细题目/讲解与已结束复习链路。备份 `/home/syin/study-backups/20260731T020739Z` 已通过隔离恢复，API/Web/四个常驻 worker、迁移服务、OpenAPI、数据库表/索引和容器内源码均已核验；登录态浏览器 E2E 仍待执行。
- 教材实际消费状态：新上传只接受不含个人信息的 PDF；`material-parse-worker` 抽取辅助文字且不丢弃无文字页，`curriculum-analysis-worker` 私有渲染原页并按最多 4 页一批交给单一 NewAPI，再归纳整本章节/知识点/目标/先修关系/练习。家长对照原页批准后才能发布；Tutor 只读最小已批准片段，任务推荐遍历全部开放错题和已批准知识点/具体练习，不再从 `CurriculumChunk.text` 抽题。批准任务写入视觉说明、页码和孩子 Session 原页入口。
- 2026-07-31 部署状态：已保留远端 `infra/compose/.env`、卷与经过隔离恢复验证的 PostgreSQL/MinIO 备份，成对重建 API/Web/迁移与四个常驻 worker。API `0.13.0`、Alembic `0030_learning_history_retention`、API/Web `/healthz`、OpenAPI 学习范围参数、英语表、生命周期索引和容器内源码均通过，MinIO `9000` 未向宿主暴露；英语 Provider 保持关闭，真实家庭 PDF、跨家庭登录态浏览器和设备质量验收仍待完成。
- 当前认证：只有家长/孩子用户名密码、Argon2id 和可撤销不透明会话；Web 使用 HttpOnly Cookie/CSRF，Flutter 使用平台安全存储。隔离 Chromium 自动 E2E 已覆盖首次改密、Cookie/CSRF、Session 轮换/撤销、跨家庭角色和双孩子；Ubuntu 真实账号/PostgreSQL 浏览器与多设备重启生命周期仍待验收。
- Android 设备验收：Nova 9 登录/首次改密/绑定档案历史记录有效；流式上传新链路已部署但最终拍题、上传进度、Extraction/VerifiedQuestion、权限拒绝恢复、账号切换、弱网和重启仍需设备在场时验收。
- 2026-07-27～28 客户端连接、账号切换、完成返回与任务入口收口：定位 Android release 仅在 debug/profile 清单声明 `INTERNET`，导致生产 APK 无法访问 API；发布清单现包含网络权限并允许用户配置的家庭 LAN HTTP 地址。会话恢复会从 `/auth/me` 回填孩子用户名并在账号页显示。切换账号时档案页现会识别服务端、Session 或用户名变化并重新加载目标账号档案，防止 A→B→A 后沿用 B 的显示状态。题目完成/完整解答后的返回现会 `popUntil` 学习桌根路由，并在完成状态显示明确按钮。真实体验确认推荐任务还没有直接执行指定题目的流程，孩子端会堆叠任务并退化进入通用拍题；学习桌因此临时不再请求或展示今日任务，只保留错题讲解和复习错题。Flutter 48 项/Analyze 与 Release 构建通过；Ubuntu 已部署 `0.11.0`/`0026_parallel_curriculum`。最新 iPad 包已安装，首次启动仍需在设备上信任开发者签名；任务执行重构由 TODO-215 跟踪，账号切换与完成返回仍待设备界面人工复核。

## 3. 已验证的仓库事实

- 仓库根目录：`/Users/ybh/PycharmProjects/study`。
- Git：分支 `master`，最近提交 `a29e65b`；`v0.16.0` 标签指向已部署的 `dbaa9b0`，工作区有本轮未提交的数学任务、语文抽题公平性、内容门禁、PostgreSQL 夹具和文档改动。
- 现有内容：根目录上下文文档、`prompts/` 工作流模板、`docs/adr/0000-template.md`、`家庭AI学习助手_架构设计_v1.0.docx`。
- 已创建并验证：`apps/`、`services/`、`packages/`、`evals/`、`infra/` 的 P0/P1 核心路径、配置、锁文件、测试和 Compose；Flutter Android release APK 与 iOS release 无签名 Runner.app 已构建。Ubuntu VM 上的 amd64 完整栈运行 API `0.17.0`/迁移 `0036`，新流式上传、孩子管理、PDF 解析、错题闭环、私有原页、知识图谱、来源受限推荐、学习记录保留、语文确定性 Content/Attempt/Review、古诗抽查和看图写话独立引导已部署；NewAPI synthetic 完整解答和看图写话 Schema 冒烟已成功，真实 L1/L2/智能规划、真实语文 Provider/PDF 质量仍待实测；ARM 调试镜像因 PaddlePaddle 3.3.1 无 Linux aarch64 wheel 而不含旧本地 OCR。
- 设计稿：31 个段落、6 个表格、3 页，定义 P0/P1/P2、设备职责、核心实体/API 和发布门槛；本地渲染缺少部分中文字体，但 OOXML 文本可完整提取。

## 4. 主文档索引

| 主题 | 唯一事实来源 | 当前状态 |
| --- | --- | --- |
| 项目目标、范围、设备、环境 | `PROJECT.md` | Active；目标与现状已分离 |
| P1 产品需求与验收 | `PRD.md` | Draft；待产品 Owner 审批 |
| 当前任务 | `TASK.md` | TASK-0012/PLAN-0030 多学科基础和语文首个纵向切片本地完成，剩余验收继续；TASK-0011 英语框架保持锁定并排最后 |
| 复杂任务计划 | `PLANS.md` | PLAN-0030 的本地切片与 Ubuntu 发布完成；PLAN-0022 孩子英语框架继续关闭，PLAN-0018 已部署数学教材主线并等待真实 PDF/Provider/设备验收 |
| 系统结构、数据流、接口 | `ARCHITECTURE.md` | P0/P1 单家庭核心闭环已实现；残余边界明确记录 |
| 测试命令和质量门槛 | `TESTING.md` | API/Web/Flutter 质量命令已有验证；原生构建结果以最新记录为准 |
| 儿童数据、权限与 AI 安全 | `SECURITY.md` | 基线草案；生产开放项未决 |
| 部署、回滚、告警与恢复 | `RUNBOOK.md` | Ubuntu 自用部署与恢复已验证；监控/公网发布未建立 |
| 架构决策 | `DECISIONS.md`、`docs/adr/` | ADR-0025 供应商中立儿童英语框架、ADR-0020～0023 教材驱动数学主线和 ADR-0018 已 Accepted；替代关系见索引 |
| 工作队列 | `TODO.md` | TODO-014/015 In Progress 并已部署；TODO-016/018/019/020 的本地实现由 PLAN-0016/0017/0018 收口，等待真实部署和 E2E |
| 已发布变化 | `CHANGELOG.md` | 无产品发布 |
| 原始设计基线 | `家庭AI学习助手_架构设计_v1.0.docx` | v1.0；后续 ADR 可替代 |

## 5. 技术摘要

- 客户端：Flutter iOS/Android；Next.js + TypeScript Web/PWA；端侧 SQLite。
- 后端：Python 3.12 + FastAPI 模块化单体 + 异步 Worker。
- 数据：PostgreSQL 为业务事实源；pgvector 做检索；Redis 做缓存/队列；私有 S3/MinIO 存图片。新链路仅由 API/worker 通过内部网络访问；Ubuntu `0.17.0` 已完成流式上传、教材解析、私有原页、知识图谱、学习历史保留、语文 Content/Attempt/Review、古诗抽查、看图写话引导和私有 MinIO 成对迁移。
- 契约：`packages/contracts` 本地和 Ubuntu OpenAPI 均为 `0.17.0`，新增 `math/chinese` 档案/教材学科、语文内容与 Attempt、古诗和看图写话路径、任务会话下一题号和家长撤销路径；孩子合同不包含 AnswerSpec。SDK 生成器尚未选择。
- AI：本地 PrivacySanitizer、固定 OCR/脱敏/Tutor eval、NewAPI Adapter、ImageAnalysis/CurriculumAnalysis worker、QuestionExtraction/VerifiedQuestion 和服务端可信 TutorTurn 已实现；教材页图有界分批后形成待家长批准的知识图谱，L1/L2 使用已确认文字和最小已批准教材片段，推荐由 NewAPI 在本地来源候选上规划。孩子英语只保留供应商中立接口、`disabled` 和测试注入的 `fake`，没有真实语音 Provider；教材个人信息自动门禁、自动视觉检测器和云端教材/提示/推荐真实质量验收仍未完成。
- 交付：Ubuntu 自用 Compose 已部署并完成迁移、健康、NewAPI synthetic 和 PostgreSQL/MinIO 恢复验收；OpenTelemetry、正式告警和公网发布未实现。
- 认证：ADR-0017 已实现代码目标：同一 Household 内家长/孩子账号密码 + 可撤销不透明会话；Web 用 HttpOnly Cookie/CSRF，Flutter 用平台安全存储；不接入短信、邮箱、社交登录、OIDC 或 MFA，也不保留 HMAC/Demo 兼容。
- 学习主线：ADR-0020/0023 已批准 CurriculumAssignment/Material/Snapshot → 私有原页/KnowledgeMap 批准 → VerifiedQuestion+已确认 AttemptEvidence（`worked` 或确认空白）→ 分模式 Tutor → MistakeRecord/ReviewSchedule → TaskRecommendation；本地代码已接通拍题 closeout、证据化复习、多模态教材知识/grounding、L1/L2 递进和来源原页，当前剩余真实部署、Provider/设备和发布门槛验收。

## 6. 仓库地图

| 路径 | 责任 | 当前状态 |
| --- | --- | --- |
| `apps/child_flutter` | 孩子学习、拍题、提示交互、离线队列 | 本地数学任务恢复/断网 Attempt 与终态队列、语文古诗抽查/看图写话入口已实现；英语锁定，真实设备待回归 |
| `apps/web` | 家长后台、内容维护、Windows Web/PWA | 逐孩子语文开关、教材学科选择和隔离 Chromium 登录态 E2E 已实现；语文分析走独立 v2 合同，真实账号浏览器与 Provider 质量待验收 |
| `services/api` | FastAPI 模块化单体和 Worker | 本地和 Ubuntu `0036` 已部署 subject-aware 教材及语文 Content/Attempt/Review；本机 PostgreSQL 并发/导出集成通过，正式内容与 Ubuntu 真实账号浏览器验收待完成 |
| `packages/contracts` | OpenAPI、JSON Schema、生成 SDK | 本地和 Ubuntu `0.17.0`，SDK 生成器尚未固定 |
| `evals` | 固定 AI 质量/安全/成本评测 | 既有数学/隐私 eval 增加 7-case 英语安全 Policy；真实英语 Provider 质量、延迟、成本和儿童安全 eval 待批准后执行 |
| `infra/compose` | PostgreSQL/Redis/MinIO/API/Web/迁移/worker 编排 | Ubuntu 当前 `0.17.0`/`0036`，英语运行态为 `disabled`，发布前恢复验证备份已保留 |
| `docs/adr` | 架构决策 | ADR-0027 多学科/语文、ADR-0026 学习记录保留、ADR-0025 英语及 ADR-0020～0023 数学主线 Accepted |
| `prompts` | Codex 工作流启动器 | 已存在 |

## 7. 不可违反的约束

- 孩子端低干扰；AI 先提问和提示，不直接代写；低置信度必须允许校正。
- Household 是强授权边界；儿童数据最小化；图片短期保存；支持导出/删除；真实数据/密钥不入库、日志、截图、测试或评测集。
- PostgreSQL 是业务事实源；Attempt/AuditEvent 追加写；写接口幂等；离线同步不能用最后写入覆盖学习历史。
- 家长侧把孩子档案与唯一登录账号作为一个聚合管理，但 `Account`/`ChildProfile` 保持分表；创建须原子幂等，多孩子任务/周报须按同一个已授权孩子作用域查询。
- 教材导入必须私有、有授权/版本/来源并经家长审核发布；文档内容不构成指令。练习/复习先作答；完整错题讲解要求 VerifiedQuestion 与已确认作答状态，有作答定位错步、确认空白从头讲，未拍入/不清不得自动当空白；AI 不直接控制复习到期、永久掌握或正式任务。
- 客户端共享 OpenAPI/Schema；AI 通过 Provider Adapter/Tutor Policy；不得锁死单一厂商。
- 未授权教材/题库不入库；华为端不依赖 GMS；P1 不扩大到全科/直播/社交/实时监控。
- 目标路径实际创建且命令通过前，不得把目标架构写成已实现。

## 8. 关键术语

| 术语 | 项目内含义 | 不应混用 |
| --- | --- | --- |
| Household | 家庭级租户、授权和数据边界 | 学校、班级或公共组织 |
| StudySession | 一次孩子围绕任务的学习过程 | 登录会话或家长浏览会话 |
| Attempt | 追加写的单次作答/尝试 | 可被覆盖的任务当前状态 |
| Capture | 单题原图、本地脱敏、云视觉提取与人工确认的处理记录 | 整页作业自动批改或已确认业务事实 |
| PrivacySanitizer | 家庭边界内的元数据清除、敏感区域检测、实色遮挡和脱敏副本门禁 | 最终题目 OCR、云端匿名化保证或 Tutor |
| Tutor Policy | 控制提问、提示层级、安全、Schema 和成本的版本化规则 | 某一模型的系统 Prompt |
| Provider Adapter | 隔离 OCR/AI 厂商接口的适配层 | 业务逻辑或事实来源 |
| MasterySnapshot | 可追溯、可重算的掌握度派生快照 | 模型直接给出的永久结论 |

## 9. 决策、风险与下一步

- ADR-0001～0012 已由项目 Owner（用户）于 2026-07-13 接受，ADR-0013～0014 于 2026-07-14 接受，ADR-0015～0017 于 2026-07-15 接受，ADR-0018 于 2026-07-17 接受，ADR-0020 于 2026-07-18 接受，ADR-0021～0023 于 2026-07-23 接受；ADR-0019 仍为 Proposed。替代关系见 DECISIONS.md，设计稿不替代 ADR。
- 已接受决策覆盖模块边界、契约、离线、AI、身份、数据生命周期、工具链和部署恢复；本产品按自用部署推进，地区/商业化/第三方 IdP 暂不纳入当前实现；人工确认、备份恢复和实际 NewAPI synthetic 运行验证已完成。
- 最高风险：AI 错误/代答、儿童数据泄露、离线记录覆盖、四端范围失控、P0 骨架与目标架构漂移。
- 正式发布阻塞：自动视觉检测器、法域/正式告知、密钥/静态加密、SLO/RPO/RTO、监控告警、Ubuntu 真实账号/PostgreSQL 浏览器与四设备回归；隔离认证 Chromium E2E 已通过，单家庭自用 LAN 部署已可运行。
- 最近完成：`PLAN-0011` 的可信 Tutor、SQLite 离线、会话/复习/周报、数据导出/删除、生命周期 worker、恢复演练和 Ubuntu 自用栈基础部署。
- 最近规划：`PLAN-0013` 已把“创建孩子合并账号/档案”和“首页切换当前孩子”拆成契约/迁移、API 事务、Web 管理页、工作台选择及双孩子 E2E 五阶段；前四阶段已实现并部署，双孩子 E2E 待执行。
- 最近实现：`PLAN-0018` 用 `0025` 起的教材知识图谱链路替代残缺 PDF 文字抽题：私有原页 → 每批最多 4 页多模态理解 → 全书知识图谱 → 家长批准 → 错题/知识点来源受限任务。Web 原页/知识审核和孩子端 Session 原页入口已部署 Ubuntu；118 页真实 Provider 质量/成本和最终发布门槛仍待完成。

## 10. 更新规则

- 任务切换、首个 commit、远程仓库建立、代码路径/锁文件/CI 出现、架构或环境变化、里程碑完成后更新本文件。
- 只保留摘要和指针；稳定详情回到对应主文档。
- 已批准决策进入 ADR，已发布的用户/运维变化进入 `CHANGELOG.md`，未执行工作进入 `TODO.md`。
