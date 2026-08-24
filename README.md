# AIStudy — 家庭学习助手

AIStudy 是给一个家庭自己使用的小学生学习助手。孩子在平板或手机上学习，家长在网页上管理孩子、上传有权使用的教材，并查看学习记录。

它目前更适合家庭局域网内自用，不是面向公众开放的网站，也不替代老师、家长或学校的判断。

## 能帮孩子做什么

### 数学

- 拍下已经做过的题，孩子先说明自己的想法，再获得一步一步的提示。
- 做错的题会进入复习清单，到时间后再练一次。
- 家长安排的今日任务会带着指定题目进入拍题；多道题会按顺序完成，孩子也可以先跳过。
- 断网时已经确认的作答、任务完成和跳过会先保存在本机，恢复联网后先同步作答，再按顺序完成任务状态；不会保存图片、答案原文或登录令牌。
- 家长可以查看记录、导出家庭数据或删除数据。

### 语文

- **古诗抽查**：家长上传并审核教材后，系统从教材中的古诗随机出题。屏幕给出上一句，孩子选择下一句；答错会立即显示正确答案，并安排以后复习。
- **看图写话**：孩子拍照或从相册选图，先看画面，再回答引导问题，写出第一句，最后补充细节。系统只提供观察和表达的提示，**不会代写作文，也不会给作文打分**；图片服务暂时不可用时仍可从通用观察问题开始。

### 英语

英语入口暂时锁定，尚未接入真实语音服务，不能作为日常学习功能使用。

## 家长最关心的事

- 每个家庭、家长和孩子都有独立账号，不能互相查看学习记录。
- 图片会先在家庭自己的设备和服务里处理；只有家长确认后的处理版本才可能发送给已批准的 AI 服务。
- 系统不会把 AI 的回答直接当成标准答案。拍题结果需要确认后才会进入学习记录。
- 请只上传家庭有权使用的教材，不上传包含孩子姓名、联系方式或个人批注的材料。
- 不要把登录密码、密钥、孩子照片、教材文件或学习记录提交到 GitHub。

## 现在能用到什么程度

| 功能 | 当前情况 |
| --- | --- |
| 家长网页 | 可以管理孩子、上传审核教材、查看记录、导出和删除数据 |
| 孩子端 | 可以登录、学习数学、按题完成今日任务、古诗抽查、看图写话、拍题和复习；断网作答会稍后同步 |
| 看图写话 | 已有拍照/相册、三步引导、空句阻断和安全通用降级；仍需继续做不同真实图片的体验验证 |
| 古诗抽查 | 从已审核教材自动出题，答题结果由固定规则判断 |
| 英语 | 暂未开放 |
| 自用部署 | 已在家庭 Ubuntu 服务器运行；不等同于公开网站或商业服务 |

Ubuntu 当前运行 API/OpenAPI `0.17.0`、迁移 `0036_task_session_progress`。服务器配有 12 GB 内存和 8 个 CPU 核心；本地 `Qwen3.5-4B Q4_K_M` 已完成测试但因视觉质量门禁失败而停止，当前 AI 请求使用现有 NewAPI 云端配置。跨设备任务位置、每天最多 3 项、未来任务保护、家长撤销、语文教材批准后自动古诗出题和看图写话安全降级由 tag `v0.17.0` 固化；可切换本地模型路由是后续增量。备份、恢复校验、模型测试、健康检查和仍待完成的设备/Provider 验证见 [RUNBOOK.md](RUNBOOK.md) 和 [TESTING.md](TESTING.md)。

## 家庭使用流程

1. 家长在网页创建孩子账号，并打开需要的学科。
2. 家长上传自己有权使用、且不含个人信息的教材，审核后才会用于出题。
3. 孩子在设备上登录，选择数学或语文学习。
4. 家长定期查看记录和到期复习，需要时导出或删除家庭数据。

## 给维护者的安装说明

下面内容用于在家庭服务器上安装和维护本项目。普通使用者不需要执行这些命令。

### 首次启动

目标 GitHub 仓库：`git@github.com:yubinhong/AIStudy.git`

```bash
git clone git@github.com:yubinhong/AIStudy.git
cd AIStudy
cp infra/compose/.env.example infra/compose/.env
```

编辑 `infra/compose/.env`，至少替换 PostgreSQL、MinIO 和 Session Secret。初次启动应保持所有外部 Provider 开关关闭。

```bash
docker compose -f infra/compose/compose.yml config
docker compose -f infra/compose/compose.yml up -d --build
docker compose -f infra/compose/compose.yml ps

curl -fsS http://127.0.0.1:8000/healthz
curl -fsS http://127.0.0.1:3000/healthz
```

空数据库会创建一次性 `admin/admin123456` 引导账号。只应在受信本机或家庭局域网首次登录，并立即修改密码；改密前家庭数据接口会被阻断。不要把默认账号暴露到公网。

完整配置、Apple Silicon 限制、NewAPI 接入、备份与恢复步骤见 [infra/compose/README.md](infra/compose/README.md) 和 [RUNBOOK.md](RUNBOOK.md)。

### AI 模型路由

Compose 支持在本地 Qwen 和现有 NewAPI 云端模型之间进行显式切换：

- `STUDY_LOCAL_MODEL_ENABLED=true`：启动 `Qwen3.5-4B Q4_K_M`，当前所有 AI 大模型请求统一走本地 OpenAI-compatible 服务。请求失败时不会静默回退到云端，避免同一份内容在未确认时被外发。
- `STUDY_LOCAL_MODEL_ENABLED=false`：不加载本地权重，恢复现有 `STUDY_NEWAPI_*` 云端路由；云端仍需单独设置 `STUDY_NEWAPI_ENABLED=true` 和有效配置。

本地模型首次启动会下载约数 GB 权重并写入持久化 Docker volume，所需时间取决于网络。若只有 Docker 守护进程能访问外网，可设置仅传给模型容器的 `STUDY_LOCAL_MODEL_PROXY_URL`。家庭 Ubuntu 服务器使用 12 GB 内存、8 个 CPU 核心和 `8192` context 对 `Qwen3.5-4B Q4_K_M` 完成了两轮 synthetic 测试：4 核下完整视觉请求 600 秒内未收敛；8 核下短文本 JSON 为 1.387 秒，但 synthetic 数学大图耗时 373.128 秒、生成到 2048 token 上限后仍因 `provider_response_schema_invalid` 失败。模型运行中约占 5.87 GiB，未使用 Swap。该结果说明增加 CPU 可以改善吞吐，但不能解决当前模型、量化和运行时组合的视觉 Schema 质量，不应把短文本 smoke 通过视为多模态可用。

因此 Ubuntu 当前设置为 `STUDY_LOCAL_MODEL_ENABLED=false`，本地模型容器已停止，模型缓存保留以便后续重新选型；所有已启用的 AI 请求显式使用现有 NewAPI 云端配置。切换后 synthetic 数学文本 Schema smoke 在 3.591 秒内通过，API、Web 和四个 worker 保持运行。本地与云端不会在单次请求失败时自动互相回退，切换必须修改开关并重启 API 和 AI worker。开关和模型参数示例见 [infra/compose/.env.example](infra/compose/.env.example)，完整 4 核/8 核证据、限制和后续调研问题见 [本地 Qwen 测试报告](docs/local-qwen-evaluation-report-2026-08-24.md)。上述结果只使用 synthetic 数据，不代表真实教材、真实儿童图片、完整 Tutor 质量或设备验收通过。

## Android APK 与部署

仓库提供 `Build Android APK` GitHub Actions：手动运行时生成保留 14 天的 Actions Artifact；推送 `v*` 标签时还会自动创建对应 GitHub Release，并上传三个 ABI APK、SHA-256 摘要和构建信息。工作流使用固定 Flutter `3.44.6`，发布 Job 才获得最小 `contents: write` 权限。

未配置 Android 签名 Secrets 时，产物使用 runner 的 debug 证书，只适合家庭侧载验证；稳定升级和正式分发必须配置受控签名密钥并更换当前示例 application ID。GitHub Actions 操作、签名配置、APK 安装、Compose 服务端部署、升级和回滚见 [构建与自托管部署指南](docs/DEPLOYMENT.md)。

## 电子教材

项目可配合独立的 [tchMaterial-parser](https://github.com/happycola233/tchMaterial-parser) 获取国家中小学智慧教育平台电子课本 PDF。该工具不是 AIStudy 依赖，AIStudy 不接收其 Access Token，也不包含或分发下载的教材。请只下载和导入自己有权使用的资料，并遵守平台条款、教材版权和当地法律；完整安全导入步骤见 [部署指南的教材章节](docs/DEPLOYMENT.md#7-获取和导入电子教材)。

## 本地开发与验证

API：

```bash
cd services/api
uv sync --locked
uv run ruff format --check .
uv run ruff check .
uv run mypy src
uv run pytest -m "not integration"
```

Web：

```bash
cd apps/web
pnpm install --frozen-lockfile
pnpm format:check
pnpm lint
pnpm typecheck
pnpm test
pnpm build
```

Flutter：

```bash
cd apps/child_flutter
flutter pub get
dart format --output=none --set-exit-if-changed .
flutter analyze
flutter test
```

具体已验证结果、已知全仓失败和设备门槛以 [TESTING.md](TESTING.md) 为准；不要仅因单元测试通过就宣称真实 Provider、真实教材或生产发布已验收。

## 数据、内容与第三方组件

Apache-2.0 只授权本仓库贡献者拥有权利的代码和文档，不自动授权以下内容：

- 用户上传的教材、题库、作业图片、学习记录或其他家庭数据；
- AI/OCR 模型权重、模型服务、API Key 或外部 Provider 输出；
- 第三方依赖、字体、图标和原生库，这些内容继续适用各自许可证；
- 项目名称、标识或第三方商标超出合理来源说明的使用。

Flutter 直接依赖与原生音频组件的通知见 [apps/child_flutter/THIRD_PARTY_NOTICES.md](apps/child_flutter/THIRD_PARTY_NOTICES.md)。其他依赖版本和来源以各子项目锁文件为准。

## 贡献与安全

提交代码前请先阅读 [AGENTS.md](AGENTS.md) 的长期边界和 [TESTING.md](TESTING.md) 的验证要求。变更公共 API、数据库、安全边界或 AI Provider 时，需要同步 OpenAPI/Schema、迁移、测试和相关 ADR。

安全问题不要附带真实密钥、儿童数据、图片、教材或数据库转储。处理和报告要求见 [SECURITY.md](SECURITY.md)。

## 许可证

本仓库自有代码和文档采用 [Apache License 2.0](LICENSE)。该协议允许使用、修改和分发，并包含明确的贡献者专利授权；分发时须保留许可证、NOTICE 和适用的归属声明。
