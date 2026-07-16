# PROJECT.md — 家庭 AI 学习助手

## 文档信息

- 状态：`ACTIVE`（产品与目标架构已形成 v1.0 设计；P0 骨架、合成 Learning/Capture 切片和 ADR-0001～0011、0013～0017 已完成/接受；ADR-0012 已被替代；ADR-0017 认证方案待实现）
- Owner：`TBD（项目发起人确认）`
- 最后更新：`2026-07-15`
- 项目仓库：本地 Git 仓库 `/Users/ybh/PycharmProjects/study`；远程地址 `TBD（项目 Owner 确认）`
- 设计基线：`家庭AI学习助手_架构设计_v1.0.docx`

## 1. 项目概述

### 一句话说明

面向小学阶段家庭、可复用现有 iPad、Windows 和手机的开源 AI 学习助手，先打通“任务 → 作答 → 分步提示 → 错题沉淀 → 复习/家长反馈”的学习闭环。

### 要解决的问题

专用学习机采购成本高、软硬件和内容生态封闭，家庭难以控制模型、数据和学习规则；通用 AI 聊天工具又容易直接给答案，缺少任务管理、渐进式提示、错题复习、离线能力和家长可理解的长期反馈。本项目需要在家庭已有设备上提供低干扰、可审计、可自托管的学习体验。

### 为什么现在做

- 家庭已有 iPad mini 6、Windows 笔记本、iPhone 11 和华为 nova 9，可在不新增专用硬件的前提下验证多端协作。
- OCR、视觉模型和推理模型已能支持单题识别与分步辅导，Provider Adapter 可以降低对单一模型供应商的锁定。
- 开源、自托管和最小化儿童数据能够形成与商业学习机不同的产品价值。

## 2. 用户与利益相关者

| 角色 | 目标 | 主要痛点 | 决策权 |
| --- | --- | --- | --- |
| 小学生 | 独立完成当天任务，在需要时获得逐级提示 | 通用 AI 容易直接给答案；学习界面容易分心；弱网时进度可能丢失 | 可选择提示、校正识别结果、完成/跳过任务；不能修改家庭级策略 |
| 家长/监护人 | 安排任务并通过周报理解投入、完成率和薄弱点 | 多设备数据分散；难以判断孩子是在理解还是抄答案 | 家庭空间、孩子档案、任务、数据保留和模型/成本策略 |
| 内容维护者 | 维护教材版本、知识点映射和家庭导入内容 | 版权内容不可直接复制入库；跨科目扩展容易污染核心模型 | 内容导入和映射规则，不得越过家庭权限边界 |
| 项目维护者 | 以可替换、可测试的模块持续交付 | 多端、离线同步、AI 不确定性和儿童数据安全增加复杂度 | 技术实现、发布门槛和运维；产品/安全边界变化需记录决策 |

## 3. 目标与非目标

### 项目目标

- 在四类现有设备上完成清晰分工：iPad 为孩子主端，Windows Web/PWA 负责重输入与管理，两部手机作为家长伴随端或临时拍题端。
- 首版聚焦小学数学，实现每日任务、学习会话、单题拍照、本地隐私脱敏、云端视觉结构化、1～3 级分步提示、自动错题本、复习入口和可追溯家长周报。
- 采用模块化单体和 OpenAPI 契约起步，使客户端共享业务契约，并保留后续拆服务和科目插件化的空间。
- 支持弱网/离线队列、模型可替换、过程可审计、成本可观测和儿童数据最小化。
- 保持开源和可自托管，避免业务逻辑锁死在单一云、模型或专用硬件中。

### 非目标

- 不复制学而思等商业学习机的全学段课程、海量题库、教辅版权内容或专用护眼硬件体验。
- v1 不做整页作业自动批改、全科 OCR、直播课、完整排课、多学校/教师组织架构、公开排名或社交榜单。
- v1 不提供无限自由聊天、直接代写答案，或把未经校验的模型答案直接作为标准答案入库。
- Windows 原生 Flutter Desktop、语文/英语插件、语音和 Python 游戏化模块不属于 P1 MVP。

## 4. 成功指标

| 指标 | 基线 | 目标 | 时间窗口 | 数据来源 |
| --- | --- | --- | --- | --- |
| 核心学习闭环 | 尚无可运行产品 | “任务 → 作答 → 分步提示 → 错题 → 周报”核心 E2E 100% 通过 | P1 发布前 | E2E 与验收记录 |
| 多端覆盖 | 仅有目标设计 | iPad、Windows Web、iPhone、华为 Android 均完成职责内的弱网、横竖屏和权限回归 | P1 发布前 | 设备测试矩阵 |
| 离线可靠性 | 尚无实现 | 断网期间会话、Attempt 和上传队列不丢失，恢复联网后可幂等同步 | P1 发布前 | 离线/同步集成测试与审计事件 |
| AI 可控性 | 尚无实现 | 所有辅导响应满足固定 JSON Schema，记录模型、提示/策略版本、延迟和成本；低置信度结果进入人工校正 | P1 发布前及持续监控 | AI eval、结构化日志、成本指标 |
| 家长可理解性 | 尚无实现 | 每周报告可追溯到学习会话、错因和知识点，并给出复习建议及异常说明 | P1 验收周 | 周报验收样例与数据追溯测试 |
| 儿童数据治理 | 尚无实现 | 图片短期保存策略、家庭数据导出和删除流程均有自动化或演练记录 | P1 发布前 | 安全测试、删除/导出演练 |

## 5. 范围

### 当前范围（P0 + P1）

- 仓库与 CI 基础、OpenAPI 契约、家庭账号/孩子账号/设备身份模型和可观测性。
- 每日任务、学习会话、数学单题拍照与人工裁切、本地 PrivacySanitizer、脱敏预览/手动涂抹、单一获批云视觉 Provider 结构化与人工校正。
- Tutor Policy 约束下的渐进式提问、提示和讲解总结。
- 错因标签、知识点映射、错题沉淀、复习入口和家长周报。
- iPad/Android Flutter 子端、响应式 Web/PWA、端侧 SQLite 和离线上传队列。
- 模型 Provider Adapter、对象存储、关系数据、缓存/队列和审计事件。

### 明确排除

- 购买或研发专用学习硬件。
- 未获许可的教材、题库和教辅内容入库。
- 生产环境真实儿童数据用于本地开发、测试或 AI 评测。
- 未经监护人控制的儿童手机号注册、开放社交或实时监控。

### 后续候选（P2）

- 基于复习调度的掌握度模型。
- 语文、英语等科目插件，语音交互和内容插件生态。
- Python 编程启蒙的游戏化模块和受控沙箱。
- 有明确独立扩容需求后拆分模块化单体中的服务。

## 6. 技术基线

| 层 | 选型 | 版本 | 说明 |
| --- | --- | --- | --- |
| 孩子/移动端 | Flutter（iOS/Android） | Flutter stable `3.44.6`（`ADR-0007` Accepted）；`image_picker 1.2.3`、`crypto 3.0.7`（`ADR-0013/0014` Accepted） | iPad 为孩子主端；Android 不依赖 Google Play Services；首页内容在 1.2 秒有限启动过渡后方并行加载并遵循减少动态效果设置；相机/相册选择后已进入本地脱敏预览，可手动涂抹并确认生成脱敏 PNG/哈希后再上传；当前仍注入 HMAC Bearer，PLAN-0007 将改为孩子账号密码登录并把会话保存在 Keychain/Android Keystore |
| Web/PWA | Next.js + TypeScript | Next.js `16.2.10`（`ADR-0007` Accepted） | 家长后台和 Windows 首版入口；PLAN-0007 增加登录、强制首次改密、退出以及孩子账号创建/停用/重置 |
| API/Worker | Python + FastAPI + 异步 Worker | Python `3.12.x`、FastAPI `0.136.3`、boto3 `1.43.46`、Pillow `12.3.0`、PaddleOCR `3.7.0`、PaddlePaddle CPU `3.3.1` | 模块化单体；当前 Capture 已实现被 ADR-0015 替代的本地完整 OCR 路线及 MinIO/授权/人工确认/生命周期安全基础，并新增上传对象实际 SHA-256 核验、Provider-neutral PrivacySanitizer 核心、OCR/规则信号、receipt-only ImageAnalysis ledger/API、offline Tutor Policy API、五份 Schema 和 synthetic eval。Paddle 在 macOS ARM64 与 Linux x86_64 安装；Linux ARM64 调试镜像因锁定版本无 aarch64 wheel 而不包含该回滚能力。目标仍为本地检测 + 用户确认 + 单一获批云视觉解析；真实视觉检测器、云视觉/Tutor Provider、临时副本删除与云视觉固定 eval 尚未实现。现有 Paddle 版本是当前代码事实，不代表后续轻量隐私模型已选定 |
| 云端视觉/推理 | Provider Adapter + 固定 JSON Schema / Tutor Policy | 自用 NewAPI URL/key/model 通过环境注入；默认关闭 | 图片解析与 Tutor 分离；服务端只向单一自托管 Provider 发送用户确认的脱敏副本，不在客户端保存密钥，不自动跨 Provider 广播；NewAPI Adapter 和 ImageAnalysis worker 已实现，人工确认持久化/联调仍待完成 |
| 业务数据 | PostgreSQL + pgvector | `TBD（P0 锁定）` | PostgreSQL 是业务事实来源；目标同时保存 Account、Argon2id 密码哈希和 AuthSession 摘要；pgvector 仅用于知识检索，不替代关系数据 |
| 缓存/队列 | Redis | `TBD（P0 锁定）` | 不作为长期业务事实来源 |
| 文件 | 本地 MinIO / S3 兼容 Adapter | MinIO `RELEASE.2025-09-07T16-13-09Z`；boto3 `1.43.46` | 私有 Bucket、短期预签名 URL；保留策略和清理器见 ADR-0010/0011 |
| 端侧数据 | SQLite | 随 Flutter 依赖锁定 | 缓存今日任务、学习会话和上传队列 |
| 交付/可观测性 | Docker Compose、CI、OpenTelemetry | `TBD（P0 锁定）` | CI 覆盖 lint、test、契约测试与 AI eval；模型和 Prompt/Policy 版本化 |

## 7. 环境

| 环境 | 用途 | 访问方式 | 数据级别 | 部署来源 |
| --- | --- | --- | --- | --- |
| local | 本地开发、离线与多端联调 | `infra/compose/compose.yml` 编排 PostgreSQL、Redis、MinIO、API、家长 Web、迁移和默认 ImageAnalysis worker；配置展开、amd64 发布镜像、ARM64 调试镜像和 Web standalone 镜像已验证 | synthetic / 自用 restricted（需显式启用并自行承担生命周期） | 本地工作区 |
| staging | 集成、设备、AI 评测和迁移/恢复验证 | `TBD（P0/P1 建立）` | sanitized/synthetic | CI 产物，禁止从个人工作区直接发布 |
| production | 家庭正式使用 | `TBD（发布方案和 RUNBOOK 批准后建立）` | restricted | 仅允许已通过发布门槛的版本化产物 |

当前事实：Git 位于 `master`，最近提交为 `c3a107e`；P0 目标目录、入口、最小测试、Compose 配置、CI、三类锁文件、Profile/Device 合成 API 以及 Learning/Capture `0.5.0` 合同/语义已创建。ADR-0001～0011、0013～0017 已 Accepted，ADR-0012 已被 ADR-0015 替代；Learning/Capture/OCR/ImageAnalysis PostgreSQL migration/事务仓储、私有 MinIO 预签名上传、服务端对象确认（含实际 SHA-256）、过期清理、按 Household/Child 的 Capture 对象级联删除编排、local/CI 家长删除顺序、完整像素规范化、本地 OCR 候选结果、text/formula Job、ImageAnalysis queued worker、QuestionExtraction 持久化、API/迁移 `linux/amd64` 发布镜像、无 Paddle 的 `linux/arm64` 调试镜像和 Compose 配置展开均是已验证实现事实。Provider-neutral PrivacySanitizer 核心、OCR/规则信号、Schema、6-case synthetic 脱敏评测、Flutter 本地预览/手动涂抹/确认后脱敏 PNG+哈希上传、有限启动过渡、自用 Bearer 和 NewAPI Adapter 已新增；ADR-0017 的账号/密码/会话表、登录接口和 Web/Flutter 登录页尚未实现，当前运行时仍是 HMAC Bearer。真实视觉检测器、人工确认接口、临时脱敏副本清理、实际 NewAPI 联调、完整 Compose 启动、SQLite 落盘、生产 Profile/数据库与备份级联仍未完成。不得把未确认提取或认证计划描述成已实现。

现状修订（2026-07-15）：上一段中的“PrivacySanitization receipt/新 ImageAnalysis 接口未实现”是历史快照；当前已完成 `0008_image_analysis_job` receipt/API、`0009_question_extraction` 提取结果持久化、无 Provider `offline-tutor-policy.v1`、自用 Bearer 认证、NewAPI Adapter 和可开关 ImageAnalysis worker。Web 家长学习概览和 synthetic eval 已通过质量门槛；人工确认接口、真实 NewAPI 联调、SQLite 和备份恢复仍未完成。

认证规划修订（2026-07-15）：项目 Owner 接受 ADR-0017 和 PLAN-0007。目标是单家庭自用的家长/孩子账号密码与可撤销会话，不接入短信、邮箱、社交登录、OIDC 或 MFA。空账号库仅可初始化一次 `admin/admin123456`，只允许本机首次登录并强制改密；改密前不得读取家庭数据。该方案排在当前 TASK-0006 之后，尚未修改代码、OpenAPI、数据库或 Compose。

## 8. 仓库与服务边界

以下为 v1.0 设计确定的结构；P0 目录已创建，但除健康端点和空壳入口外的领域能力仍未实现。

| 模块/服务 | 目标路径 | 责任 | Owner | 依赖 |
| --- | --- | --- | --- | --- |
| 孩子端 | `apps/child_flutter` | 学习会话、拍题/相册选择、渐进提示交互、SQLite 与离线队列 | `TBD` | OpenAPI SDK、`image_picker`、端侧存储 |
| Web/PWA | `apps/web` | 家长端、内容维护、运营与 Windows 首版体验 | `TBD` | OpenAPI SDK、Web 认证 |
| 模块化 API | `services/api` | 身份、档案、计划、任务、捕获、本地隐私脱敏、云视觉解析、辅导、错题、掌握度、报告和通知 | `TBD` | PostgreSQL、Redis、对象存储、AI Provider |
| 跨端契约 | `packages/contracts` | OpenAPI、JSON Schema 和生成 SDK 的唯一契约来源 | `TBD` | API 与所有客户端 |
| AI 评测 | `evals` | 固定评测集，比较质量、安全、成本和延迟 | `TBD` | 模型/Prompt/Policy 版本 |
| 本地基础设施 | `infra/compose` | PostgreSQL、Redis、MinIO、API、家长 Web 和 worker 等本地编排 | `TBD` | Docker Compose |
| 架构决策 | `docs/adr` | 记录不可轻易撤销的工程和产品决策 | 项目维护者 | `DECISIONS.md` |

## 9. 约束与假设

### 硬约束

- 法规/合规：儿童数据最小化；家长拥有家庭空间；家长和孩子使用家庭内账号密码而非被强制要求手机号；自用版不接入短信、邮箱或 MFA；支持数据导出和删除。适用法域及正式保留周期仍需在上线前由 Owner 确认。
- 内容版权：教材、题库和教辅内容未经授权不得入库或随开源代码分发。
- 成本：优先复用现有设备；AI 调用必须有模型路由、成本上限和可观测性。
- 安全：密钥、真实用户数据和学习图片不得进入代码库、日志明文、截图或测试夹具。
- 可靠性：写接口支持幂等；Attempt/AuditEvent 采用追加写；任务状态按服务端版本合并，不得用简单最后写入覆盖学习记录。
- AI 行为：先提问和提示，不抢先给答案；输出受 JSON Schema 和 Tutor Policy 约束；低置信度内容必须允许人工校正。
- 兼容性：P1 必须覆盖 iPad mini 6、Windows Web/PWA、iPhone 11 和不依赖 GMS 的华为 nova 9。
- 截止时间：`TBD（当前设计未给出日期承诺）`。

### 已接受假设

- `ASSUMPTION-01`：家庭愿意复用现有四类设备；验证方式：P0 在 iPad 与 Windows Web 共享同一孩子档案，P1 完成四端职责测试。
- `ASSUMPTION-02`：数学单题“本地自动脱敏 + 用户确认 + 云视觉结构化 + 题目确认”可在可接受隐私、延迟和成本内支持首版闭环；验证方式：用固定 synthetic 脱敏/题型集分别衡量漏检、误遮挡、Schema 成功率、人工校正、延迟和单题成本。真实数据前仍须批准 Provider 条款与法域。
- `ASSUMPTION-03`：模块化单体能满足 P0/P1 容量；验证方式：持续采集模块延迟与负载，仅在独立扩容证据出现后提拆分 ADR。
- `ASSUMPTION-04`：家长周报比实时监控更符合产品原则；验证方式：用可追溯样例进行家庭验收，不新增儿童实时监控。

## 10. 里程碑

| 里程碑 | 结果 | 负责人 | 目标日期 | 状态 |
| --- | --- | --- | --- | --- |
| P0｜基础 | 建立仓库、OpenAPI、家庭/孩子/设备、CI 和可观测性；iPad 与 Windows Web 共享孩子档案 | `TBD` | `TBD` | 未开始 |
| P1｜MVP | 交付任务、会话、拍题、分步提示、错题、周报和离线队列；四端各司其职且断网不丢 | `TBD` | `TBD` | 未开始 |
| P2｜增强 | 交付复习调度、掌握度、科目插件、语音和 Python 游戏化模块；插件不修改核心任务/会话模型 | `TBD` | `TBD` | 候选 |

## 11. 项目级风险

| 风险 | 可能性 | 影响 | 缓解措施 | Owner |
| --- | --- | --- | --- | --- |
| 脱敏漏检、云视觉误解析或模型直接泄露答案 | H | H | 原图不外发、单题裁剪/自动脱敏/用户确认、单 Provider、题目人工校正、Tutor Policy、分级提示、结构化输出、固定 eval 和全链路审计 | `TBD` |
| 儿童图片或学习数据过度采集/保留 | M | H | 最小采集、短期图片、家长控制、导出/删除、日志脱敏和发布前演练 | `TBD` |
| 离线同步覆盖或重复学习记录 | M | H | 追加写、幂等键、服务端版本合并、重连与并发测试 | `TBD` |
| 四端适配导致 MVP 范围失控 | H | M | 固定设备职责；Windows 原生端后置；手机不承担长时孩子学习 | `TBD` |
| 目标架构先于工程基线，文档与实现漂移 | H | M | P0 先建立锁文件、CI 和契约；每次里程碑刷新 `AI_CONTEXT.md` 和本文件 | `TBD` |
| 第三方模型价格、能力或可用性变化 | M | M | Provider Adapter、模型路由、成本上限、降级策略和可替换评测 | `TBD` |

## 12. 相关文档

- 产品与技术设计基线：`家庭AI学习助手_架构设计_v1.0.docx`
- 产品需求：`PRD.md`（P1 MVP 草案，待 Owner 审批）
- 架构：`ARCHITECTURE.md`（目标架构，尚未实现）
- 安全：`SECURITY.md`（基线策略，生产细节仍有开放项）
- 测试：`TESTING.md`（目标质量门槛；代码初始化后绑定并验证真实命令）
- 决策：`DECISIONS.md` 与 `docs/adr/`
- 当前任务：`TASK.md`
