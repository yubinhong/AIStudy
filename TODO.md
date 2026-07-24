# TODO.md

> 工作队列，不是实施说明。项目已有 P0/P1 基础实现，当前以 `TASK.md` 的活动任务为唯一执行项；进入执行的待办必须移入 `TASK.md`，一次只保留一个活动任务。

## Now — 建议优先进入执行

| ID | 事项 | 价值/原因 | 优先级 | Owner | 依赖 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| TODO-001 | 建立 P0 最小可运行仓库骨架与质量门槛 | 让目标路径、依赖锁、健康端点、测试和 CI 首次成为可验证事实；不实现完整 MVP | P0 | `TBD（技术负责人）` | Owner/远程仓库；工具链决策 | Done（TASK-0002，原生平台构建待环境补齐） |
| TODO-002 | 起草并批准核心 ADR | 模块化单体、契约生成、离线同步、AI Provider/Tutor Policy、儿童身份/数据和工具链需要可追溯决策 | P0 | 项目 Owner（用户） | 无 | Done（TASK-0004；ADR-0001～0008 于 2026-07-13 Accepted） |
| TODO-003 | 交付家庭/孩子/设备 + OpenAPI 的首个纵向切片 | 达成 P0“iPad 与 Windows Web 共享孩子档案”的最小业务验收 | P0 | `TBD` | TODO-001、关键 ADR | Done（TASK-0003；合成切片，真实认证待后续） |

### TODO-001 推荐边界

- 创建 `apps/child_flutter`、`apps/web`、`services/api`、`packages/contracts`、`evals`、`infra/compose` 的最小结构。
- 锁定 Flutter/Node/Next.js/Python/数据库/镜像版本，提交唯一锁文件和 `.env.example`。
- 建立 API 健康端点、空壳 OpenAPI、Flutter/Web 最小消费者、格式/Lint/类型/单元命令和 CI。
- 建立 PostgreSQL/Redis/MinIO 本地 Compose 健康检查，不加入真实数据或 AI Provider。
- 验收以 `TESTING.md` 的命令能在干净环境运行并通过为准；不要在同一任务实现 Capture/Tutor/周报。

## Next — P0/P1 近期候选

| ID | 事项 | 价值/原因 | 优先级 | Owner | 进入条件 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| TODO-004 | 建立 staging 基线、SLO/容量/成本阈值和告警 | 把性能、成本和恢复从 TBD 变为可测门槛 | P1 | `TBD` | P0 纵向切片可运行 | Planned |
| TODO-005 | 完成儿童数据法域、同意、保留、导出/删除和备份决策 | 解除真实儿童数据和 production 阻塞 | P0 | `TBD（安全/法务/产品）` | Owner 与目标法域明确 | Planned |
| TODO-006 | 修复设计稿跨环境中文字体渲染 | 当前 LibreOffice 渲染缺字，影响后续设计稿维护/发布 | P2 | `TBD` | 确认目标阅读/发布环境 | Planned |
| TODO-007 | 实现任务/会话/Attempt 与离线同步 | 建立学习过程和断网不丢的核心底座 | P1 | Codex（执行） | ADR-0003 Accepted | Done（TASK-0005；synthetic PostgreSQL 事务与队列边界，真实设备离线待后续） |
| TODO-008 | 实现 Capture/本地隐私脱敏/云视觉解析/人工校正 | 支持数学单题输入，保证原图不外发并控制脱敏漏检、模型误解析和低置信度风险 | P1 | Codex（执行） | ADR-0011/0015/0016/0018 Accepted；ADR-0010 已被替代 | Done（TASK-0006/0009；人工确认、派生对象清理、MinIO/授权/生命周期、哈希门禁、固定 synthetic eval 和真实 NewAPI 合成大图联调已实现；上传传输收敛由 TODO-014/PLAN-0012 跟踪，真实视觉检测器与设备回归仍是明确风险） |
| TODO-009 | 实现 Tutor Policy、Provider Adapter 和固定 AI eval | 只消费人工确认的 VerifiedQuestion，提供分级提示并控制安全、Schema 和成本 | P1 | Codex（执行） | ADR-0015/0016；本地 NewAPI 可选，默认离线降级 | Done（PLAN-0011；Tutor 只按服务端 VerifiedQuestion ID 读取事实，1～3 级策略、Schema、幂等和追加写 TutorTurn 已实现并通过 synthetic/集成测试；外部 Tutor Provider 仍为可选后续插件） |
| TODO-010 | 实现错题、复习和可追溯周报 | 完成孩子学习到家长反馈的闭环 | P1 | Codex（执行） | Session/Tutor 数据稳定 | Done（PLAN-0011；会话完成结果、needs_review、TutorTurn 统计和家长周报聚合已实现；复杂知识点图谱/通知属于后续增强） |
| TODO-011 | 恢复可复现的 uv 可执行入口 | 当前临时 uv 路径已清理，依赖锁可用但标准 `uv` 命令不可发现 | P0 | `TBD` | 确认项目级或用户级 uv 安装策略 | Planned |
| TODO-012 | 收敛账号密码与可撤销会话认证 | 家长 Web 和孩子 Flutter 只保留用户名/密码入口，不能继续暴露 HMAC、Demo Header 或 Web 免登录旁路 | P0 | Codex（执行） | ADR-0017 Accepted；TASK-0007 / PLAN-0008 阶段 5a | Done（TASK-0007：HMAC/Demo/免登录和旧配置已删除，OpenAPI `0.6.0` 只保留 Session，Flutter 已支持登录前服务端地址配置；远端部署、浏览器和实体设备验收继续由 PLAN-0008 跟踪） |
| TODO-013 | 锁定移动端正式 App ID 与发布签名 | 当前 Android/iOS 仍使用 Flutter `com.example` 标识，Android release 为本地自用使用 debug 签名；擅自改变会生成新 App、清空原 App 安全会话并需要 Owner 证书/keystore | P0（正式分发前） | 项目 Owner + Codex | Owner 确认 Android applicationId、iOS bundle ID、Apple Team 与 Android keystore 安全位置 | Planned |
| TODO-014 | 将 Capture 改为 API 有界流式上传并关闭 MinIO LAN 入口 | 统一 Session/Household/孩子授权、限速、幂等、文件验证和审计；App 不再持有预签名 URL 或直连对象存储 | P0 / Security | Codex（执行中） | ADR-0018 Accepted；PLAN-0012；API/App 必须成对升级 | In Progress（API/Flutter/契约/Compose 已迁移并部署 Ubuntu；真机、断连/超时/并发现场验收和 Provider 额度恢复后的识别待完成） |
| TODO-015 | 统一 Web 孩子管理并支持多孩子工作台切换 | 创建孩子时原子创建档案和唯一绑定账号；首页按所选孩子统一过滤任务、档案和周报，消除“两套对象”和永远取第一个孩子的问题 | P0 / Web UX | Codex（执行） | PLAN-0013；ADR-0019；发布匹配 OpenAPI/API/Web 并完成迁移验收 | In Progress（聚合创建/列表/删除、Web 单表单、唯一约束和首页孩子选择已实现并部署 Ubuntu；浏览器 E2E/双孩子回归待完成） |
| TODO-016 | 建立孩子 PDF 教材范围、材料导入与知识发布 | 让错题讲解和任务建议基于家长确认的当前年级/学期/PDF 教材，而不是模型无来源记忆 | P0 / Product Foundation | Codex（执行） | ADR-0020～0023 Accepted；PLAN-0018 | In Progress（Ubuntu `0.11.0`/`0025` 已部署 PDF-only、私有原页、分批多模态分析、整本知识图谱和家长批准；真实 118 页 PDF/NewAPI 质量/成本及最终 E2E 待验收） |
| TODO-017 | 重构 Flutter 数学三入口并实现错题详细讲解 | 提供“数学 → 错题讲解/复习错题/今日任务”；拍题同时解析题目和孩子作答，确认 `worked/blank/unclear/answer_area_missing`；有作答定位错步，确认空白从头讲解，并创建错题 | P0 / Core Learning | Codex（执行） | TODO-016；PLAN-0012；ADR-0020；PLAN-0016 M1/M4 | In Progress（三入口、四态、完整解答和 closeout 已实现；真实相机四态与完整错步质量验收待设备/Provider） |
| TODO-018 | 实现正式错题本与到期复习调度 | 将拍题讲解原子沉淀为错题，提供实际题目、重新作答、追加 ReviewAttempt 和确定性到期/全部逐题过关 | P0 / Retention | Codex（执行） | TODO-017；PLAN-0016 M1/M2；ReviewPolicy v2 | In Progress（closeout、实际题目、ReviewAttempt、服务端判定和无到期项时提前复习全部错题已实现；真实设备/并发/时区 E2E 待验收） |
| TODO-019 | 实现可解释今日任务建议 | 用到期错题、已批准教材练习和有证据的薄弱知识点提出任务，默认由家长批准 | P1 / Recommendation | Codex（执行） | TODO-016、TODO-018；PLAN-0018/ADR-0022/0023 | In Progress（本地已改为全量开放错题 + 已批准知识图谱，保存具体题/视觉说明/页码/原页/日期/时长并审批下发，残缺页级文字不再进入推荐；真实 Provider/PDF/E2E 与 token/延迟/成本审计待验收） |
| TODO-020 | 实现 Tutor 第 1/2 级语义渐进提示 | L1 帮助看懂题意/定位疑点，L2 在同一 L1 上增加方法或第一步脚手架；按 worked/blank/review 分支且不泄露最终答案 | P0 / Tutor Quality | Codex（执行） | PLAN-0017；Tutor Hint Schema/Policy；固定数学 eval | In Progress（云端 L1/L2、builds-on、答案/重复/题意门禁、同时经过时间回退和 5-case eval 已在本地实现；真实 Provider/设备质量验收待完成） |

## Later — P2 候选，不承诺

- TODO-201：掌握度与复习调度增强 — 正式 MistakeRecord/ReviewSchedule 和 ReviewPolicy v1 已提升为 TODO-018；本项仅保留更复杂的自适应掌握度算法，进入条件为 v1 家庭数据质量和反馈证明有价值。
- TODO-202：语文/英语科目插件 — 进入条件：插件 ADR 证明不修改核心任务/会话模型。
- TODO-203：语音交互 — 进入条件：儿童隐私、设备权限和成本评审通过。
- TODO-204：Python 编程启蒙/受控沙箱 — 进入条件：独立安全威胁模型和 Windows 端范围批准。
- TODO-205：服务拆分 — 进入条件：模块存在独立扩容、隔离或团队边界的测量证据。
- TODO-206：教材/课程文档导入与任务生成 — 已由 ADR-0020 提升并拆入 TODO-016/019；本项仅保留更多文件格式、跨教材迁移和高级自动生成扩展。
- TODO-207：多题画面分割与人工选题 — 来源：`PRD.md` OPT-002；单题脱敏副本的云视觉解析已由 ADR-0015 提前接受，本项只保留整页/多题分割；进入条件：当前 P1 单题链路完成，评审多题脱敏范围、分割 Schema、人工选题、成本和 ADR-0015 增量。
- TODO-208：答错后的视频或详细解题过程 — 详细文字/图示解题过程已提升为 TODO-017；本项仅保留视频讲解，进入条件为视频版权/匹配、年龄适配、字幕/可访问性和成本获批。
- TODO-209：任务完成后的即时家长提醒 — 来源：`PRD.md` OPT-004；进入条件：当前 P1 开发完成，订阅/免打扰、多孩子归属、去重和推送降级规则明确。
- TODO-210：选择云端 Tutor Provider — 来源：`PRD.md` OPT-005；进入条件：当前 P1 开发完成或 Owner 明确提前推进，Provider 数据条款、预算、安全阈值和降级策略获批。
- TODO-211：评审在线优先并取消完整离线目标 — 来源：`PRD.md` OPT-006；进入条件：当前 P1 开发完成，以新 ADR 明确替代 ADR-0003，并给出现有离线代码/数据的迁移和回滚方案。
- TODO-212：完善一个 Household 下的多孩子体验 — 已将当前工作台切换与账号/档案聚合提升为 `TODO-015` / `PLAN-0013`；本项仅保留后续设备绑定、通知归属等增强，进入条件为对应领域模型和规则明确。
- TODO-213：教材页个人信息自动门禁 — 当前多模态教材分析依赖家长声明“清洁电子教材、不含儿童姓名/个人批注”，尚未自动检测姓名、手写批注、人脸或其他个人信息；进入条件为建立教材专用脱敏/阻断策略、固定漏检评测和 Provider 数据条款，不得直接复用单题拍照的语义裁剪假设。

## Blocked — 需要外部决策

| ID | 事项 | 阻塞原因 | 等待对象 | 下一次检查 |
| --- | --- | --- | --- | --- |
| BLOCK-001 | 使用真实儿童数据或向外部云端发送儿童图片 | 项目 Owner 已明确自用真实数据和本地 NewAPI 可用；仍要求只发送确认且哈希绑定的脱敏副本，不能把本地 NewAPI 配置误当成已完成安全/删除/备份验证 | 技术 Owner | NewAPI 实际联调、人工确认和删除演练前 |
| BLOCK-002 | staging/production 部署 | 平台、Owner、密钥、SLO/RPO/RTO、Runbook 和授权未确定 | 技术/运维/项目 Owner | P0 可运行后 |
| BLOCK-003 | 公开开源发布 | 远程仓库和许可证未确认 | 项目 Owner | 首次公开前 |

## 发现问题记录规则

- 范围外问题只记录症状、影响、证据和建议优先级。
- 不在 TODO 中写完整实现计划；进入执行时替换 `TASK.md`，复杂任务再更新 `PLANS.md`。
- 已完成项从队列移除，并由 Git/Issue/`CHANGELOG.md`（仅已发布变化）保留历史。
