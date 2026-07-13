# TESTING.md

## 1. 当前状态与质量目标

当前仓库已有 P0 依赖清单、最小测试、CI 草案和三类锁文件。API 的 Household 边界/幂等切片、Web/Flutter 合同消费入口、Compose 配置以及 Flutter 格式/分析/单元测试已有本地验证；Android 调试 APK 和 iOS 无签名 Runner.app 均已构建通过。E2E/AI/契约 SDK 生成/安全扫描仍是后续入口。

- 核心用户路径：家长创建任务 → 孩子端同步 → 作答/拍题 → OCR 校正 → 1～3 级提示 → 错题沉淀 → 离线重连 → 家长周报。
- 不可接受的失败：跨家庭越权；儿童数据/图片/密钥泄漏；学习记录丢失或被最后写入覆盖；AI 直接代答或错误结论静默入库；删除请求未执行却报告成功；未记录的成本失控。
- 覆盖策略：风险驱动，不设脱离代码基线的统一行覆盖率。家庭权限、幂等/离线合并、Tutor Policy/Schema、数据删除和核心 E2E 必须覆盖成功与失败路径；普通模块在 P0 代码基线后批准覆盖阈值。

## 2. 当前可运行验证

### 文档占位符检查

```bash
rg -n '\{\{|\}\}' AGENTS.md AI_CONTEXT.md ARCHITECTURE.md CHANGELOG.md DECISIONS.md PLANS.md PRD.md PROJECT.md RUNBOOK.md SECURITY.md TASK.md TESTING.md TODO.md
```

预期：无输出。`prompts/` 和 `docs/adr/0000-template.md` 是可复用模板，保留占位符是预期行为。

### 仓库事实检查

```bash
git status --short
git branch --show-current
rg --files -uu -g '!.git/**' -g '!node_modules/**'
```

预期：当前分支 `master`、无提交；P0 骨架文件和三类锁文件已存在，Android/iOS 原生构建均已有本地验证。

## 3. P0 目标标准命令

以下命令同时是脚手架验收契约。实现时如采用不同入口，必须先保证实际可运行，再同步本文件和 `AGENTS.md`。

| 区域/目的 | 目标命令 | 何时运行 | 当前状态 |
| --- | --- | --- | --- |
| Flutter 安装 | `cd apps/child_flutter && flutter pub get` | 锁文件变化/干净环境 | 通过（2026-07-12；Flutter 3.44.6；2026-07-13 交互式 PATH 与 `flutter doctor -v` 全绿） |
| Flutter 格式 | `cd apps/child_flutter && dart format .` | 每次 Flutter 变更 | 通过（2026-07-13；离线队列已按当前 Dart formatter 写回） |
| Flutter 静态/类型 | `cd apps/child_flutter && flutter analyze` | 每次 Flutter 变更 | 通过（无 issues，2026-07-13） |
| Flutter 单元/Widget | `cd apps/child_flutter && flutter test` | 每次 Flutter 变更 | 通过（4 tests，2026-07-13；含离线队列） |
| Flutter 构建 | `cd apps/child_flutter && flutter build ios --no-codesign` 或 `flutter build apk` | 合并前/平台变更 | 通过（2026-07-12）：Flutter 3.44.6、重装的 NDK `28.2.13676358` 和 Android Studio JDK 21 生成 `app-debug.apk`（139 MB）；Xcode 26.6 + iOS 26.5 runtime 生成无签名 `Runner.app`。2026-07-13 已接受 Android 许可证，交互式 `flutter doctor -v` 全绿 |
| Web 安装 | `cd apps/web && pnpm install --frozen-lockfile` | 锁文件变化/干净环境 | 通过（2026-07-12；构建脚本白名单已审查） |
| Web 格式 | `cd apps/web && pnpm format:check` | 每次 Web 变更 | 通过（2026-07-12） |
| Web Lint | `cd apps/web && pnpm lint` | 每次 Web 变更 | 通过（2026-07-12） |
| Web 类型 | `cd apps/web && pnpm typecheck` | 每次 Web 变更 | 通过（2026-07-12） |
| Web 单元 | `cd apps/web && pnpm test` | 每次 Web 变更 | 通过（1 test，2026-07-12） |
| Web E2E | `cd apps/web && pnpm e2e` | 用户流程变更/P1 门槛 | 不可运行 |
| Web 构建 | `cd apps/web && pnpm build` | 合并前 | 通过（2026-07-12） |
| API 安装 | `cd services/api && uv sync --locked` | 锁文件变化/干净环境 | 通过（2026-07-13；锁定 SQLAlchemy 2.0.51、Alembic 1.18.5、Psycopg 3.3.4） |
| API 格式 | `cd services/api && uv run ruff format --check .` | 每次 API 变更 | 通过（2026-07-13；25 files） |
| API Lint | `cd services/api && uv run ruff check .` | 每次 API 变更 | 通过（2026-07-13） |
| API 类型 | `cd services/api && uv run mypy src tests` | 每次 API 变更 | 通过（2026-07-13；22 source files） |
| API 单元 | `cd services/api && uv run pytest -m "not integration"` | 每次 API 变更 | 通过（14 tests，2026-07-13；含 Household、任务版本、Attempt 幂等、离线批次与 Capture 校正） |
| Compose 配置 | `docker compose -f infra/compose/compose.yml config` | Compose 变更 | 通过（2026-07-13；仅确认 local-only 配置） |
| 集成环境 | `docker compose -f infra/compose/compose.yml up -d postgres` | API/数据/跨模块变更 | 通过（2026-07-13；Docker Desktop 29.2.1，postgres:16.10 healthy，端口 5432，synthetic local 配置） |
| API 集成 | `cd services/api && uv run pytest -m integration` | 跨模块/数据变更 | 通过（5 tests，2026-07-13；migration schema、Learning/Capture 持久化幂等、批次原子性、连接池重连和并发版本冲突） |
| API 镜像 | `docker compose -f infra/compose/compose.yml build api` | 合并/发布前 | 不可运行 |
| AI eval | `TBD（P0 在 evals/ 建立稳定入口）` | 模型/Prompt/Policy/路由变更 | 阻塞：仅有占位边界，无模型/评测集 |
| 契约结构/差异 | `ruby -ryaml -e '...'`（见任务记录） | OpenAPI/Schema 变更 | 通过（2026-07-13）：健康、Profile/Device、Learning 与 Capture `0.4.0` 路径和 Schema 已检查；SDK 生成器未决定 |
| 安全扫描 | `TBD（按 Flutter/pnpm/uv/镜像工具链建立）` | 合并/发布前 | 阻塞：无依赖/镜像 |

耗时预算必须在命令首次进入 CI 后用实际数据补充，不在无代码阶段猜测。

## 4. 最小相关验证规则

- 文档变更：运行占位符、交叉引用、Markdown 表格和敏感信息检查；确认目标架构没有写成已实现。
- 纯函数：运行对应单元测试、格式、Lint 和类型检查。
- OpenAPI/JSON Schema：运行生成/差异、兼容性、消费者和授权测试；生成 SDK 后工作区必须无差异。
- API：运行契约、家庭授权正反向、错误映射、幂等和相关集成测试。
- 数据模型：验证扩展/迁移/收缩、旧客户端、离线事件、回滚/前滚、备份恢复、并发和索引路径。
- 离线同步：覆盖断网、进程终止、队列部分成功、重复提交、同键不同载荷、过期令牌、时钟偏差和版本冲突。
- UI：验证职责内设备、横竖屏、弱网、键盘、相机/存储权限、空/错/加载/重试和辅助功能。
- AI：固定版本评测正确提示层级、禁止直接代答、低置信度校正、Schema 失败、敏感内容、Provider 超时/限流、降级和成本上限。
- 缺陷：先建立失败复现，再做最小修复和回归测试。

## 5. 测试矩阵（目标）

| 能力 | 单元 | 集成 | E2E/设备 | 安全 | 性能/成本 | Owner |
| --- | --- | --- | --- | --- | --- | --- |
| 家庭/孩子/设备 | 权限策略、令牌状态 | DB/API/契约 | iPad + Windows 共享档案 | 跨 Household、过期/撤销设备 | 登录/同步延迟 | `TBD` |
| 任务/会话/Attempt | 状态机、追加写 | 事务、幂等、冲突 | 创建到完成、断网重连 | 越权、载荷篡改 | 队列吞吐 | `TBD` |
| Capture/OCR | Schema、置信度 | 签名上传、Provider Adapter | 四端权限、裁切、校正 | 文件类型/大小、恶意内容、URL | 上传/OCR 延迟和成本 | `TBD` |
| Tutor | Policy、提示级别、Schema | Provider 失败/降级、审计 | 完整分步提示 | 直接代答、敏感内容、提示注入 | token/延迟/家庭预算 | `TBD` |
| 错题/复习/周报 | 规则和聚合 | 数据追溯、重算 | 家长查看与异常说明 | 家庭隔离、删除联动 | 周报生成时间 | `TBD` |
| 导出/删除 | 范围计算、状态机 | DB/对象/缓存/备份策略 | 家长发起到完成 | 身份确认、审计、残留扫描 | 完成时间 | `TBD` |
| 通知 | 路由和降级 | HMS/应用内适配器 | 华为/iPhone 回归 | 令牌保护、最小内容 | 发送成功率/成本 | `TBD` |

## 6. 测试数据与环境

- 默认使用合成数据；需要真实分布时只使用经批准、不可回溯且最小化的脱敏数据。
- 禁止把生产凭据、儿童身份、题目图片、家庭内容或数据库转储复制到夹具、快照、评测集和日志。
- 固定随机种子：单元/属性/AI 抽样测试必须可重放；具体种子入口由各模块配置并记录失败种子。
- 时间/时区：服务端存储 UTC；界面按家庭时区显示。测试至少覆盖 UTC、Asia/Shanghai、周界、夏令时边界（即使首版家庭不使用 DST）和客户端时钟偏差。
- 外部服务：CI 默认使用 mock/fake 或本地 MinIO/Redis/PostgreSQL；真实 AI/HMS sandbox 仅在受控集成阶段使用，凭据不进入日志。
- AI eval：样本必须标注来源/授权、年级、题型、期望提示行为和禁止行为；模型输出不得反向污染金标。

## 7. CI 与发布质量门槛

- [ ] 依赖按锁文件安装；格式、Lint、类型检查通过。
- [ ] 最小相关测试和受影响套件通过，测试失败不能通过无解释重跑掩盖。
- [ ] OpenAPI/Schema 兼容检查通过，生成物无漂移。
- [ ] 家庭授权、幂等/离线、文件输入、AI 安全和删除路径的高风险测试通过。
- [ ] 无未批准的高危依赖/镜像/密钥扫描问题；SBOM/签名策略在生产前确定。
- [ ] 构建产物可生成，迁移与备份恢复经过验证。
- [ ] P1 核心 E2E 全通过，四类设备完成职责内弱网/横竖屏/权限回归。
- [ ] AI eval、成本告警、周报追溯和儿童数据删除有可审查记录。

## 8. 无法运行测试时

必须在 `TASK.md` 完成记录中写明：未运行的命令、阻塞原因、已完成的替代验证、残余风险和下一位执行者的精确下一步。当前 Android/iOS 本地构建均已通过，但不等同于真实设备安装、签名、权限或四设备回归验证。
