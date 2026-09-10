# AIStudy 构建与自托管部署

本文说明如何通过 GitHub Actions 构建 Android APK、部署单家庭 Compose 服务、连接孩子端，以及把有权使用的电子教材导入 AIStudy。当前流程面向家庭自用和测试，不代表公网、应用商店或商业生产发布已经获批。

## 1. 交付物与边界

| 交付物 | 生成方式 | 当前边界 |
| --- | --- | --- |
| Android APK | GitHub Actions `Build Android APK` | 默认是 runner debug 证书签名的 evaluation 包；配置稳定密钥后才是可持续升级的自签名包 |
| API、Web、Worker、可选本地模型 | `infra/compose/compose.yml` + `infra/compose/compose.local-model.yml` | 单家庭自托管；`infra/compose/compose.sh` 根据 `STUDY_LOCAL_MODEL_ENABLED` 选择是否加载 Compose 内部 Qwen3.5-4B Q4_K_M；关闭时不创建 `local-model`；不应直接暴露到公网 |
| PostgreSQL、Redis、MinIO | 同一 Compose | MinIO 只在 Compose 内部可达，不发布 `9000` |
| 英语口语 | 客户端和 Provider 中立框架 | 真实 Provider 未接入，默认锁定 |
| 教材 PDF | 家长在 Web 选择 SmartEdu 公开目录，或自行合法取得后上传 | 下载内容只进入家庭私有存储和审核链路，不进入 Git 仓库，不随 AIStudy 分发，不因 Apache-2.0 获得额外授权 |

## 2. 推送到 GitHub

本地仓库的目标远程为：

```text
git@github.com:yubinhong/AIStudy.git
```

首次推送前确认没有 `.env`、密钥、数据库、儿童资料、图片或教材：

```bash
git remote -v
git status --short
git diff --check
git push -u origin master
```

仓库的默认分支应设为 `master`。手动运行 GitHub Actions 要求工作流文件已经存在于默认分支，而且操作者对仓库有写权限。

## 3. GitHub Actions 构建 APK

工作流位于 `.github/workflows/android-apk.yml`，使用固定 Flutter `3.44.6` 和 Java 17。它会依次执行：

1. 从 Flutter 官方仓库检出固定版本并缓存 SDK。
2. `flutter pub get` 安装锁定依赖。
3. 检查 Dart 格式、运行 `flutter analyze` 和全部 Flutter 测试。
4. 按 ABI 构建 release APK。
5. 生成 `SHA256SUMS` 和 `BUILD-INFO.txt`。
6. 上传保留 14 天的 GitHub Actions Artifact。
7. 如果由 `v*` 标签触发，从 `CHANGELOG.md` 提取同名版本区块，创建或更新中文 GitHub Release，并上传 APK、摘要和构建信息。

工作流不会接收 API URL、Session、Provider Key 或教材。应用首次启动时由用户在登录页配置家庭 API 地址。

### 手动构建

1. 打开 GitHub 仓库的 **Actions** 页面。
2. 选择 **Build Android APK**。
3. 点击 **Run workflow**，选择 `master` 后确认。
4. 等待 `Test and build split APKs` 完成。
5. 在该次运行底部下载名称以 `aistudy-android-` 开头的 Artifact。

也可以使用 GitHub CLI：

```bash
gh workflow run android-apk.yml --ref master
gh run list --workflow android-apk.yml
```

### 标签发布到 GitHub Release

推送 `v` 开头的标签会触发构建，并在全部 Flutter 检查通过后自动创建或更新同名 GitHub Release。发布前必须先在 `CHANGELOG.md` 增加唯一的对应版本区块；GitHub Actions 会严格读取该区块作为 Release 正文，缺少或重复时直接失败：

```markdown
## v0.18.0 - 2026-09-10

### 更新内容

- 用中文记录本次用户可感知变化。
```

```bash
# 代码和 CHANGELOG.md 必须先在同一提交中完成，并推送该提交。
git add <changed-files> CHANGELOG.md
git commit -m "feat(web): 本次更新摘要"
git push origin master

git tag -a v0.18.0 -m "v0.18.0：本次更新摘要"
git push origin v0.18.0
```

Release 正文来自该版本区块，不使用 GitHub 的默认 `--generate-notes`；重新运行同一标签的 workflow 时会同步更新正文并覆盖同名附件，不重复创建 Release。Release 附件包含三个 APK、`SHA256SUMS` 和 `BUILD-INFO.txt`，可直接从仓库 **Releases** 页面下载。手动运行仍只生成 Actions Artifact，不会创建没有版本标签的 Release。两种触发方式都不会推送应用商店或部署服务器。

### APK 文件选择

Artifact 解压后或 GitHub Release 附件中包含：

- `app-arm64-v8a-release.apk`：大多数现代 Android 手机和平板，包括常见华为 ARM64 设备。
- `app-armeabi-v7a-release.apk`：较旧的 32 位 ARM 设备。
- `app-x86_64-release.apk`：主要用于 x86_64 模拟器。
- `SHA256SUMS`：APK SHA-256 摘要。
- `BUILD-INFO.txt`：提交 SHA、Flutter 版本和签名模式。

## 4. Android 签名

### 无 Secrets 的 evaluation 构建

如果仓库没有配置 Android 签名 Secrets，Gradle 会使用 GitHub runner 临时生成的 debug 证书签署 release APK。它可以用于侧载测试，但不同 workflow run 的证书可能不同，后续安装可能提示签名不一致并要求先卸载旧 App。卸载会清除设备上的本地会话和离线队列。

不要把这种包上传 Google Play，也不要把它称为正式发布包。当前应用 ID 仍为 `com.example.study_child`，正式发布前也必须更换为项目唯一 ID。

### 配置稳定自签名密钥

在可信的离线或本地环境生成并备份 keystore：

```bash
keytool -genkeypair -v \
  -keystore aistudy-upload.jks \
  -keyalg RSA -keysize 2048 -validity 10000 \
  -alias aistudy
```

将 keystore 编码成单行 Base64：

```bash
base64 < aistudy-upload.jks | tr -d '\n'
```

在 GitHub 仓库 **Settings → Secrets and variables → Actions** 中添加四个 Repository secrets：

| Secret | 内容 |
| --- | --- |
| `ANDROID_KEYSTORE_BASE64` | 上一步产生的单行 Base64 |
| `ANDROID_KEYSTORE_PASSWORD` | keystore 密码 |
| `ANDROID_KEY_ALIAS` | 示例中的 `aistudy` |
| `ANDROID_KEY_PASSWORD` | key 密码 |

四项必须同时存在，否则工作流会失败。工作流只在临时 runner 内以权限最小化方式写入 `android/key.properties` 和 keystore；两者均被 `.gitignore` 排除。不要把 keystore、密码或 Base64 内容提交到仓库、Issue、Actions 日志或聊天中。

稳定签名密钥一旦用于安装，后续升级必须继续使用同一密钥。密钥丢失可能导致无法覆盖安装已有 App，因此应保存在至少两个受控、加密的离线位置。

## 5. 校验和安装 APK

在 Artifact 解压目录验证摘要：

Linux：

```bash
sha256sum -c SHA256SUMS
```

macOS：

```bash
shasum -a 256 -c SHA256SUMS
```

通过 ADB 安装 ARM64 包：

```bash
adb devices
adb install -r app-arm64-v8a-release.apk
```

若出现 `INSTALL_FAILED_UPDATE_INCOMPATIBLE`，说明设备上的旧包与新包签名不同。先确认旧数据是否需要保留；evaluation 包通常只能卸载旧包后重新安装。不要为了绕过该错误共享或提交签名私钥。

首次启动后，在登录页填写 Android 设备可以访问的 API 地址，例如：

```text
http://192.168.1.20:8000
```

地址必须是服务器的局域网地址，不能填写 Android 自己的 `127.0.0.1`。修改服务端地址会清除旧会话。公网访问应先建立受信 HTTPS 反向代理、证书和正式安全评审；当前文档不批准直接公网暴露 API/Web。

## 6. 部署自托管服务

### 前置条件

- Linux x86_64 或 ARM64 主机。
- Docker Engine 与 Docker Compose v2。
- 能访问 GHCR；私有 Package 需要一个只具备 `read:packages` 的 GitHub 凭据。
- 至少为 PostgreSQL、MinIO、镜像和备份预留充足磁盘空间。
- 家庭局域网内固定或可发现的服务器地址。
- 可选 NewAPI；如果不启用本地模型，没有 NewAPI 时保持 AI Provider 关闭，基础服务仍可启动。

### 配置

```bash
git clone git@github.com:yubinhong/AIStudy.git
cd AIStudy
cp infra/compose/.env.example infra/compose/.env
chmod 600 infra/compose/.env
openssl rand -hex 32
```

编辑 `infra/compose/.env`：

1. 为 `POSTGRES_PASSWORD` 和 `MINIO_ROOT_PASSWORD` 设置不同的高强度随机值。
2. 同步更新 `DATABASE_URL` 中的 PostgreSQL 密码，主机名必须保持 `postgres`。
3. 初次部署保持 `STUDY_NEWAPI_ENABLED=false`。
4. 保持 `STUDY_ENGLISH_LIVE_ENABLED=false` 和 `STUDY_ENGLISH_LIVE_PROVIDER=disabled`。
5. 不添加客户端密钥、真实教材内容、儿童资料或 Session。
6. 将 `STUDY_API_IMAGE` 与 `STUDY_WEB_IMAGE` 固定到同一次 GitHub Actions 发布的相同 `v*` 或 `sha-*` 标签；`latest` 只适合跟随 `master` 的临时自用环境。

GitHub Actions 只在 `master` 或 `v*` 标签的契约、API、Web 和隔离浏览器检查全部通过后发布镜像。Pull Request 不发布。Package 为 private 时，在部署主机先登录，令牌不得进入命令历史、`.env` 或日志：

```bash
printf '%s' "$GHCR_READ_TOKEN" | docker login ghcr.io -u <github-user> --password-stdin
```

### 启动和验证

```bash
infra/compose/compose.sh config
infra/compose/compose.sh pull
infra/compose/compose.sh up -d --remove-orphans
infra/compose/compose.sh ps

curl -fsS http://127.0.0.1:8000/healthz
curl -fsS http://127.0.0.1:3000/healthz
```

确认 `migrate` 成功退出，API、Web、PostgreSQL、Redis、MinIO 和常驻 worker 健康：

```bash
infra/compose/compose.sh logs --tail=100 migrate api web
```

日志不得复制到公开 Issue，除非已经确认其中没有 Session、密钥、儿童资料、题目、教材文字或对象键。

空数据库会建立一次性 `admin/admin123456` 引导账号。只在服务器本机或受信家庭局域网首次登录并立即改密；改密前家庭数据接口会被阻断。随后在家长 Web 创建孩子档案和孩子账号，孩子 App 使用该账号登录。

更完整的 Compose 配置、NewAPI、备份恢复和架构限制见 [Compose 部署说明](../infra/compose/README.md) 与 [运维手册](../RUNBOOK.md)。

本地模型模式：复制 `infra/compose/.env.example` 后设置 `STUDY_LOCAL_MODEL_ENABLED=true`，再使用 `infra/compose/compose.sh`。脚本会自动叠加 `compose.local-model.yml`，启动 `llama.cpp` 并从配置的 Hugging Face GGUF 仓库加载 `Qwen3.5-4B` 的 `Q4_K_M` 权重和视觉 projector；模型端口不发布到宿主/LAN。开启本地模式后 API、ImageAnalysis worker、CurriculumAnalysis worker 的所有当前 NewAPI-compatible 请求都只发给本地服务，不会在失败时静默切回云端。首次启动后应先用不含儿童数据的 synthetic 文本/图片和 Schema eval 验证，再进行家庭使用；模型来源、镜像摘要、目标硬件质量和成本/延迟记录仍是独立验收项。设置为 `false` 时基础 Compose 不定义 `local-model`，不会拉取或启动该镜像。

## 7. 获取和导入电子教材

家长 Web 的“选择教材并加载”已内置 SmartEdu 公开目录适配器，参考了 [tchMaterial-parser](https://github.com/happycola233/tchMaterial-parser)（MIT）对目录版本文件、教材详情、PDF 存储候选和 URL 绑定 MAC 的解析方式。AIStudy 自己实现适配器，不安装或调用上游工具，不向浏览器显示第三方 PDF 直链；默认免配置，严格私有 CDN 需要登录时，家长按页面“如何获取”从本人 SmartEdu 登录会话复制 JSON 到页面。JSON 至少包含 `access_token`，`mac_key` 与 `diff` 可省略；服务端只在本次下载请求中使用它，并把 50 MiB 上限、PDF 文件头和 SHA-256 校验后的内容写入家庭私有存储，凭据不进入数据库、日志、镜像或返回值。Web 将凭据和同一孩子/资源的幂等键临时保存在当前标签页 `sessionStorage`，刷新后可继续重试，手动清除/退出登录/关闭标签页后清除；服务端命中已完成结果时会在下载前回放。凭据缺失或过期时页面会明确提示更新，仍可改用本地 PDF 上传。

推荐流程：

1. 登录 AIStudy 家长 Web，选择当前孩子、学科和年级，在“公共教材目录”搜索并点击“加载为草稿”。
2. 在确认框中确认自己有权使用教材、不对外分发，并确认文件不含儿童姓名、个人批注或其他个人信息；跨家庭精确复用另行勾选。
3. 等待私有下载和本地解析完成，在“教材快照”查看原页/知识图谱，家长审核后再发布；发布前 Tutor/任务不会引用。
4. 如果页面提示需要登录，按页面“如何获取”在自己登录 SmartEdu 的同一浏览器控制台运行脚本，复制输出的整段 JSON 粘贴到页面；只含 `access_token` 也可以，`mac_key` 和 `diff` 是可选增强字段。凭据会临时留在当前标签页以支持刷新重试和连续加载，手动清除、退出登录或关闭标签页后清除；不要把原值放进聊天、命令历史、日志或工单。
5. 不把 PDF、派生页图、解析结果或教材题库提交到 AIStudy 仓库，也不对外二次分发。

上游项目明确说明它不托管教材，资源版权属于原平台和相关权利人，并要求用户遵守平台条款。AIStudy 的 Apache-2.0 只覆盖本仓库贡献者有权授权的代码和文档，不覆盖下载工具、教材或用户导入数据。

## 8. 升级、备份和回滚

升级服务前先验证备份：

```bash
infra/compose/scripts/backup.sh /srv/study-backups
infra/compose/scripts/verify-restore.sh /srv/study-backups/<UTC_TIMESTAMP>
```

然后拉取明确代码版本，将两个镜像变量固定到该版本对应的同一镜像标签，再拉取并启动：

```bash
git fetch --tags origin
git checkout <approved-tag-or-commit>
infra/compose/compose.sh config
infra/compose/compose.sh pull
infra/compose/compose.sh up -d --remove-orphans
infra/compose/compose.sh ps
```

回滚应用时把 `STUDY_API_IMAGE` 与 `STUDY_WEB_IMAGE` 一起改回上一个已验证的 `v*` 或 `sha-*` 标签，再执行 `pull` 和 `up -d`。保留 PostgreSQL、MinIO 和 Redis 卷，不执行 `down -v`，也不在正式数据上随意运行数据库 downgrade。Android 回滚必须使用相同签名密钥和兼容的版本号；如果旧 APK 不接受新数据库/API 合同，应优先做前向修复。

## 9. 尚未完成的生产门槛

- 登录态浏览器 E2E 和完整设备生命周期回归。
- 正式 Android application ID、图标、版本策略、稳定签名保管和 Play Store AAB 流程。
- 公网 HTTPS、反向代理、监控告警、依赖/镜像安全扫描和异机加密备份。
- 真实教材质量、Provider 成本和儿童数据法务审批。
- 合规英语语音 Provider、监护人同意文本和真实安全评测。

在这些门槛完成前，GitHub Actions 成功只证明该提交能通过自动检查并生成 APK/服务镜像，不证明它已经达到应用商店或商业生产发布条件。
