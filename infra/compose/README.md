# Docker Compose 自托管部署

这套 Compose 适合单家庭、自用部署，包含 PostgreSQL、Redis、私有 MinIO、FastAPI API、家长 Web、数据库迁移一次性服务、AI worker、可切换的 llama.cpp 本地模型服务和数据生命周期 worker。Compose 会从同目录的 `.env` 注入服务变量，不需要在启动命令中传入 `--env-file`。云端 NewAPI 仍由部署者单独提供；API 通过 OpenAI-compatible `/v1/chat/completions` 访问。

当前本地和 Ubuntu 服务端状态：API `0.17.0`、迁移头 `0036_task_session_progress`；本次 Ubuntu 发布先来自未提交工作区，现已由 `v0.17.0` 提交/tag 固化，详细备份和验收记录见根目录 `RUNBOOK.md`。账号密码/可撤销会话、PostgreSQL 业务事实、MinIO、ImageAnalysis/VerifiedQuestion/TutorTurn、独立 `picture_writing_guides`、周报/导出、家长 Web、worker 和备份恢复脚本已实现。真实自动视觉检测器、正式监控和四设备回归仍未完成，因此本文件提供的是自用部署说明，不是公网或商业生产发布证明。

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

- 替换 `POSTGRES_PASSWORD`、`MINIO_ROOT_PASSWORD`、NewAPI key 和视觉模型配置；首次启动后必须在本机使用 `admin/admin123456` 登录并立即改密。
- `DATABASE_URL` 必须把主机写成 `postgres`，并与 PostgreSQL 用户、密码、数据库名一致。
- `WEB_PORT` 是家长 Web 对宿主机暴露的端口，默认 `3000`；Web 容器内部始终通过 `http://api:8000` 访问 API。
- Capture 图片现在由 App 携带登录 Session 通过 API 的有界原始字节流上传，API 在内部校验并写入私有 MinIO。MinIO 的 S3 API 和控制台不映射到宿主机或局域网；不要配置 `OBJECT_STORAGE_PUBLIC_ENDPOINT_URL`、`MINIO_API_PORT` 或预签名上传地址。
- Compose 只使用账号密码认证。Web 登录后会通过 HttpOnly Cookie 保存会话；不要把会话或密码写入 `.env`、客户端构建参数或日志。HMAC、Demo Header 和 Web 免登录旁路已删除。
- 如果 NewAPI 在宿主机，使用 `http://host.docker.internal:<port>`；如果在另一台机器或另一个 Compose 网络，填写容器可访问的 URL。Adapter 会自动补齐 `/v1/chat/completions`，因此 base URL 可以是根地址或以 `/v1` 结尾。
- 初次部署保持 `STUDY_NEWAPI_ENABLED=false`。确认 NewAPI 视觉模型、key 和响应契约后，再改为 `true`。
- Adapter 默认以 `study-api/0.5` 作为 `User-Agent`，避免部分 Cloudflare 规则拦截 Python `urllib` 的默认特征；如前置网关要求其他值，可设置 `STUDY_NEWAPI_USER_AGENT`，但只允许 1–256 个可打印 ASCII 字符，不能包含换行或其他控制字符。
- `STUDY_NEWAPI_MAX_IMAGE_BYTES` 默认 `600000`。更大的已确认脱敏图会在 worker 内存中去元数据、等比缩放并重编码为 JPEG 后再 base64 传输，用于避开 NewAPI/反向代理请求体上限；不要把该值调高到网关限制以上。
- `STUDY_LOCAL_MODEL_ENABLED=true` 会让 API、ImageAnalysis worker 和 CurriculumAnalysis worker 统一使用 Compose 内部 `local-model` 的 Qwen3.5-4B Q4_K_M；云端 NewAPI 配置会被忽略，不存在自动云端回退。`false` 时本地容器空闲，路由回到 `STUDY_NEWAPI_*`。
- 本地模型默认使用 `ghcr.io/ggml-org/llama.cpp:server-b9603`、`Qwen3.5-4B.Q4_K_M.gguf` 和 `Qwen3.5-4B.BF16-mmproj.gguf`，会从 `bjivanovich/Qwen3.5-4B-Vision-GGUF` 显式下载到 `local-model-cache`。未完成的 `.part` 文件会在容器重启后断点续传，完整文件不会重复下载。首次启动需要网络和数 GB 磁盘；正式家庭数据前应固定镜像摘要、核对模型文件来源/许可证并完成目标硬件质量评测。
- 本地模型不发布宿主端口；API 通过 `http://local-model:8080/v1` 访问。只有模型缓存持久化，推理请求不进入云端；不要把 `STUDY_LOCAL_MODEL_API_KEY` 当作云端密钥或写入日志。
- 如果 Docker 守护进程可以拉取镜像、但容器不能直接访问 Hugging Face，可只为模型服务设置 `STUDY_LOCAL_MODEL_PROXY_URL`。该值映射到 `local-model` 的标准代理环境变量，不会传给 API 或 worker；可直连时保持为空。
- 本地 CPU 视觉推理默认超时为 `600` 秒；云端 NewAPI 上限仍为 `120` 秒。当前 4 核 Ubuntu 的大图结构化视觉请求可能需要数分钟，不适合低延迟交互。不要用增加超时掩盖持续卡死，调整前先记录目标硬件的 synthetic 延迟和内存。
- 本地输出固定受 `STUDY_LOCAL_MODEL_MAX_OUTPUT_TOKENS` 约束（默认 `2048`），且本地超时/网络失败不自动重复推理；云端仍使用既有的最多三次瞬时重试。这样模型不收敛时会返回可见失败，而不是长时间占满 CPU 或切换 Provider。
- DataLifecycle worker 固定删除超过 180 天、且不再被开放错题引用的详细题目/讲解和已结束复习链路。紧急调查时可设置 `LEARNING_HISTORY_CLEANUP_ENABLED=false` 暂停后续清理；不要改变代码中的 180 天策略或手工删除开放错题。

不要把 `infra/compose/.env`、真实 API key、儿童图片或真实题目写入仓库。

## 3. 校验与启动

```bash
docker compose -f infra/compose/compose.yml config

docker compose -f infra/compose/compose.yml up -d --build

docker compose -f infra/compose/compose.yml ps

curl http://127.0.0.1:${API_PORT:-8000}/healthz
curl http://127.0.0.1:${WEB_PORT:-3000}/healthz
```

首次 amd64 构建会安装 PaddleOCR 依赖并下载五份锁定模型，可能明显慢于后续启动；原生 ARM 构建会跳过该不兼容依赖和模型。Web 构建使用 Node 24.18.0 和 pnpm 11.7.0，并生成 Next.js standalone 镜像。`migrate` 只执行 `alembic upgrade head`，成功后退出；API 依赖其成功状态，Web 依赖 API 健康状态。ImageAnalysis worker 在 `STUDY_NEWAPI_ENABLED=false` 时安全空闲，不连接 Provider、不读取图片；DataLifecycle worker 默认每 300 秒清理到期 Capture 对象、24 小时导出快照和超过 180 天的可清理详细学习历史，只记录计数。迁移是前滚式的，Compose 不会自动 downgrade。

查看日志时只看稳定状态，不要把请求体、图片、令牌或 NewAPI key 粘贴到工单或聊天中：

```bash
docker compose -f infra/compose/compose.yml logs --tail=100 api migrate image-analysis-worker data-lifecycle-worker
```

Web 日志：

```bash
docker compose -f infra/compose/compose.yml logs --tail=100 web
```

## 4. 启用本地 Qwen 模型

在 `infra/compose/.env` 设置：

```dotenv
STUDY_LOCAL_MODEL_ENABLED=true
STUDY_LOCAL_MODEL_NAME=Qwen3.5-4B-Q4_K_M
STUDY_LOCAL_MODEL_HF_REPO=bjivanovich/Qwen3.5-4B-Vision-GGUF
STUDY_LOCAL_MODEL_MODEL_FILE=Qwen3.5-4B.Q4_K_M.gguf
STUDY_LOCAL_MODEL_MMPROJ_FILE=Qwen3.5-4B.BF16-mmproj.gguf
STUDY_LOCAL_MODEL_BASE_URL=http://local-model:8080/v1
# 仅在模型容器不能直连 Hugging Face 时设置：
STUDY_LOCAL_MODEL_PROXY_URL=
```

然后重启本地模型和所有会调用 AI 的服务：

```bash
docker compose -f infra/compose/compose.yml up -d local-model api image-analysis-worker curriculum-analysis-worker
docker compose -f infra/compose/compose.yml ps local-model api image-analysis-worker curriculum-analysis-worker
docker compose -f infra/compose/compose.yml logs --tail=100 local-model
```

`local-model` 首次启动会下载 Q4_K_M 权重和视觉 projector，`health` 变为 `200` 后 API/worker 才会继续启动。验证只使用不含儿童数据的 synthetic 请求；模型输出仍必须通过现有 Schema、人工确认、Tutor Policy 和教材审核门禁。

关闭本地模型并恢复云端路径：

```bash
STUDY_LOCAL_MODEL_ENABLED=false docker compose -f infra/compose/compose.yml up -d api image-analysis-worker curriculum-analysis-worker
```

Shell 中的临时变量不会修改 `.env`；要持久切换，请编辑 `infra/compose/.env` 后执行同一重启命令。关闭本地模型不会删除缓存、学习记录或数据库事实。

## 5. 启用 NewAPI 图片分析

在 `infra/compose/.env` 设置：

```dotenv
STUDY_NEWAPI_ENABLED=true
STUDY_NEWAPI_BASE_URL=http://host.docker.internal:3000
STUDY_NEWAPI_API_KEY=your_local_newapi_key
STUDY_NEWAPI_VISION_MODEL=your_vision_model
STUDY_NEWAPI_USER_AGENT=study-api/0.5
```

然后仅重建/重启 API 和已在默认 profile 中的 worker（且 `STUDY_LOCAL_MODEL_ENABLED=false`）：

```bash
docker compose -f infra/compose/compose.yml \
  up -d --build api image-analysis-worker
```

只有客户端已确认、且服务端保存的 SHA-256 与 Capture 一致的脱敏副本会进入 worker。worker 只保存 Schema 校验后的未确认 `QuestionExtraction`，不会把它直接当作答案或 Tutor 学习事实。失败只记录稳定失败状态；关闭开关后新 worker 不再领取任务。

首次启动后，在服务器本机访问家长 Web，使用一次性 `admin/admin123456` 登录并完成首次改密；改密前 API 会阻断家庭数据接口。改密成功后，家长可以在“孩子账号”页面创建、停用、启用和重置孩子账号。Flutter 孩子端在登录页先填写对 iPad/Android 可达的 API 地址（例如 `http://192.168.1.4:8000`），再使用孩子账号密码登录。地址和会话由系统安全存储持久化，更换地址会先清除旧会话。

## 6. 停止、升级和回滚

```bash
# 停止容器但保留 PostgreSQL/MinIO/Redis 数据卷
docker compose -f infra/compose/compose.yml down

# 查看卷；不要在未确认备份前执行 down -v
docker volume ls | grep study
```

升级步骤：先备份 PostgreSQL 和 MinIO 数据，再拉取/切换到目标代码版本，运行 `config`，执行 `up -d --build`，确认 `migrate` 成功和 `/healthz` 正常。本地和当前 Ubuntu 目标 head 为 `0036_task_session_progress`；回退应用时保留新增表、列和索引，不在正式数据上执行 downgrade。发生学习历史范围异常时先设置 `LEARNING_HISTORY_CLEANUP_ENABLED=false` 并重启 DataLifecycle worker，再前向修复；已经按策略删除的数据不能靠应用回滚恢复。发生 Provider 问题时关闭 NewAPI 开关并停止 ImageAnalysis worker；不得破坏性回滚 Profile、Account、Attempt 或 AuditEvent。

### 备份与恢复验证

备份脚本会暂时停止全部应用写入者，生成 PostgreSQL custom dump、MinIO quiesced 快照和 SHA-256 清单，然后自动恢复服务。默认输出到被 Git 忽略的 `infra/compose/backups/`，也可传入宿主机专用目录：

```bash
infra/compose/scripts/backup.sh /srv/study-backups
infra/compose/scripts/verify-restore.sh /srv/study-backups/<UTC_TIMESTAMP>
```

恢复验证只在一次性隔离的 `postgres:16.10` 容器中执行，不覆盖运行中的数据库。脚本验证 MinIO 快照文件和全部摘要，但正式灾难恢复时仍需运维人员在停机窗口把验证过的快照恢复到新卷。备份包含 Restricted 数据，宿主目录必须权限最小化并另行配置加密/异机副本；仓库不保存备份或密钥。

当前未提供定时备份调度或生产级监控；不要把 `down -v` 当作清理儿童数据的正式删除流程，也不要把本 Compose 暴露到公网。

## 7. 最小验收

```bash
docker compose -f infra/compose/compose.yml ps
curl -fsS http://127.0.0.1:${API_PORT:-8000}/healthz
curl -fsS http://127.0.0.1:${WEB_PORT:-3000}/healthz
docker compose -f infra/compose/compose.yml logs --no-log-prefix migrate | tail -20
```

然后使用 `docker compose -f infra/compose/compose.yml exec -T api python scripts/run_newapi_live_eval.py` 完成一次不含真实数据的合成大图链路；输出只能包含状态、计数、模型名和布尔门禁，不包含题目原文、对象键或密钥。设备端仍需人工验证拍照、权限、脱敏预览、弱网和重启。
