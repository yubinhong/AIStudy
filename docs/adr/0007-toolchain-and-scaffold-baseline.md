# ADR-0007：P0 工具链与仓库骨架基线

- 状态：`Accepted`
- 日期：`2026-07-12`
- Owner：`TBD（技术负责人 + 项目 Owner）`
- 决策者：`项目 Owner（用户；2026-07-13 对话确认）`
- 关联：`TASK-0002`、`TASK-0004`、`TODO-002`
- 替代/被替代：`无`
- 批准记录：`2026-07-13`，项目 Owner（用户）批准执行本 ADR；版本变更仍须更新锁文件、验证与本 ADR。

## Context

仓库刚从文档阶段进入工程初始化。目标架构要求 Flutter、Next.js/TypeScript、Python 3.12/FastAPI、OpenAPI 契约、Docker Compose 和 CI，但尚无远程仓库、许可证、SDK 或依赖锁文件。

## Decision Drivers

- 先建立可运行的模块边界和健康端点，避免业务代码落在临时单文件中。
- 使用官方支持线并提交唯一锁文件，降低依赖漂移和供应链不可追溯风险。
- 保持本地合成数据，禁止 Provider、真实儿童数据和生产凭据进入骨架。

## Considered Options

1. 继续只维护文档：安全但无法验证目标路径和质量命令。
2. 直接初始化完整 MVP：反馈快但扩大范围，绕过授权、契约、离线和安全决策。
3. 建立最小骨架并暂以官方稳定线为假设：可验证且可回滚，但锁文件/版本仍需 Owner 批准和工具链安装。

## Decision

暂采用选项 3 作为 `TASK-0002` 的 Proposed 实施基线：Python 3.12、Node 24 LTS、Flutter stable 3.44、FastAPI 0.136.3、Next.js 16.2.10、pnpm 和 uv；API 现有 `/healthz` 及合成 Profile/Device 纵向切片，Compose 提供本地 PostgreSQL/Redis/MinIO 健康检查。

精确版本、容器镜像来源、GitHub Actions、许可证和远程仓库均需具名 Owner 批准后才可把本 ADR 改为 `Accepted`。本 ADR 不批准身份、数据生命周期、Provider、离线合并或生产部署。

## Consequences

### Positive

- 新增 FastAPI、Uvicorn、Next.js、React、Flutter SDK 和本地基础设施镜像依赖；它们均应在对应锁文件/镜像版本中固定，并在首次合并前完成许可证与漏洞检查。

### Negative / Trade-offs
- 工具链依赖本机安装；不能把某开发机成功构建视为 CI/四设备发布验证。
- 业务模块必须继续遵守 `packages/contracts` 唯一契约源和 `services/api` 模块化边界。

### Risks and Mitigations

- 风险：Node 或本机原生 SDK 与锁定基线不匹配；缓解：在 `TESTING.md` 明确实测版本/警告，并由 CI 使用目标版本。

## Compatibility and Migration

- `/healthz` 是新增 P0 端点，不改变既有 API；后续资源接口必须采用向后兼容的 OpenAPI 增量。
- 从 Proposed 到 Accepted 只需补充 Owner、许可证、锁文件和 CI 实测记录；若版本不合适，在未接入业务数据前重新生成锁文件即可。
- 回滚只删除本轮新增骨架/配置或回退未提交文件；不得删除用户既有文档、Prompt、设计稿或未知工作区文件。

## Validation

- `docker compose -f infra/compose/compose.yml config`
- `uv sync --locked`、API format/lint/test
- `pnpm install --frozen-lockfile`、Web format/lint/type/test/build
- `flutter pub get`、format/analyze/test
- CI 配置审查；不得在锁文件生成前启用成功门槛。
