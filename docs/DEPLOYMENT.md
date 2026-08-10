# AIStudy 构建与自托管部署

本文说明如何通过 GitHub Actions 构建 Android APK、部署单家庭 Compose 服务、连接孩子端，以及把有权使用的电子教材导入 AIStudy。当前流程面向家庭自用和测试，不代表公网、应用商店或商业生产发布已经获批。

## 1. 交付物与边界

| 交付物 | 生成方式 | 当前边界 |
| --- | --- | --- |
| Android APK | GitHub Actions `Build Android APK` | 默认是 runner debug 证书签名的 evaluation 包；配置稳定密钥后才是可持续升级的自签名包 |
| API、Web、Worker | `infra/compose/compose.yml` | 单家庭自托管；不应直接暴露到公网 |
| PostgreSQL、Redis、MinIO | 同一 Compose | MinIO 只在 Compose 内部可达，不发布 `9000` |
| 英语口语 | 客户端和 Provider 中立框架 | 真实 Provider 未接入，默认锁定 |
| 教材 PDF | 家长自行合法取得并通过 Web 上传 | 不进入 Git 仓库，不随 AIStudy 分发，不因 Apache-2.0 获得额外授权 |

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
7. 如果由 `v*` 标签触发，创建同名 GitHub Release 并上传 APK、摘要和构建信息。

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

推送 `v` 开头的标签会触发构建，并在全部 Flutter 检查通过后自动创建同名 GitHub Release：

```bash
git tag v0.1.0
git push origin v0.1.0
```

Release 附件包含三个 APK、`SHA256SUMS` 和 `BUILD-INFO.txt`，可直接从仓库 **Releases** 页面下载。重新运行同一标签的 workflow 时会覆盖同名附件，不重复创建 Release。手动运行仍只生成 Actions Artifact，不会创建没有版本标签的 Release。两种触发方式都不会推送应用商店或部署服务器。

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
- 至少为 PostgreSQL、MinIO、镜像和备份预留充足磁盘空间。
- 家庭局域网内固定或可发现的服务器地址。
- 可选 NewAPI；没有它时保持图片 Provider 关闭，基础服务仍可启动。

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

### 启动和验证

```bash
docker compose -f infra/compose/compose.yml config
docker compose -f infra/compose/compose.yml up -d --build
docker compose -f infra/compose/compose.yml ps

curl -fsS http://127.0.0.1:8000/healthz
curl -fsS http://127.0.0.1:3000/healthz
```

确认 `migrate` 成功退出，API、Web、PostgreSQL、Redis、MinIO 和常驻 worker 健康：

```bash
docker compose -f infra/compose/compose.yml logs --tail=100 migrate api web
```

日志不得复制到公开 Issue，除非已经确认其中没有 Session、密钥、儿童资料、题目、教材文字或对象键。

空数据库会建立一次性 `admin/admin123456` 引导账号。只在服务器本机或受信家庭局域网首次登录并立即改密；改密前家庭数据接口会被阻断。随后在家长 Web 创建孩子档案和孩子账号，孩子 App 使用该账号登录。

更完整的 Compose 配置、NewAPI、备份恢复和架构限制见 [Compose 部署说明](../infra/compose/README.md) 与 [运维手册](../RUNBOOK.md)。

## 7. 获取和导入电子教材

[tchMaterial-parser](https://github.com/happycola233/tchMaterial-parser) 是独立的 MIT 开源桌面工具，可从国家中小学智慧教育平台解析和下载电子课本 PDF，并支持批量下载、自动命名和书签。它不是 AIStudy 的依赖、子模块或内置下载器，AIStudy 不调用它、不接收它的 Access Token，也不随仓库分发它下载的教材。

推荐流程：

1. 从该项目的 [Releases](https://github.com/happycola233/tchMaterial-parser/releases) 获取适合自己系统的版本，或按其 README 从源码运行。
2. 按上游说明使用工具，并遵守国家中小学智慧教育平台条款、教材版权和所在地法律。
3. Access Token 只保留在本地工具中，不写入 AIStudy `.env`，不上传 GitHub，也不粘贴到日志或 Issue。
4. 下载后确认 PDF 来源合法、仅用于获准的个人学习或教学场景，并确认文件不含儿童姓名、个人批注或其他个人信息。
5. 登录 AIStudy 家长 Web，在当前孩子作用域上传 PDF，等待私有解析和教材理解，再逐页审核并明确发布。
6. 不把 PDF、派生页图、解析结果或教材题库提交到 AIStudy 仓库，也不对外二次分发。

上游项目明确说明它不托管教材，资源版权属于原平台和相关权利人，并要求用户遵守平台条款。AIStudy 的 Apache-2.0 只覆盖本仓库贡献者有权授权的代码和文档，不覆盖下载工具、教材或用户导入数据。

## 8. 升级、备份和回滚

升级服务前先验证备份：

```bash
infra/compose/scripts/backup.sh /srv/study-backups
infra/compose/scripts/verify-restore.sh /srv/study-backups/<UTC_TIMESTAMP>
```

然后拉取明确版本，检查差异并重建：

```bash
git fetch --tags origin
git checkout <approved-tag-or-commit>
docker compose -f infra/compose/compose.yml config
docker compose -f infra/compose/compose.yml up -d --build
docker compose -f infra/compose/compose.yml ps
```

回滚应用时保留 PostgreSQL、MinIO 和 Redis 卷，不执行 `down -v`，也不在正式数据上随意运行数据库 downgrade。Android 回滚必须使用相同签名密钥和兼容的版本号；如果旧 APK 不接受新数据库/API 合同，应优先做前向修复。

## 9. 尚未完成的生产门槛

- 登录态浏览器 E2E 和完整设备生命周期回归。
- 正式 Android application ID、图标、版本策略、稳定签名保管和 Play Store AAB 流程。
- 公网 HTTPS、反向代理、监控告警、依赖/镜像安全扫描和异机加密备份。
- 真实教材质量、Provider 成本和儿童数据法务审批。
- 合规英语语音 Provider、监护人同意文本和真实安全评测。

在这些门槛完成前，GitHub Actions 成功只证明该提交能通过自动检查并生成 APK，不证明它已经达到应用商店或商业生产发布条件。
