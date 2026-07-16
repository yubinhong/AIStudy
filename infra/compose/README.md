# Docker Compose 自托管部署

这套 Compose 适合单家庭、自用部署，包含 PostgreSQL、Redis、MinIO、FastAPI API、家长 Web、数据库迁移一次性服务和默认启动的 NewAPI 图片分析 worker。Compose 会从同目录的 `.env` 注入服务变量，不需要在启动命令中传入 `--env-file`。它不会部署 NewAPI；NewAPI 由部署者单独提供，API 通过 OpenAI-compatible `/v1/chat/completions` 访问。

当前服务端状态：API、Bearer 认证、MinIO 预签名上传、ImageAnalysis 队列、QuestionExtraction 持久化、家长 Web 和 NewAPI worker 已实现；题目人工确认生成 `VerifiedQuestion`、真实 NewAPI 联调、脱敏副本自动清理、备份恢复和生产监控仍未完成。因此本文件提供的是“可启动的自用全栈部署”，不是完整产品发布证明。

## 1. 前置条件

- Docker Desktop 或 Docker Engine + Compose v2。
- Linux x86_64 或 ARM64 Docker；Apple Silicon 上默认构建原生 `linux/arm64` 调试镜像，不再强制 amd64 模拟。
- NewAPI 已单独部署，并有支持图片输入的 OpenAI-compatible 视觉模型；没有 NewAPI 时仍可启动 API，但图片分析保持关闭。
- x86_64 构建需要留出模型构建所需磁盘空间和网络。Paddle 模型只在 amd64 镜像构建阶段下载并校验 SHA-256，运行时不会自动下载或更新。

Apple M4 本身是 ARM64，PaddlePaddle 3.3.1 也提供 macOS ARM64 wheel；但 Docker Desktop 容器运行的是 Linux ARM64，当前锁定版本没有对应的 Linux aarch64 wheel。因此原生 ARM Compose 调试镜像包含 API、迁移和 NewAPI ImageAnalysis worker，但不包含旧本地 Paddle OCR 或五份 Paddle 模型。需要在 M4 上调试完整 Paddle 路线时，应让 PostgreSQL/Redis/MinIO 留在 Compose，API/OCR worker 使用仓库 macOS Python 环境原生运行；也可显式构建 `linux/amd64` 镜像进行模拟，但速度较慢。不得把 ARM 调试镜像描述成已验证的本地 Paddle 脱敏运行时。

## 2. 配置

```bash
cd /path/to/study
cp infra/compose/.env.example infra/compose/.env
openssl rand -hex 32
```

编辑 `infra/compose/.env`：

- 替换 `POSTGRES_PASSWORD`、`MINIO_ROOT_PASSWORD` 和 `STUDY_AUTH_SECRET`。
- `DATABASE_URL` 必须把主机写成 `postgres`，并与 PostgreSQL 用户、密码、数据库名一致。
- `WEB_PORT` 是家长 Web 对宿主机暴露的端口，默认 `3000`；Web 容器内部始终通过 `http://api:8000` 访问 API。
- `STUDY_API_TOKEN` 可先留空以启动 Web 健康页；要显示家长数据，必须填入由 API 签发的 parent Bearer token，然后重启 Web。
- 如果 NewAPI 在宿主机，使用 `http://host.docker.internal:<port>`；如果在另一台机器或另一个 Compose 网络，填写容器可访问的 URL。Adapter 会自动补齐 `/v1/chat/completions`，因此 base URL 可以是根地址或以 `/v1` 结尾。
- 初次部署保持 `STUDY_NEWAPI_ENABLED=false`。确认 NewAPI 视觉模型、key 和响应契约后，再改为 `true`。

不要把 `infra/compose/.env`、真实 API key、儿童图片或真实题目写入仓库。

## 3. 校验与启动

```bash
docker compose -f infra/compose/compose.yml config

docker compose -f infra/compose/compose.yml up -d --build

docker compose -f infra/compose/compose.yml ps

curl http://127.0.0.1:${API_PORT:-8000}/healthz
curl http://127.0.0.1:${WEB_PORT:-3000}/healthz
```

首次 amd64 构建会安装 PaddleOCR 依赖并下载五份锁定模型，可能明显慢于后续启动；原生 ARM 构建会跳过该不兼容依赖和模型。Web 构建使用 Node 24.18.0 和 pnpm 11.7.0，并生成 Next.js standalone 镜像。`migrate` 只执行 `alembic upgrade head`，成功后退出；API 依赖其成功状态，Web 依赖 API 健康状态。ImageAnalysis worker 是默认服务：`STUDY_NEWAPI_ENABLED=false` 时保持安全空闲，不连接 Provider、不读取图片，也不会反复重启。迁移是前滚式的，Compose 不会自动 downgrade。

查看日志时只看稳定状态，不要把请求体、图片、令牌或 NewAPI key 粘贴到工单或聊天中：

```bash
docker compose -f infra/compose/compose.yml logs --tail=100 api migrate image-analysis-worker
```

Web 日志：

```bash
docker compose -f infra/compose/compose.yml logs --tail=100 web
```

## 4. 启用 NewAPI 图片分析

在 `infra/compose/.env` 设置：

```dotenv
STUDY_NEWAPI_ENABLED=true
STUDY_NEWAPI_BASE_URL=http://host.docker.internal:3000
STUDY_NEWAPI_API_KEY=your_local_newapi_key
STUDY_NEWAPI_VISION_MODEL=your_vision_model
```

然后仅重建/重启 API 和已在默认 profile 中的 worker：

```bash
docker compose -f infra/compose/compose.yml \
  up -d --build api image-analysis-worker
```

只有客户端已确认、且服务端保存的 SHA-256 与 Capture 一致的脱敏副本会进入 worker。worker 只保存 Schema 校验后的未确认 `QuestionExtraction`，不会把它直接当作答案或 Tutor 学习事实。失败只记录稳定失败状态；关闭开关后新 worker 不再领取任务。

认证令牌在 API 容器中签发，密钥不进入客户端镜像：

```bash
docker compose -f infra/compose/compose.yml exec api \
  python scripts/issue_auth_token.py \
  --household-id <household-uuid> --role parent
```

将命令输出的令牌写入 `infra/compose/.env` 的 `STUDY_API_TOKEN` 后，仅重启 Web：

```bash
docker compose -f infra/compose/compose.yml up -d web
```

## 5. 停止、升级和回滚

```bash
# 停止容器但保留 PostgreSQL/MinIO/Redis 数据卷
docker compose -f infra/compose/compose.yml down

# 查看卷；不要在未确认备份前执行 down -v
docker volume ls | grep study
```

升级步骤：先备份 PostgreSQL 和 MinIO 数据，再拉取/切换到目标代码版本，运行 `config`，执行 `up -d --build`，确认 `migrate` 成功和 `/healthz` 正常。发生应用问题时先关闭 NewAPI 开关并停止 worker；数据库迁移优先前向修复，不对 Attempt/AuditEvent 做破坏性回滚。

当前未提供自动备份、恢复演练、Retention worker 或生产级监控；不要把 `down -v` 当作清理儿童数据的正式删除流程，也不要把本 Compose 暴露到公网。

## 6. 最小验收

```bash
docker compose -f infra/compose/compose.yml ps
curl -fsS http://127.0.0.1:${API_PORT:-8000}/healthz
curl -fsS http://127.0.0.1:${WEB_PORT:-3000}/healthz
docker compose -f infra/compose/compose.yml logs --no-log-prefix migrate | tail -20
```

然后使用 synthetic 图片完成一次：Bearer 认证 → Capture 预签名上传 → 服务端对象 SHA-256 确认 → 用户确认脱敏副本 → ImageAnalysis 入队。真实儿童图片只在确认生命周期、删除和备份方案后再使用。
