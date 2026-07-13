# AI_CONTEXT.md

> 面向 AI 的项目入口与当前快照。稳定详情以对应主文档为准；本文件只保留摘要、状态和导航。

## 1. 项目快照

- 项目：家庭 AI 学习助手
- 一句话目标：复用家庭现有设备，提供“任务 → 作答 → 分步提示 → 错题/复习 → 家长反馈”的开源、可控、可离线学习闭环。
- 当前阶段：`P1 TASK/SESSION/OFFLINE FOUNDATION`
- 主要用户：小学阶段孩子与家长/监护人；辅助角色为家庭内容维护者和项目维护者。
- 生产状态：`NOT_DEPLOYED`
- 当前版本：`0.0.0（尚无产品发布）`
- 最近更新：`2026-07-13`

## 2. 当前工作状态

- 活动任务：无（`TASK-0005` 已完成）
- 最近完成：`TASK-0005` / `TODO-007` — 任务、会话、Attempt 与离线同步基础
- 当前分支：`master`；Git 已初始化但没有提交，全部文件未跟踪。
- 当前重点：保持 TASK-0005 完成记录可复现；ADR-0001～0009 已于 2026-07-13 接受。
- 阻塞项：真实认证、SDK 生成器、Flutter SQLite 落盘、真实设备断网、法域/保留/Provider/预算/SLO/RPO/RTO 仍待后续任务或确认。
- 下一检查点：由项目 Owner 选择下一项任务；不得把 local synthetic PostgreSQL 当作 staging/production 或真实儿童数据授权。

## 3. 已验证的仓库事实

- 仓库根目录：`/Users/ybh/PycharmProjects/study`。
- Git：分支 `master`，无 commit；当前所有项目文件均为 untracked。
- 现有内容：根目录上下文文档、`prompts/` 工作流模板、`docs/adr/0000-template.md`、`家庭AI学习助手_架构设计_v1.0.docx`。
- 已创建但未完全验证：`apps/`、`services/`、`packages/`、`evals/`、`infra/` 的 P0 骨架、家庭 Profile/Device 合成切片、配置样例、最小测试、Compose 和 CI；三类锁文件已生成，Flutter Android 调试 APK 和 iOS 无签名 Runner.app 已构建。
- 设计稿：31 个段落、6 个表格、3 页，定义 P0/P1/P2、设备职责、核心实体/API 和发布门槛；本地渲染缺少部分中文字体，但 OOXML 文本可完整提取。

## 4. 主文档索引

| 主题 | 唯一事实来源 | 当前状态 |
| --- | --- | --- |
| 项目目标、范围、设备、环境 | `PROJECT.md` | Active；目标与现状已分离 |
| P1 产品需求与验收 | `PRD.md` | Draft；待产品 Owner 审批 |
| 当前任务 | `TASK.md` | TASK-0005 已完成：Task/Session/Attempt 与离线同步基础 |
| 复杂任务计划 | `PLANS.md` | PLAN-0001～0005 已完成 |
| 系统结构、数据流、接口 | `ARCHITECTURE.md` | Draft 目标架构；P0 合成切片已实现 |
| 测试命令和质量门槛 | `TESTING.md` | API/Web/Flutter 质量命令已有验证；原生构建结果以最新记录为准 |
| 儿童数据、权限与 AI 安全 | `SECURITY.md` | 基线草案；生产开放项未决 |
| 部署、回滚、告警与恢复 | `RUNBOOK.md` | Not deployed；仅生产前契约 |
| 架构决策 | `DECISIONS.md`、`docs/adr/` | ADR-0001～0009 Accepted；仍保留真实数据/生产前置条件 |
| 工作队列 | `TODO.md` | TODO-001、TODO-003、TODO-007 已完成；后续任务待批准 |
| 已发布变化 | `CHANGELOG.md` | 无产品发布 |
| 原始设计基线 | `家庭AI学习助手_架构设计_v1.0.docx` | v1.0；后续 ADR 可替代 |

## 5. 技术摘要（目标，尚未实现）

- 客户端：Flutter iOS/Android；Next.js + TypeScript Web/PWA；端侧 SQLite。
- 后端：Python 3.12 + FastAPI 模块化单体 + 异步 Worker。
- 数据：PostgreSQL 为业务事实源；pgvector 做检索；Redis 做缓存/队列；S3/MinIO 存图片。
- 契约：`packages/contracts` 已有 P0 健康/Profile/Device 与 P1 Learning `0.3.0` 合同；SDK 生成方向已由 ADR-0002 接受，具体生成器尚未选择。
- AI：OCR/视觉/推理/低成本模型经 Provider Adapter；Tutor Policy 控制提示层级、安全、Schema 和成本。
- 交付：P0 Compose/CI 已创建；AI eval、OpenTelemetry 和部署仍未实现。
- 认证：家长拥有 Household；孩子使用 PIN/可撤销设备令牌；具体 IdP/TTL/MFA `TBD`。

## 6. 仓库地图

| 路径 | 责任 | 当前状态 |
| --- | --- | --- |
| `apps/child_flutter` | 孩子学习、拍题、提示交互、离线队列 | P0 骨架、平台目录和锁文件；通用待同步队列边界与 4 项测试已写，SQLite 未实现 |
| `apps/web` | 家长、内容维护、Windows Web/PWA | 合成孩子档案消费入口；质量门槛已通过 |
| `services/api` | FastAPI 模块化单体和 Worker | Profile/Device 合成 API；Learning 可切换至 PostgreSQL 事务仓储；Alembic 首迁移与 15 项 API 测试已验证 |
| `packages/contracts` | OpenAPI、JSON Schema、生成 SDK | 健康 + Profile/Device + Learning `0.3.0` 合同已写 |
| `evals` | 固定 AI 质量/安全/成本评测 | 占位边界已写，无真实数据 |
| `infra/compose` | 本地 PostgreSQL/Redis/MinIO/API 编排 | Docker Desktop 已准备；PostgreSQL 16.10 已启动且 healthy，Redis/MinIO 未启动 |
| `docs/adr` | 架构决策 | 模板 + ADR-0001～0009 Accepted |
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
| Capture | 单题图片及 OCR/结构化处理记录 | 整页作业自动批改 |
| Tutor Policy | 控制提问、提示层级、安全、Schema 和成本的版本化规则 | 某一模型的系统 Prompt |
| Provider Adapter | 隔离 OCR/AI 厂商接口的适配层 | 业务逻辑或事实来源 |
| MasterySnapshot | 可追溯、可重算的掌握度派生快照 | 模型直接给出的永久结论 |

## 9. 决策、风险与下一步

- ADR-0001～0009 已由项目 Owner（用户）于 2026-07-13 接受；设计稿仍不替代 ADR。
- 已接受决策覆盖模块边界、契约、离线、AI、身份、数据生命周期、工具链和部署恢复；真实数据、Provider、法域与 production 前置条件仍未解除。
- 最高风险：AI 错误/代答、儿童数据泄露、离线记录覆盖、四端范围失控、P0 骨架与目标架构漂移。
- 生产阻塞：法域/同意/保留、身份、密钥/加密、Provider 数据条款、SLO/RPO/RTO、告警/恢复。
- 最近完成：`TASK-0005` / `TODO-007`；仅实现 synthetic 数据的 Learning 持久化切片，不进入真实认证或儿童数据。

## 10. 更新规则

- 任务切换、首个 commit、远程仓库建立、代码路径/锁文件/CI 出现、架构或环境变化、里程碑完成后更新本文件。
- 只保留摘要和指针；稳定详情回到对应主文档。
- 已批准决策进入 ADR，已发布的用户/运维变化进入 `CHANGELOG.md`，未执行工作进入 `TODO.md`。
