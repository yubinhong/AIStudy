# AI_CONTEXT.md

> 面向 AI 的项目入口与当前快照。稳定详情以对应主文档为准；本文件只保留摘要、状态和导航。

## 1. 项目快照

- 项目：家庭 AI 学习助手
- 一句话目标：复用家庭现有设备，提供“任务 → 作答 → 分步提示 → 错题/复习 → 家长反馈”的开源、可控、可离线学习闭环。
- 当前阶段：`P1 CAPTURE/CORRECTION FOUNDATION`
- 主要用户：小学阶段孩子与家长/监护人；辅助角色为家庭内容维护者和项目维护者。
- 生产状态：`NOT_DEPLOYED`
- 当前版本：`0.0.0（尚无产品发布）`
- 最近更新：`2026-07-15`

## 2. 当前工作状态

- 活动任务：`TASK-0006` — Capture 与人工校正安全基础
- 任务状态：`IN_PROGRESS（2026-07-15）`
- 当前分支：`master`；最近提交 `c3a107e`，当前工作区含 OCR 入队/调度增量。
- 当前重点：项目 Owner 于 2026-07-15 接受 ADR-0015，将 Capture 目标路线改为“本地 PrivacySanitizer（OCR 只定位敏感信息）→ 用户确认不可逆脱敏副本 → 单一自托管/获批云端视觉 Provider 解析 → 人工确认题目 → Tutor”。随后明确 NewAPI 由项目 Owner 自行部署；本轮已实现不依赖云 Provider 的本地脱敏核心、Provider-neutral Schema、self-hosted Bearer 认证和 OpenAI-compatible NewAPI Adapter 边界。
- 已完成：本地 MinIO、图片安全读取/无 EXIF 规范化、授权/幂等/生命周期、人工校正和旧 PaddleOCR text/formula Job/结果链路均已实现并通过 synthetic 验证，可作为新路线的存储/校验基础和关闭的回滚 Provider；新增 `PrivacySanitizer` 实色覆盖/不可逆重编码、`LocalPrivacyDetector` 信号适配、`PrivacySanitization`/`ImageAnalysisJob`/`QuestionExtraction`/`VerifiedQuestion` Schema、6-case 固定脱敏评测、0008/0009 ImageAnalysis ledger/提取持久化/queued worker，以及 Flutter 本地预览/手动涂抹/确认后仅上传脱敏 PNG 并记录 analysis job 的客户端顺序和有限启动过渡。Web 家长工作台已读取 children/tasks/devices 并通过生产构建；无 Provider 的 `offline-tutor-policy.v1` 已提供 1～3 级提示和 3-case eval。上传确认已核验对象实际 SHA-256；新增自用 HMAC Bearer 令牌脚本、API Bearer 校验和 OpenAI-compatible NewAPI 结构化视觉 Adapter，Adapter 默认关闭且不记录原始 Provider 内容。Compose worker 已进入默认 profile，Provider 关闭时安全空闲；Linux ARM64 调试镜像已原生构建。
- 当前未完成：QuestionExtraction 已形成服务端持久化和读取接口，但人工确认生成 VerifiedQuestion 的接口、临时脱敏副本清理、视觉固定 eval、备份恢复和实际 NewAPI 运行验证仍待完成。自用模式允许在本机部署后使用真实数据，但必须只上传确认且哈希绑定的脱敏副本；原图仍不外发。
- 后续已批准：ADR-0017/PLAN-0007 将以家长/孩子账号密码、Argon2id 和可撤销不透明会话替换 HMAC Bearer；家长 Web 提供首次改密和孩子账号管理，Flutter 提供孩子登录。空数据库的一次性 `admin/admin123456` 只允许本机首次登录，改密前阻断家庭数据。该工作为 `TODO-012`，当前 TASK-0006 未结束，因此没有认证代码、合同或迁移变更。

## 3. 已验证的仓库事实

- 仓库根目录：`/Users/ybh/PycharmProjects/study`。
- Git：分支 `master`，最近提交 `c3a107e`；工作区有本轮未提交的 API、迁移与文档改动。
- 现有内容：根目录上下文文档、`prompts/` 工作流模板、`docs/adr/0000-template.md`、`家庭AI学习助手_架构设计_v1.0.docx`。
- 已创建并部分验证：`apps/`、`services/`、`packages/`、`evals/`、`infra/` 的 P0 骨架、家庭 Profile/Device 合成切片、配置样例、最小测试、Compose 和 CI；三类锁文件已生成，Flutter Android 调试 APK 和 iOS 无签名 Runner.app 已构建。自用 Compose 的 `linux/amd64` 发布镜像和原生 `linux/arm64` 调试镜像均已在 macOS arm64 Docker 构建通过；ARM 调试镜像因 PaddlePaddle 3.3.1 无 Linux aarch64 wheel 而不含旧本地 OCR，完整 Compose 启动与真实 NewAPI 联调仍待执行。
- 设计稿：31 个段落、6 个表格、3 页，定义 P0/P1/P2、设备职责、核心实体/API 和发布门槛；本地渲染缺少部分中文字体，但 OOXML 文本可完整提取。

## 4. 主文档索引

| 主题 | 唯一事实来源 | 当前状态 |
| --- | --- | --- |
| 项目目标、范围、设备、环境 | `PROJECT.md` | Active；目标与现状已分离 |
| P1 产品需求与验收 | `PRD.md` | Draft；待产品 Owner 审批 |
| 当前任务 | `TASK.md` | TASK-0006 进行中：Capture 与人工校正安全基础 |
| 复杂任务计划 | `PLANS.md` | PLAN-0001～0005 已完成；PLAN-0006 进行中；PLAN-0007 账号密码认证已规划、未执行 |
| 系统结构、数据流、接口 | `ARCHITECTURE.md` | Draft 目标架构；P0 合成切片已实现 |
| 测试命令和质量门槛 | `TESTING.md` | API/Web/Flutter 质量命令已有验证；原生构建结果以最新记录为准 |
| 儿童数据、权限与 AI 安全 | `SECURITY.md` | 基线草案；生产开放项未决 |
| 部署、回滚、告警与恢复 | `RUNBOOK.md` | Not deployed；仅生产前契约 |
| 架构决策 | `DECISIONS.md`、`docs/adr/` | ADR-0001～0011、0013～0017 Accepted；ADR-0012 Superseded；ADR-0017 账号/会话目标未实现 |
| 工作队列 | `TODO.md` | TODO-001、TODO-003、TODO-007 已完成；TODO-012 账号密码认证已规划，等待当前任务结束 |
| 已发布变化 | `CHANGELOG.md` | 无产品发布 |
| 原始设计基线 | `家庭AI学习助手_架构设计_v1.0.docx` | v1.0；后续 ADR 可替代 |

## 5. 技术摘要（目标，尚未实现）

- 客户端：Flutter iOS/Android；Next.js + TypeScript Web/PWA；端侧 SQLite。
- 后端：Python 3.12 + FastAPI 模块化单体 + 异步 Worker。
- 数据：PostgreSQL 为业务事实源；pgvector 做检索；Redis 做缓存/队列；S3/MinIO 存图片。
- 契约：`packages/contracts` 已有 P0 健康/Profile/Device、P1 Learning 与 Capture `0.5.0` 合同；SDK 生成方向已由 ADR-0002 接受，具体生成器尚未选择。
- AI：本地 PrivacySanitizer 核心使用版本化敏感区域信号做实色覆盖和不可逆重编码，视觉解析经 Provider Adapter；图片解析和 Tutor 分离，均需固定 Schema/人工确认。Provider-neutral Schema、6-case 脱敏 eval、无 Provider 的 1～3 级 offline Tutor Policy、3-case eval、NewAPI Adapter、ImageAnalysis worker 和 QuestionExtraction 持久化已实现；真实检测器、VerifiedQuestion 确认接口和视觉固定 eval 尚未实现。
- 交付：P0 Compose/CI 已创建；旧 OCR、PrivacySanitizer 和 offline Tutor Policy synthetic eval 已实现，云 Provider eval、OpenTelemetry 和部署仍未实现。
- 认证：ADR-0017 目标为同一 Household 内家长/孩子账号密码 + 可撤销不透明会话；Web 用 HttpOnly Cookie/CSRF，Flutter 用平台安全存储；不接入短信、邮箱、社交登录、OIDC 或 MFA。当前代码仍使用 HMAC Bearer，目标尚未实现。

## 6. 仓库地图

| 路径 | 责任 | 当前状态 |
| --- | --- | --- |
| `apps/child_flutter` | 孩子学习、拍题、提示交互、离线队列 | 相机/相册、1.2 秒有限启动过渡、ADR-0015 本地脱敏预览/手动涂抹/确认、Bearer 注入和旧 OCR UI 已实现；PLAN-0007 孩子账号登录/安全会话存储、服务端 QuestionExtraction 人工确认和离线 SQLite 尚未实现 |
| `apps/web` | 家长后台、内容维护、Windows Web/PWA | 简洁明亮的学习概览工作台和 Bearer 环境注入已实现；PLAN-0007 的登录、首次改密、退出和孩子账号管理尚未实现 |
| `services/api` | FastAPI 模块化单体和 Worker | Capture/ImageAnalysis/NewAPI 与 HMAC Bearer 已实现；ADR-0017 的 Account/AuthSession、Argon2id、登录限速、首次改密和会话撤销尚未实现，题目人工确认、真实视觉检测器和脱敏副本删除也未实现 |
| `packages/contracts` | OpenAPI、JSON Schema、生成 SDK | 健康 + Profile/Device + Learning/Capture/OCR 结果读取 `0.5.0` 合同及 ADR-0015/0016 的 6 份 Schema 已写，SDK 生成器尚未固定 |
| `evals` | 固定 AI 质量/安全/成本评测 | 旧 OCR、6-case PrivacySanitizer 和 3-case offline Tutor Policy synthetic eval 已有；云视觉结构化/Tutor Provider eval 未实现，无真实数据 |
| `infra/compose` | 本地 PostgreSQL/Redis/MinIO/API/家长 Web/迁移/worker 编排 | Compose 配置展开通过且无额外 profile；ImageAnalysis worker 默认启动、Provider 关闭时安全空闲；amd64 发布镜像、无 Paddle 的 ARM64 调试镜像和 Web standalone 镜像已纳入编排，完整启动、备份恢复和监控仍待验证 |
| `docs/adr` | 架构决策 | 模板 + ADR-0001～0011、0013～0017 Accepted；ADR-0012 Superseded；ADR-0017 待实施 |
| `prompts` | Codex 工作流启动器 | 已存在 |

## 7. 不可违反的约束

- 孩子端低干扰；AI 先提问和提示，不直接代写；低置信度必须允许校正。
- Household 是强授权边界；儿童数据最小化；图片短期保存；支持导出/删除；真实数据/密钥不入库、日志、截图、测试或评测集。
- PostgreSQL 是业务事实源；Attempt/AuditEvent 追加写；写接口幂等；离线同步不能用最后写入覆盖学习历史。
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

- ADR-0001～0012 已由项目 Owner（用户）于 2026-07-13 接受，ADR-0013～0014 已于 2026-07-14 接受；2026-07-15 接受 ADR-0015 并替代 ADR-0012 的默认本地完整 OCR 路线，接受 ADR-0016 的 NewAPI 边界，并以 ADR-0017 替代其 HMAC 认证部分及 ADR-0005 的孩子 PIN/设备凭证默认方案。设计稿仍不替代 ADR。
- 已接受决策覆盖模块边界、契约、离线、AI、身份、数据生命周期、工具链和部署恢复；本产品按自用部署推进，地区/商业化/第三方 IdP 暂不纳入当前实现；人工确认接口、备份恢复和实际 NewAPI 运行验证仍未完成。
- 最高风险：AI 错误/代答、儿童数据泄露、离线记录覆盖、四端范围失控、P0 骨架与目标架构漂移。
- 生产阻塞：法域/同意/保留、ADR-0017 账号/会话实现和引导改密、密钥/加密、云视觉/Tutor Provider 数据条款/区域/训练退出/预算、PrivacySanitizer/用户确认/单 Provider/临时副本删除、固定 eval、SLO/RPO/RTO、告警/恢复。
- 最近完成：`TASK-0005` / `TODO-007`；`TASK-0006` 已完成 OCR 候选结果、家长图片生命周期、固定 synthetic OCR eval 和 local/CI 入队调度切片，仍不进入真实认证或儿童数据。

## 10. 更新规则

- 任务切换、首个 commit、远程仓库建立、代码路径/锁文件/CI 出现、架构或环境变化、里程碑完成后更新本文件。
- 只保留摘要和指针；稳定详情回到对应主文档。
- 已批准决策进入 ADR，已发布的用户/运维变化进入 `CHANGELOG.md`，未执行工作进入 `TODO.md`。
