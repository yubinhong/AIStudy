# AI_CONTEXT.md

> 面向 AI 的项目入口与当前快照。稳定详情以对应主文档为准；本文件只保留摘要、状态和导航。

## 1. 项目快照

- 项目：家庭 AI 学习助手
- 一句话目标：复用家庭现有设备，以数学为首科提供“家庭教材范围 → 错题讲解 → 错题沉淀 → 到期复习 → 今日任务/家长反馈”的开源、可控学习闭环。
- 当前阶段：`P1 SECURITY FOUNDATION / CURRICULUM-MISTAKE ROADMAP`
- 主要用户：小学阶段孩子与家长/监护人；辅助角色为家庭内容维护者和项目维护者。
- 生产状态：`SELF_HOSTED_DEPLOYED`（Ubuntu 单家庭 Compose 正在运行；不等同于公网/商业生产批准）
- 当前版本：API/OpenAPI `0.8.0`（尚无正式产品发布标签）
- 最近更新：`2026-07-18`

## 2. 当前工作状态

- 活动计划：`PLAN-0012` — Capture 服务端流式上传收敛已部署，活动任务仍为 `TASK-0009`；下一阶段是最终设备回归与 Provider 额度恢复后的识别验收。`PLAN-0013` 已完成 API/Web 首版并部署，`PLAN-0014` 已开始实现错题/复习最小闭环。
- 任务状态：ADR-0018/PLAN-0012 已完成本地与 Ubuntu API/Flutter/Compose/契约迁移；Ubuntu 不再依赖预签名直传，MinIO `9000` 未向宿主/LAN 暴露。最终真机仍未回归。
- 当前分支：`master`；工作区包含本轮未提交的 P1 闭环代码、迁移、测试和文档。
- 当前重点：在已部署的 API 流式上传和孩子管理聚合上完成真实设备/浏览器回归；同时保留 Provider HTTP `402` 的可操作错误提示，待 NewAPI 额度恢复后复验真实识别。
- 已完成：OpenAPI `0.8.0`、迁移 `0013`～`0017`、可信 VerifiedQuestion → TutorTurn、错题/复习最小闭环、会话完成/复习、周报、24 小时孩子数据导出、级联删除、SQLite 离线 Attempt 队列、真实任务/活动会话 Flutter 首页和家长任务/周报/导出 UI。Ubuntu Compose 运行 API/Web/ImageAnalysis/DataLifecycle worker，流式上传、孩子管理聚合和 PostgreSQL/MinIO 隔离恢复通过。
- 当前未完成：最终设备回归、浏览器 E2E、Provider 额度恢复后的真实识别、自动视觉检测器、四设备最终权限/弱网/横竖屏/重启回归、正式依赖/镜像安全扫描、监控告警和已批准的 RPO/RTO。SDK 生成器仍未选择。
- 新产品主线部分完成：ADR-0020/PLAN-0014 已新增 `MistakeRecord`/`ReviewSchedule`、`0017` 迁移、到期查询、确定性复习和 Web/Flutter 调用；仍没有教材导入/审核发布、CurriculumSnapshot、作答四态/错因讲解、任务建议或 Flutter“数学三入口”。
- Web 多孩子现状：账号与档案已由孩子管理聚合 API/Web 首版统一创建、列表和删除；首页支持 `?child=` 并按所选孩子过滤任务/周报。双孩子浏览器 E2E 和真实设备验收仍待完成；目标是产品/API 聚合而非物理合表，详见 PLAN-0013。
- 当前认证：只有家长/孩子用户名密码、Argon2id 和可撤销不透明会话；Web 使用 HttpOnly Cookie/CSRF，Flutter 使用平台安全存储。Ubuntu LAN 登录、首次改密和 Nova 9 绑定档案读取已有实机记录；浏览器自动 E2E 和多设备重启生命周期仍待验收。
- Android 设备验收：Nova 9 登录/首次改密/绑定档案历史记录有效；流式上传新链路已部署但最终拍题、Extraction/VerifiedQuestion、权限拒绝恢复、弱网和重启仍需设备在场时验收。

## 3. 已验证的仓库事实

- 仓库根目录：`/Users/ybh/PycharmProjects/study`。
- Git：分支 `master`，最近提交 `c86490f`；工作区有本轮未提交的 P1 闭环、迁移、客户端和文档改动。
- 现有内容：根目录上下文文档、`prompts/` 工作流模板、`docs/adr/0000-template.md`、`家庭AI学习助手_架构设计_v1.0.docx`。
- 已创建并验证：`apps/`、`services/`、`packages/`、`evals/`、`infra/` 的 P0/P1 核心路径、配置、锁文件、测试和 Compose；Flutter Android release APK 与 iOS release 无签名 Runner.app 已构建。Ubuntu VM 上的 amd64 完整栈运行 API `0.8.0`/迁移 `0016`，新流式上传和孩子管理聚合已部署；synthetic 识别请求到达 NewAPI 但返回 HTTP `402`，因此实际 Provider 识别尚待额度恢复；ARM 调试镜像因 PaddlePaddle 3.3.1 无 Linux aarch64 wheel 而不含旧本地 OCR。
- 设计稿：31 个段落、6 个表格、3 页，定义 P0/P1/P2、设备职责、核心实体/API 和发布门槛；本地渲染缺少部分中文字体，但 OOXML 文本可完整提取。

## 4. 主文档索引

| 主题 | 唯一事实来源 | 当前状态 |
| --- | --- | --- |
| 项目目标、范围、设备、环境 | `PROJECT.md` | Active；目标与现状已分离 |
| P1 产品需求与验收 | `PRD.md` | Draft；待产品 Owner 审批 |
| 当前任务 | `TASK.md` | TASK-0009 代码/自动化/Ubuntu 完成；等待最终真机相机人工验收与 Provider 额度恢复 |
| 复杂任务计划 | `PLANS.md` | PLAN-0012 已部署并等待最终验收；PLAN-0013 API/Web 首版已部署、浏览器 E2E 待执行；PLAN-0014 已完成错题/复习最小闭环，教材/三入口/建议待实现；PLAN-0011 已完成 |
| 系统结构、数据流、接口 | `ARCHITECTURE.md` | P0/P1 单家庭核心闭环已实现；残余边界明确记录 |
| 测试命令和质量门槛 | `TESTING.md` | API/Web/Flutter 质量命令已有验证；原生构建结果以最新记录为准 |
| 儿童数据、权限与 AI 安全 | `SECURITY.md` | 基线草案；生产开放项未决 |
| 部署、回滚、告警与恢复 | `RUNBOOK.md` | Ubuntu 自用部署与恢复已验证；监控/公网发布未建立 |
| 架构决策 | `DECISIONS.md`、`docs/adr/` | ADR-0020 教材驱动错题主线 Accepted；ADR-0018 Accepted；ADR-0019 孩子管理聚合/工作台作用域 Proposed；替代关系见索引 |
| 工作队列 | `TODO.md` | TODO-014/015 In Progress 并已部署；TODO-016 教材/知识发布 Ready；TODO-017 错题讲解 Planned；TODO-018 错题/复习最小闭环已实现、完整体验待补；TODO-019 Planned |
| 已发布变化 | `CHANGELOG.md` | 无产品发布 |
| 原始设计基线 | `家庭AI学习助手_架构设计_v1.0.docx` | v1.0；后续 ADR 可替代 |

## 5. 技术摘要

- 客户端：Flutter iOS/Android；Next.js + TypeScript Web/PWA；端侧 SQLite。
- 后端：Python 3.12 + FastAPI 模块化单体 + 异步 Worker。
- 数据：PostgreSQL 为业务事实源；pgvector 做检索；Redis 做缓存/队列；私有 S3/MinIO 存图片。本地新链路仅由 API/worker 通过内部网络访问；Ubuntu `0.8.0` 已完成成对迁移。
- 契约：`packages/contracts` 已有 P0 健康/Profile/Device 和 P1 Learning/Capture/Account Session/Tutor/Report/Export `0.8.0` 合同；SDK 生成方向已由 ADR-0002 接受，具体生成器尚未选择。
- AI：本地 PrivacySanitizer、固定 OCR/脱敏/Tutor eval、NewAPI Adapter、ImageAnalysis worker、QuestionExtraction/VerifiedQuestion 和服务端可信 TutorTurn 已实现；Ubuntu synthetic 大图完成真实单 Provider 链路。自动视觉检测器与外部 Tutor Provider 未实现，后者保持零成本离线策略。
- 交付：Ubuntu 自用 Compose 已部署并完成迁移、健康、NewAPI synthetic 和 PostgreSQL/MinIO 恢复验收；OpenTelemetry、正式告警和公网发布未实现。
- 认证：ADR-0017 已实现代码目标：同一 Household 内家长/孩子账号密码 + 可撤销不透明会话；Web 用 HttpOnly Cookie/CSRF，Flutter 用平台安全存储；不接入短信、邮箱、社交登录、OIDC 或 MFA，也不保留 HMAC/Demo 兼容。
- 学习主线：ADR-0020 已批准 CurriculumAssignment/Material/Snapshot → VerifiedQuestion+已确认 AttemptEvidence（`worked` 或 `blank_confirmed`）→ 分模式 Tutor → MistakeRecord/ReviewSchedule → TaskRecommendation；当前已写入 `MistakeRecord`/`ReviewSchedule` OpenAPI/`0017` 迁移，教材/作答证据/任务建议仍未实现。

## 6. 仓库地图

| 路径 | 责任 | 当前状态 |
| --- | --- | --- |
| `apps/child_flutter` | 孩子学习、拍题、提示交互、离线队列 | 当前真实任务/拍题/题目确认/最小 Tutor 和 API 单次流式上传已实现；数学三入口、题目+作答区拍摄/状态确认、错题本和到期复习尚未实现 |
| `apps/web` | 家长后台、内容维护、Windows Web/PWA | 学习概览、登录、任务/周报及分离账号/档案管理已实现；聚合孩子、教材导入审核发布、任务建议审批尚未实现 |
| `services/api` | FastAPI 模块化单体和 Worker | Capture/VerifiedQuestion/Tutor/Report 基础及本地流式上传已实现；远端部署收口与 Curriculum/Material/Mistake/Review/Recommendation 模块尚未实现 |
| `packages/contracts` | OpenAPI、JSON Schema、生成 SDK | 健康 + Profile/Device + Learning/Capture/OCR/Account Session/Tutor/Report/Export `0.8.0` 合同已改为单一流式上传，SDK 生成器尚未固定 |
| `evals` | 固定 AI 质量/安全/成本评测 | OCR、6-case PrivacySanitizer、3-case offline Tutor Policy 和真实 NewAPI synthetic 大图验收已有；无真实数据，自动视觉检测器 eval 待实现后补充 |
| `infra/compose` | PostgreSQL/Redis/MinIO/API/Web/迁移/worker 编排 | 本地 Compose 已取消 MinIO 宿主/LAN 端口；Ubuntu 旧运行栈待部署匹配版本 |
| `docs/adr` | 架构决策 | ADR-0020 Accepted；ADR-0018 Accepted；ADR-0019 Proposed；ADR-0010/0012/0014 Superseded，其余见索引 |
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

- ADR-0001～0012 已由项目 Owner（用户）于 2026-07-13 接受，ADR-0013～0014 于 2026-07-14 接受，ADR-0015～0017 于 2026-07-15 接受，ADR-0018 于 2026-07-17 接受，ADR-0020 于 2026-07-18 接受；ADR-0019 仍为 Proposed。替代关系见 DECISIONS.md，设计稿不替代 ADR。
- 已接受决策覆盖模块边界、契约、离线、AI、身份、数据生命周期、工具链和部署恢复；本产品按自用部署推进，地区/商业化/第三方 IdP 暂不纳入当前实现；人工确认、备份恢复和实际 NewAPI synthetic 运行验证已完成。
- 最高风险：AI 错误/代答、儿童数据泄露、离线记录覆盖、四端范围失控、P0 骨架与目标架构漂移。
- 正式发布阻塞：自动视觉检测器、法域/正式告知、密钥/静态加密、SLO/RPO/RTO、监控告警、浏览器 E2E 和四设备回归；单家庭自用 LAN 部署已可运行。
- 最近完成：`PLAN-0011` 的可信 Tutor、SQLite 离线、会话/复习/周报、数据导出/删除、生命周期 worker、恢复演练和 Ubuntu `0.8.0` 部署。
- 最近规划：`PLAN-0013` 已把“创建孩子合并账号/档案”和“首页切换当前孩子”拆成契约/迁移、API 事务、Web 管理页、工作台选择及双孩子 E2E 五阶段；前四阶段已实现并部署，双孩子 E2E 待执行。
- 最近决策：`ADR-0020` 已接受，`PLAN-0014` 将数学主线拆成教材发布、三入口/错题讲解、错题本/到期复习、任务建议和质量发布五阶段。当前已先落地错题/复习最小闭环；拍题作答四态、教材 grounding 和建议审批仍待后续阶段。

## 10. 更新规则

- 任务切换、首个 commit、远程仓库建立、代码路径/锁文件/CI 出现、架构或环境变化、里程碑完成后更新本文件。
- 只保留摘要和指针；稳定详情回到对应主文档。
- 已批准决策进入 ADR，已发布的用户/运维变化进入 `CHANGELOG.md`，未执行工作进入 `TODO.md`。
