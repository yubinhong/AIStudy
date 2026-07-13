# Prompt：项目初始化与上下文建档

你现在是本项目的技术负责人。目标是让后续 Codex 会话无需重新解释项目，而不是立即写功能代码。

请执行以下工作：

1. 阅读根目录的 `AGENTS.md`、`AI_CONTEXT.md`、`PROJECT.md`、`PRD.md`、`ARCHITECTURE.md`、`TESTING.md`、`SECURITY.md`、`RUNBOOK.md`、`TODO.md` 和 `CHANGELOG.md`。
2. 检查仓库结构、依赖清单、配置样例、入口文件、数据库迁移、CI、测试和部署脚本；不要读取或输出真实密钥。
3. 用代码和可运行命令验证文档中的技术事实，不要仅凭文件名猜测。
4. 填充能够从仓库可靠推导的 `{{...}}`；无法确定的内容保留 `TBD`，并说明需要谁确认、为什么重要。
5. 将稳定信息放入其唯一主文档：项目事实进 `PROJECT.md`，系统结构进 `ARCHITECTURE.md`，命令进 `TESTING.md`，安全规则进 `SECURITY.md`，当前快照和链接进 `AI_CONTEXT.md`。
6. 不修改业务代码，不升级依赖，不部署，不提交 Git。

完成标准：

- `AI_CONTEXT.md` 能在 3 分钟内让新会话理解项目状态和阅读路径。
- `AGENTS.md` 中的命令与仓库实际一致。
- 列出发现的文档冲突、未知项、风险和建议创建的 ADR/TODO。
- 最终汇报：更新的文件、已验证的事实、仍需确认的问题、建议的第一个 `TASK.md`。

