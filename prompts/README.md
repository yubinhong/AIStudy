# Prompt 使用说明

这些 Prompt 不是替代项目文档，而是触发不同工作阶段的“启动器”。每次只选择与当前目标最接近的一份。

使用方式：

1. 在项目根目录启动 Codex。
2. 确认 `AGENTS.md`、`AI_CONTEXT.md` 和当前 `TASK.md` 已填写。
3. 将对应 Prompt 直接发送；把 `{{...}}` 替换成当前信息。
4. 任务进行中优先在同一线程继续；切换线程时让 Codex先执行 `08-context-refresh.md`。

选择建议：

| 场景 | Prompt |
| --- | --- |
| 新仓库或旧项目首次接入 | `00-project-bootstrap.md` |
| 模糊需求变成可评审 PRD | `01-requirement-to-prd.md` |
| 已有需求，先拆任务和计划 | `02-task-planning.md` |
| 按 TASK 实现到完成 | `03-implementation.md` |
| 可复现缺陷或线上问题 | `04-debugging.md` |
| 审查工作区、提交或 PR | `05-code-review.md` |
| 准备版本、迁移和发布材料 | `06-release.md` |
| 中断、交接或换线程 | `07-handover.md` |
| 文档与代码状态需要重新对齐 | `08-context-refresh.md` |

如果同一种工作经常重复，建议把稳定流程升级为 Codex Skill；不要继续堆叠越来越长的一次性 Prompt。

