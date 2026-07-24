# AI_CONTEXT.md

> 面向 AI 的项目入口与当前快照。稳定详情以对应主文档为准；本文件只保留摘要、状态和导航。

## 1. 项目快照

- 项目：家庭 AI 学习助手
- 一句话目标：复用家庭现有设备，以数学为首科提供“家庭教材范围 → 错题讲解 → 错题沉淀 → 到期复习 → 今日任务/家长反馈”的开源、可控学习闭环。
- 当前阶段：`P1 SECURITY FOUNDATION / CURRICULUM-MISTAKE ROADMAP`
- 主要用户：小学阶段孩子与家长/监护人；辅助角色为家庭内容维护者和项目维护者。
- 生产状态：`SELF_HOSTED_DEPLOYED`（Ubuntu 单家庭 Compose 正在运行 API `0.11.0`/`0025_curriculum_knowledge_map`；API/Web/五个 worker 健康；不等同于公网/商业生产批准）
- 当前版本：本地与 Ubuntu API/OpenAPI `0.11.0`、迁移头 `0025_curriculum_knowledge_map`（尚无正式产品发布标签）
- 最近更新：`2026-07-24`

## 2. 当前工作状态

- 活动计划：活动任务为 `TASK-0010`；PLAN-0018 的私有教材原页、分批多模态页面理解、整本知识图谱、家长批准、批准知识点/全部开放错题推荐和孩子端受鉴权原页入口已部署。剩余是真实 118 页教材/NewAPI、浏览器/设备 E2E 和发布门槛验证。
- 任务状态：ADR-0018/PLAN-0012 已完成本地与 Ubuntu API/Flutter/Compose/契约迁移；Ubuntu 不再依赖预签名直传，MinIO `9000` 未向宿主/LAN 暴露。最终真机仍未回归。
- 当前分支：`master`；工作区包含本轮未提交的 P1 闭环代码、迁移、测试和文档。
- 当前重点：在已部署的 API 流式上传、孩子管理聚合和教材知识图谱上完成真实教材文件、Provider/浏览器/设备最终回归；iPad mini 6 已能启动并访问 API。教材 PDF 单文件上限为 `50 MiB`，解析 worker 使用受限私有 `curriculum/` 读取边界，分析 worker 使用 `curriculum-previews/` 私有原页和批准知识图谱。家长教材原页/知识审核、推荐详情和孩子端原页入口均已部署 Ubuntu；真实 PDF 多模态分析、发布和推荐验收待后续执行。
- 已完成：本地与 Ubuntu OpenAPI `0.11.0`、迁移 `0013`～`0025`、视觉四态候选与确认、可信 VerifiedQuestion → 云端递进 L1/L2 → 完整步骤/答案/验算、Mistake/Review closeout，以及 PDF 私有原页、分批多模态教材理解、全书知识图谱、家长批准和“批准知识点 + 全部开放错题”的来源受限推荐。
- 当前未完成：真实 118 页 PDF 多模态知识质量/费用/重试验收、浏览器 E2E、实际相机四态闭环、教材个人信息自动门禁、自动视觉检测器、四设备回归、正式依赖/镜像安全扫描、监控告警和已批准的 RPO/RTO。NewAPI 合成完整解答已现场通过；云端教材分析、L1/L2 和推荐 planner 尚未进行真实 Provider 质量/成本验收。
- 新产品主线已完成代码收口：ADR-0020/PLAN-0014 的错题、复习、教材和 Tutor 关键事实链已接通；PLAN-0016 进入设备/E2E/发布验收阶段，ADR-0021 已接受。
- Web 多孩子现状：账号与档案已由孩子管理聚合 API/Web 统一创建、列表和删除；全局顶栏通过 `?child=` 切换并在工作台、教材、孩子管理间保持同一孩子作用域，侧栏只保留三个顶层目的地。2026-07-23 已用双孩子合成会话完成 1214×805 参考图/实现图同屏浏览器 QA；真实 PostgreSQL 浏览器 E2E 和设备验收仍待完成。目标是产品/API 聚合而非物理合表，详见 PLAN-0013。
- 教材实际消费状态：新上传只接受不含个人信息的 PDF；`material-parse-worker` 抽取辅助文字且不丢弃无文字页，`curriculum-analysis-worker` 私有渲染原页并按最多 4 页一批交给单一 NewAPI，再归纳整本章节/知识点/目标/先修关系/练习。家长对照原页批准后才能发布；Tutor 只读最小已批准片段，任务推荐遍历全部开放错题和已批准知识点/具体练习，不再从 `CurriculumChunk.text` 抽题。批准任务写入视觉说明、页码和孩子 Session 原页入口。
- 2026-07-24 部署状态：已保留远端 `.env`、卷与经过隔离恢复验证的 PostgreSQL/MinIO 备份，成对重建 API/Web/迁移与五个 worker。API `0.11.0`、Alembic `0025_curriculum_knowledge_map`、API/Web healthcheck、教材分析/原页 OpenAPI 路径均通过，MinIO `9000` 未向宿主暴露；真实家庭 PDF 未上传。
- 当前认证：只有家长/孩子用户名密码、Argon2id 和可撤销不透明会话；Web 使用 HttpOnly Cookie/CSRF，Flutter 使用平台安全存储。Ubuntu LAN 登录、首次改密和 Nova 9 绑定档案读取已有实机记录；浏览器自动 E2E 和多设备重启生命周期仍待验收。
- Android 设备验收：Nova 9 登录/首次改密/绑定档案历史记录有效；流式上传新链路已部署但最终拍题、上传进度、Extraction/VerifiedQuestion、权限拒绝恢复、账号切换、弱网和重启仍需设备在场时验收。

## 3. 已验证的仓库事实

- 仓库根目录：`/Users/ybh/PycharmProjects/study`。
- Git：分支 `master`，最近提交 `c86490f`；工作区有本轮未提交的 P1 闭环、迁移、客户端和文档改动。
- 现有内容：根目录上下文文档、`prompts/` 工作流模板、`docs/adr/0000-template.md`、`家庭AI学习助手_架构设计_v1.0.docx`。
- 已创建并验证：`apps/`、`services/`、`packages/`、`evals/`、`infra/` 的 P0/P1 核心路径、配置、锁文件、测试和 Compose；Flutter Android release APK 与 iOS release 无签名 Runner.app 已构建。Ubuntu VM 上的 amd64 完整栈运行 API `0.11.0`/迁移 `0025`，新流式上传、孩子管理、PDF 解析、错题闭环、私有原页、知识图谱和来源受限推荐已部署；NewAPI synthetic 完整解答已成功，真实 L1/L2/智能规划质量仍待实测；ARM 调试镜像因 PaddlePaddle 3.3.1 无 Linux aarch64 wheel 而不含旧本地 OCR。
- 设计稿：31 个段落、6 个表格、3 页，定义 P0/P1/P2、设备职责、核心实体/API 和发布门槛；本地渲染缺少部分中文字体，但 OOXML 文本可完整提取。

## 4. 主文档索引

| 主题 | 唯一事实来源 | 当前状态 |
| --- | --- | --- |
| 项目目标、范围、设备、环境 | `PROJECT.md` | Active；目标与现状已分离 |
| P1 产品需求与验收 | `PRD.md` | Draft；待产品 Owner 审批 |
| 当前任务 | `TASK.md` | TASK-0010/PLAN-0018 已部署 `0.11.0`/`0025`；等待真实 118 页教材/NewAPI、浏览器与原页设备人工验收 |
| 复杂任务计划 | `PLANS.md` | PLAN-0012 已部署并等待最终验收；PLAN-0013 API/Web 首版已部署、浏览器 E2E 待执行；PLAN-0014 已完成教材/三入口/四态/建议首版，真实文件与最终联调待执行；PLAN-0011 已完成 |
| 系统结构、数据流、接口 | `ARCHITECTURE.md` | P0/P1 单家庭核心闭环已实现；残余边界明确记录 |
| 测试命令和质量门槛 | `TESTING.md` | API/Web/Flutter 质量命令已有验证；原生构建结果以最新记录为准 |
| 儿童数据、权限与 AI 安全 | `SECURITY.md` | 基线草案；生产开放项未决 |
| 部署、回滚、告警与恢复 | `RUNBOOK.md` | Ubuntu 自用部署与恢复已验证；监控/公网发布未建立 |
| 架构决策 | `DECISIONS.md`、`docs/adr/` | ADR-0020～0023 教材驱动错题、多模态知识图谱和来源推荐 Accepted；ADR-0018 Accepted；ADR-0019 Proposed；替代关系见索引 |
| 工作队列 | `TODO.md` | TODO-014/015 In Progress 并已部署；TODO-016/018/019/020 的本地实现由 PLAN-0016/0017/0018 收口，等待真实部署和 E2E |
| 已发布变化 | `CHANGELOG.md` | 无产品发布 |
| 原始设计基线 | `家庭AI学习助手_架构设计_v1.0.docx` | v1.0；后续 ADR 可替代 |

## 5. 技术摘要

- 客户端：Flutter iOS/Android；Next.js + TypeScript Web/PWA；端侧 SQLite。
- 后端：Python 3.12 + FastAPI 模块化单体 + 异步 Worker。
- 数据：PostgreSQL 为业务事实源；pgvector 做检索；Redis 做缓存/队列；私有 S3/MinIO 存图片。本地新链路仅由 API/worker 通过内部网络访问；Ubuntu `0.11.0` 已完成流式上传、教材解析、私有原页、知识图谱和私有 MinIO 成对迁移。
- 契约：`packages/contracts` 的 OpenAPI 已到 `0.11.0`，增加受鉴权教材原页、全书知识图谱和知识点/视觉题来源；SDK 生成器尚未选择。
- AI：本地 PrivacySanitizer、固定 OCR/脱敏/Tutor eval、NewAPI Adapter、ImageAnalysis/CurriculumAnalysis worker、QuestionExtraction/VerifiedQuestion 和服务端可信 TutorTurn 已实现；教材页图有界分批后形成待家长批准的知识图谱，L1/L2 使用已确认文字和最小已批准教材片段，推荐由 NewAPI 在本地来源候选上规划。教材个人信息自动门禁、自动视觉检测器与云端教材/提示/推荐真实质量验收仍未完成。
- 交付：Ubuntu 自用 Compose 已部署并完成迁移、健康、NewAPI synthetic 和 PostgreSQL/MinIO 恢复验收；OpenTelemetry、正式告警和公网发布未实现。
- 认证：ADR-0017 已实现代码目标：同一 Household 内家长/孩子账号密码 + 可撤销不透明会话；Web 用 HttpOnly Cookie/CSRF，Flutter 用平台安全存储；不接入短信、邮箱、社交登录、OIDC 或 MFA，也不保留 HMAC/Demo 兼容。
- 学习主线：ADR-0020/0023 已批准 CurriculumAssignment/Material/Snapshot → 私有原页/KnowledgeMap 批准 → VerifiedQuestion+已确认 AttemptEvidence（`worked` 或确认空白）→ 分模式 Tutor → MistakeRecord/ReviewSchedule → TaskRecommendation；本地代码已接通拍题 closeout、证据化复习、多模态教材知识/grounding、L1/L2 递进和来源原页，当前剩余真实部署、Provider/设备和发布门槛验收。

## 6. 仓库地图

| 路径 | 责任 | 当前状态 |
| --- | --- | --- |
| `apps/child_flutter` | 孩子学习、拍题、提示交互、离线队列 | 真实任务/拍题/题目确认/Tutor、数学三入口、视觉四态、完整解答、到期复习、来源题视觉说明和受鉴权教材原页已实现；最终设备回归待完成 |
| `apps/web` | 家长后台、内容维护、Windows Web/PWA | 方案 1 现代后台、登录、任务/周报、逐题详情、聚合孩子管理、PDF 上传、教材原页/整本知识图谱审核、发布和任务推荐审批已实现；真实教材 Provider 结果与真实数据库浏览器 E2E 待完成 |
| `services/api` | FastAPI 模块化单体和 Worker | 已到 0017～0025，增加 PDFium 私有页图、NewAPI 教材分析 worker、知识图谱批准和知识点推荐；Ubuntu 为 0025 |
| `packages/contracts` | OpenAPI、JSON Schema、生成 SDK | `0.11.0` 已增加受鉴权教材原页、知识图谱、视觉题上下文和知识点引用；SDK 生成器尚未固定 |
| `evals` | 固定 AI 质量/安全/成本评测 | OCR、6-case PrivacySanitizer、5-case offline Tutor Policy 和真实 NewAPI synthetic 完整解答已有；真实云端 L1/L2/推荐质量与自动视觉检测器 eval 待补充 |
| `infra/compose` | PostgreSQL/Redis/MinIO/API/Web/迁移/worker 编排 | 本地与 Ubuntu Compose 均已取消 MinIO 宿主/LAN 端口；Ubuntu 当前 `0.11.0`/`0025`，持久化卷保留 |
| `docs/adr` | 架构决策 | ADR-0020～0023 Accepted；ADR-0018 Accepted；ADR-0019 Proposed；ADR-0010/0012/0014 Superseded，其余见索引 |
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
- 正式发布阻塞：自动视觉检测器、法域/正式告知、密钥/静态加密、SLO/RPO/RTO、监控告警、浏览器 E2E 和四设备回归；单家庭自用 LAN 部署已可运行。
- 最近完成：`PLAN-0011` 的可信 Tutor、SQLite 离线、会话/复习/周报、数据导出/删除、生命周期 worker、恢复演练和 Ubuntu 自用栈基础部署。
- 最近规划：`PLAN-0013` 已把“创建孩子合并账号/档案”和“首页切换当前孩子”拆成契约/迁移、API 事务、Web 管理页、工作台选择及双孩子 E2E 五阶段；前四阶段已实现并部署，双孩子 E2E 待执行。
- 最近实现：`PLAN-0018` 用 `0025` 和 OpenAPI `0.11.0` 替代残缺 PDF 文字抽题：私有原页 → 每批最多 4 页多模态理解 → 全书知识图谱 → 家长批准 → 错题/知识点来源受限任务。Web 原页/知识审核和孩子端 Session 原页入口已完成；真实部署、118 页 Provider 质量/成本和发布门槛仍待完成。

## 10. 更新规则

- 任务切换、首个 commit、远程仓库建立、代码路径/锁文件/CI 出现、架构或环境变化、里程碑完成后更新本文件。
- 只保留摘要和指针；稳定详情回到对应主文档。
- 已批准决策进入 ADR，已发布的用户/运维变化进入 `CHANGELOG.md`，未执行工作进入 `TODO.md`。
