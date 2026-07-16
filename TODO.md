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
| TODO-008 | 实现 Capture/本地隐私脱敏/云视觉解析/人工校正 | 支持数学单题输入，保证原图不外发并控制脱敏漏检、模型误解析和低置信度风险 | P1 | Codex（执行） | ADR-0010/0011/0015/0016 Accepted；自托管 NewAPI 已部署后才能联调 | In progress（TASK-0006；MinIO/授权/生命周期/人工校正基础、对象实际 SHA-256、Provider-neutral Schema、本地脱敏核心/规则信号、Flutter 确认上传、6-case eval、0008 receipt/API、0009 提取结果仓储、Bearer 认证、NewAPI Adapter 和可开关 worker 已实现；待完成人工确认接口、临时副本删除演练、真实检测器和 NewAPI 联调） |
| TODO-009 | 实现 Tutor Policy、Provider Adapter 和固定 AI eval | 只消费人工确认的 VerifiedQuestion，提供分级提示并控制安全、Schema 和成本 | P1 | Codex（执行） | ADR-0015/0016；本地 NewAPI 可选，默认离线降级 | In progress（offline Tutor Policy 1～3 级提示与 synthetic eval、NewAPI 结构化 Adapter 已实现；Tutor 仍只接受人工确认的 VerifiedQuestion，真实 Tutor Provider 暂不接入） |
| TODO-010 | 实现错题、复习和可追溯周报 | 完成孩子学习到家长反馈的闭环 | P1 | `TBD` | Session/Tutor 数据稳定 | Planned |
| TODO-011 | 恢复可复现的 uv 可执行入口 | 当前临时 uv 路径已清理，依赖锁可用但标准 `uv` 命令不可发现 | P0 | `TBD` | 确认项目级或用户级 uv 安装策略 | Planned |
| TODO-012 | 用账号密码和可撤销会话替换静态家庭 Token | 家长 Web 需要真实登录、首次改密和孩子账号管理；孩子需要独立可撤销身份，不能继续共享长期 HMAC Token | P0 | Codex（待执行） | ADR-0017 Accepted；当前 TASK-0006 完成或由 Owner 明确暂停后进入 TASK | Planned（下一优先级；PLAN-0007 已建立） |

## Later — P2 候选，不承诺

- TODO-201：掌握度与复习调度增强 — 进入条件：P1 数据质量和家庭反馈证明有价值。
- TODO-202：语文/英语科目插件 — 进入条件：插件 ADR 证明不修改核心任务/会话模型。
- TODO-203：语音交互 — 进入条件：儿童隐私、设备权限和成本评审通过。
- TODO-204：Python 编程启蒙/受控沙箱 — 进入条件：独立安全威胁模型和 Windows 端范围批准。
- TODO-205：服务拆分 — 进入条件：模块存在独立扩容、隔离或团队边界的测量证据。
- TODO-206：教材/课程文档导入与任务生成 — 来源：`PRD.md` OPT-001；进入条件：当前 P1 开发完成，明确文档格式、版权、知识点映射、人工审核和生成失败回滚。
- TODO-207：多题画面分割与人工选题 — 来源：`PRD.md` OPT-002；单题脱敏副本的云视觉解析已由 ADR-0015 提前接受，本项只保留整页/多题分割；进入条件：当前 P1 单题链路完成，评审多题脱敏范围、分割 Schema、人工选题、成本和 ADR-0015 增量。
- TODO-208：答错后的视频或详细解题过程 — 来源：`PRD.md` OPT-003；进入条件：当前 P1 开发完成，视频版权/匹配、Tutor Policy、详细答案正确性和固定 eval 获批。
- TODO-209：任务完成后的即时家长提醒 — 来源：`PRD.md` OPT-004；进入条件：当前 P1 开发完成，订阅/免打扰、多孩子归属、去重和推送降级规则明确。
- TODO-210：选择云端 Tutor Provider — 来源：`PRD.md` OPT-005；进入条件：当前 P1 开发完成或 Owner 明确提前推进，Provider 数据条款、预算、安全阈值和降级策略获批。
- TODO-211：评审在线优先并取消完整离线目标 — 来源：`PRD.md` OPT-006；进入条件：当前 P1 开发完成，以新 ADR 明确替代 ADR-0003，并给出现有离线代码/数据的迁移和回滚方案。
- TODO-212：完善一个 Household 下的多孩子体验 — 来源：`PRD.md` OPT-007；进入条件：当前 P1 开发完成，真实持久化、孩子切换、设备绑定、任务/通知/周报隔离和删除规则明确。

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
