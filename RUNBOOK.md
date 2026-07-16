# RUNBOOK.md

## 1. 服务概览

- 服务：家庭 AI 学习助手（目标包括 Flutter 孩子端、Web/PWA、FastAPI/Worker、PostgreSQL、Redis、S3/MinIO 和 AI Provider）。
- 当前状态：`SELF_HOSTED_DEV_VALIDATED`。Ubuntu 24.04 x86_64 VM `192.168.1.4` 已运行一次自用 Compose 验证栈；没有 staging/production、Dashboard 或日志平台，本 Runbook 仍不构成生产部署批准。`ADR-0008` 已 Accepted。
- Owner/值班：`TBD（项目 Owner/运维负责人在 staging 前确认）`。
- 用户影响：服务中断会阻止同步、拍题、AI 提示和周报；孩子端必须保留离线任务/作答，不能因服务中断丢学习记录。
- 外部依赖：单一获批云视觉 Provider、Tutor Provider、HMS（或应用内提醒）和对象存储；具体供应商 `TBD`。本地 OCR 仅是目标 PrivacySanitizer 的隐私检测依赖，不是外部 Provider。
- Dashboard/日志/Trace：目标为 OpenTelemetry 接入批准的可观测平台；链接和查询 `TBD`。

## 2. SLO 与关键指标

SLO 必须在 staging 获得基线后由产品/技术 Owner 批准，不在零代码阶段编造。

| 指标 | 目标 | 告警阈值 | 当前状态 |
| --- | --- | --- | --- |
| API 可用性 | `TBD` | `TBD` | 无服务 |
| 任务/会话 API 延迟 | `TBD` | `TBD` | 无基线 |
| 本地脱敏/云视觉解析/首个 Tutor 提示延迟 | `TBD` | `TBD` | 仅旧本地 OCR 有 synthetic 基线；新路线无 Provider |
| 错误率 | `TBD` | `TBD` | 无基线 |
| 离线同步冲突/失败 | 不得丢失或覆盖学习记录 | 阈值 `TBD`；任何确认的数据丢失立即升级 | 无实现 |
| AI Schema/安全失败 | 阻断不合规响应 | 阈值 `TBD`；直接代答/敏感泄露立即升级 | 无 eval |
| AI 成本 | 每家庭/请求预算 `TBD` | 超批准预算即告警/降级 | 无成本数据 |
| 导出/删除/备份失败 | 0 个静默失败 | 任一超时或错误立即告警 | 无实现 |

## 3. 环境与部署

### 当前环境

- local：`infra/compose/compose.yml` 已编排 PostgreSQL、Redis、MinIO、API、家长 Web、一次性 Alembic migration 和默认启动的 ImageAnalysis worker；Apple Silicon `linux/arm64` 调试镜像构建成功。NewAPI 默认关闭；此时 worker 保持空闲。
- Ubuntu 自用验收：宿主确认 Ubuntu 24.04/x86_64、Docker 29.1.3、Compose 2.40.3；Docker IPv6 已关闭并经 `socks5://192.168.1.100:7893` 出网。远端 Compose config、`0011` migration、amd64 Paddle 模型镜像、API/Web healthz、loopback bootstrap login、重启恢复和内存 synthetic OCR smoke 已通过；远端 `.env` 未进入仓库且权限为 600。NewAPI Key/模型已配置并启用；Cloudflare 1010 拦截 Python 默认 User-Agent 后，受限 `study-api/0.5` 请求已成功完成 synthetic `queued → Extraction`，临时派生对象删除且残留 Job 为 0。首次改密、Cookie/CSRF、孩子账号/iPad 生命周期、备份恢复和生产监控仍未执行。
- staging：未建立。
- production：未建立且未获部署授权。

### 账号密码认证切换（ADR-0017；代码已实现，环境验收待执行）

自用首次启动和迁移按以下顺序执行；`0011_account_password_session` 已提供 migration/API，Ubuntu Compose 健康与 loopback bootstrap login 已验证，首次改密和真实设备验收仍需执行：

1. 先让 Web/API 只监听 loopback，应用 Account/AuthSession 前滚迁移；仅当账号表为空时创建一次性 `admin/admin123456`，确认数据库只含 Argon2id 哈希且 `must_change_password=true`。
2. 从服务器本机登录，验证除当前账号、改密和退出外的家庭数据接口均返回 `password_change_required`；立即修改管理员密码。
3. 确认所有引导会话已撤销，新会话可读取同一 Household 数据后，才允许把 Web 暴露到家庭局域网；禁止让默认密码在非 loopback 环境继续有效。
4. 在 Web 创建孩子账号并绑定 ChildProfile；验证孩子只能访问自己的任务/会话，不能访问家长管理接口或兄弟孩子数据。
5. 验证登出、改密、停用、重置和 30 天到期均能撤销会话；验证 Web Cookie/CSRF、Flutter 登录前服务端地址配置和 Keychain/Android Keystore 生命周期。
6. 唯一管理员忘记密码时当前仅允许服务器本机维护人员按恢复方案处理；正式受审计恢复命令仍待实现，不提供短信、邮箱或 MFA 恢复。

回滚时优先前滚修复；确需回退时只回退到上一应用版本，不删除 Account/AuthSession 表或恢复已撤销会话。上一版本包含的 HMAC/Demo 路径不视为安全回滚方案，若必须启用需项目 Owner 另行明确批准且限于隔离环境。迁移版本为 `0011_account_password_session`，真实回滚/恢复脚本仍待实测。

### 自用 NewAPI 启用流程

默认 `STUDY_NEWAPI_ENABLED=false`，此时图片分析只记录 `provider_not_enabled` 的 blocked 回执，worker 保持空闲，不读图片、不出网。自用部署者在本机 NewAPI 已可达并确认模型支持视觉后，注入对应环境变量，再重启 API 和 worker：

```bash
export STUDY_NEWAPI_ENABLED=true
export STUDY_NEWAPI_BASE_URL=http://127.0.0.1:3000
export STUDY_NEWAPI_API_KEY="<local-newapi-key>"
export STUDY_NEWAPI_VISION_MODEL="<vision-model>"
export STUDY_NEWAPI_USER_AGENT="study-api/0.5"
cd services/api
uv run python scripts/run_image_analysis_worker.py --watch
```

启用前先用 synthetic 图片验证 NewAPI 返回 `question-extraction.v1` JSON；默认 `STUDY_NEWAPI_USER_AGENT=study-api/0.5`，用于兼容会拦截 Python 默认 `urllib` 签名的前置网关。该值只能是 1–256 个可打印 ASCII 字符，禁止换行或其他控制字符。worker 的失败只写稳定错误码，原始 Provider 请求/响应不写日志。发现外发范围、模型行为或成本异常时，立即将 `STUDY_NEWAPI_ENABLED=false` 并停止 worker；已入队任务不会在关闭开关后继续被新 worker 领取。

### 生产前置检查

- [ ] CI、契约、测试、AI eval、安全扫描和四设备回归通过。
- [ ] 版本化产物、配置清单、迁移、容量、功能开关、模型/Prompt/Policy 版本已审查。
- [ ] 备份、恢复演练、数据导出/删除、成本和安全告警就绪。
- [ ] 适用法域、儿童隐私、保留期限、Owner/值班和安全联系渠道已批准。
- [ ] ADR-0017 环境验收：代码已实现默认管理员仅本机首次登录、首次改密、会话撤销、Web Cookie/CSRF 和孩子账号反向授权；完整 Compose、浏览器 E2E 和真实设备验证后才能勾选。
- [ ] 自用 NewAPI 的 URL、API key、视觉模型、响应 Schema、停用开关和本地 synthetic 联调已验证；PrivacySanitizer/用户确认/临时副本删除 eval 已通过。
- [ ] 发布、停止、回滚和前滚负责人明确，真实数据不来自开发环境。

### 本地/自用 Compose 流程

```bash
cp infra/compose/.env.example infra/compose/.env
openssl rand -hex 32
docker compose -f infra/compose/compose.yml config
docker compose -f infra/compose/compose.yml up -d --build
docker compose -f infra/compose/compose.yml ps
curl http://127.0.0.1:${WEB_PORT:-3000}/healthz
```

ImageAnalysis worker 是默认服务；NewAPI 关闭时它安全空闲，启用后执行 `up -d --build api image-analysis-worker` 使配置生效。Apple Silicon 默认构建原生 Linux ARM 调试镜像；它不包含只提供 macOS ARM64/Linux x86_64 wheel 的 PaddlePaddle 3.3.1，因此不能用于验证旧本地 Paddle OCR。需要完整 Paddle 路线时，在 macOS 原生进程运行 API/OCR worker，或显式使用 `linux/amd64` 模拟镜像。完整变量说明、NewAPI 容器外部接入、迁移、停止、升级和回滚见 `infra/compose/README.md`。Compose 使用持久卷；未完成备份前不得使用 `down -v`。日志/遥测、自动备份、保留清理器和生产安全默认值仍需补齐。

以下命令只运行 ADR-0012 下已经实现的本地完整 OCR synthetic 路线，用于兼容/回滚验证；它不实现 ADR-0015，也不会向云端发送图片。API 与旧 OCR Worker 要共享 Job 状态时，必须显式启用 PostgreSQL Learning/Capture、Job 和结果仓储；Worker 需要五个带构建期 SHA-256 标记的模型目录、PostgreSQL、MinIO 配置：

```bash
cd services/api
STUDY_API_LEARNING_REPOSITORY=postgres \
STUDY_API_OCR_QUEUE=postgres \
STUDY_API_OCR_RESULTS=postgres \
uv run uvicorn study_api.main:app --host 0.0.0.0 --port 8000

# One job:
STUDY_API_OCR_QUEUE=postgres uv run python scripts/run_ocr_worker.py

# Continuous local polling:
STUDY_API_OCR_QUEUE=postgres OCR_WORKER_POLL_INTERVAL_SECONDS=2 \
uv run python scripts/run_ocr_worker.py --watch
```

一次性命令只处理一个任务；`idle` 和 `succeeded` 返回 0，OCR 失败返回 1，启动配置错误返回 2。队列请求默认使用普通 text OCR；只有显式提交 `{"mode":"formula"}` 才调用本地公式模型。`--watch` 会持续轮询 PostgreSQL 队列，Ctrl-C 后关闭资源并返回最近状态；当前未定义进程管理、Redis Worker 或生产告警。

### staging/production 部署

```text
TBD：当前只提供单家庭自托管 Compose；公网暴露、CI/CD、自动备份、监控和多环境发布流程尚未决定。
```

未获用户明确授权不得部署、修改云资源、迁移生产数据或发送外部通知。

## 4. 部署后验证（目标）

1. 验证版本、配置、迁移状态和依赖健康，不打印密钥。
2. 使用合成监控家庭验证家长登录/改密/退出、孩子账号创建/停用/重置、孩子登录、会话撤销、孩子档案、任务同步和会话开始；确认默认引导凭据和改密前会话不能读取家庭数据。
3. 验证一次离线作答重连、幂等重复提交和同步冲突路径。
4. 使用 synthetic 图片验证签名上传、本地脱敏/手动涂抹/用户确认、单 Provider 云视觉结构化、题目校正、临时副本删除、Tutor Schema/Policy 和成本记录；确认 Provider 请求不含原图、MinIO URL、对象键或敏感 OCR 文本。
5. 验证错题/周报追溯、应用内提醒降级和导出/删除测试流程。
6. 检查授权异常、错误率、延迟、队列、AI 安全/成本、对象删除和备份指标。

具体烟雾测试命令 `TBD（P0/P1 实现时建立）`。

## 5. 回滚与前滚

- 触发条件：跨家庭越权、学习记录丢失/覆盖、迁移破坏、AI 安全阻断失败、Restricted 数据泄漏、删除错误、错误率/成本超过批准阈值。
- 功能降级顺序：关闭云视觉图片外发 → 降级为重新裁剪/手工录入或显式本地 OCR 回滚 Provider → 关闭受影响 Tutor 模型/Policy → 关闭拍题/Tutor/通知/周报等独立开关 → 回退应用版本 → 隔离写入。任何降级都不得发送原图或自动广播给其他 Provider。
- 应用回滚：部署平台与命令 `TBD`。必须回退到已验证版本，并保持客户端/契约兼容。
- 数据策略：优先向前修复；只有已验证无数据损失且符合迁移契约时才回滚。Attempt/AuditEvent 不做破坏性覆盖。
- 离线兼容：回滚版本仍须接受或明确拒绝已发放客户端的版本化事件，不能让队列永久卡死。
- 验证：重跑部署后烟雾、授权、幂等/同步、AI 安全和数据追溯；确认告警恢复且无新增丢失。

## 6. 常见告警与处置框架

### 家庭授权异常

- 含义：跨 Household 访问尝试或本不应成功的授权路径。
- 首先检查：版本/配置变更、actor/device/household 不可逆标识、路由和策略版本；不得查看无关原始儿童数据。
- 临时缓解：撤销会话/设备、关闭受影响接口或回退；确认成功越权时按 Critical 事件处理。
- 升级：任一确认的跨家庭成功访问立即升级安全 Owner。

### 离线同步冲突或失败激增

- 含义：设备队列无法清空、重复副作用或版本冲突超基线。
- 首先检查：Schema/客户端版本、幂等存储、数据库错误、队列积压和最近迁移。
- 临时缓解：停止破坏性状态写入，保留追加事件和客户端队列；不得要求用户清空应用数据。
- 升级：任何学习记录丢失/覆盖立即按高严重度事件处理。

### AI Schema/安全/成本异常

- 含义：模型输出不符合契约、Tutor Policy 阻断率变化、直接代答或成本超限。
- 首先检查：Provider/model、Prompt/Policy/Schema 版本、路由、延迟/token/成本和最近开关。
- 临时缓解：切回已验证版本/低风险模型，收紧提示或暂停 AI；保留任务与手工学习路径。
- 升级：敏感泄漏、对儿童有害输出或预算失控立即升级产品/安全/技术 Owner。

### 图片脱敏或外发门禁异常

- 含义：原图/未确认副本可能外发、敏感信息漏检、遮挡可逆、同一图片跨 Provider 发送或临时副本未按期删除。
- 首先检查：Capture/脱敏副本不可逆标识、sanitizer/rule/schema 版本、用户确认哈希、Provider 路由、请求摘要和删除状态；不得查看或复制无关原图/敏感 OCR 文本。
- 临时缓解：立即关闭云视觉外发开关，撤销 Provider 凭据，阻止待发队列并保留最小审计证据；学习流程降级为手工录入。
- 升级：任一确认的原图/身份外发、跨 Provider 广播或删除失败按 Restricted 数据事件升级安全/法务/产品/技术 Owner。

### 导出/删除/备份失败

- 含义：数据生命周期或恢复能力未达到承诺。
- 首先检查：任务状态、对象/数据库/缓存/备份范围、权限和审计关联。
- 临时缓解：停止报告“完成”，阻止进一步自动清理造成证据丢失，人工跟踪受影响请求。
- 升级：超批准时限或遗漏 Restricted 数据立即升级安全/法务 Owner。

## 7. 事故响应

1. 确认影响、严重度、开始时间、家庭/设备/版本范围，避免复制原始敏感数据。
2. 优先止损：撤销凭据、关闭功能/Provider、隔离写入或回退；不在事故中做无关重构。
3. 保留最小必要日志、指标、变更和操作证据；不得删除审计或擅自对外通知。
4. 状态更新间隔 `TBD（值班制度建立前建议高严重度不超过 30 分钟，但需 Owner 批准）`。
5. 恢复后验证核心学习、授权、离线、AI 和数据生命周期路径。
6. 建立复盘、回归测试、TODO/ADR，并更新 `SECURITY.md`、本 Runbook 和告警。

## 8. 灾难恢复

- RPO：`TBD（生产前批准）`。
- RTO：`TBD（生产前批准）`。
- 备份位置/加密/权限：`TBD（部署平台确定后记录，不在仓库写密钥）`。
- 恢复流程：目标为在隔离环境恢复 PostgreSQL、对象引用和必要配置，验证家庭边界、事件完整性、对象可用性和删除策略后才切流。
- 演练频率：`TBD`；staging 上线前至少完成一次端到端恢复演练，production 后按批准频率重复。
- Redis 和端侧 SQLite 不作为服务端灾难恢复事实源；Redis 可重建，端侧未同步队列需在恢复后兼容接收。

## 9. Runbook 完成条件

在 staging/production 建立后，本文件必须补齐实际 Owner、平台、Dashboard、日志查询、SLO/告警阈值、部署/回滚命令、RPO/RTO、备份位置和演练记录。任何一项仍为 `TBD` 时，不得宣称具备生产运维能力。
