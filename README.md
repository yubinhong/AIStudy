# 家庭 AI 学习助手

面向小学阶段家庭的开源、可控、可离线学习闭环：任务 → 作答 → 分步提示 → 错题/复习 → 家长反馈。

当前已完成 P0 家庭/孩子/设备合成纵向切片。API 提供 Household-scoped ChildProfile/Device 路由，Web/Flutter 已接入演示消费入口；真实身份、持久化、离线同步、Capture/OCR、Tutor 和 Provider 尚未实现。

## 仓库入口

- `AI_CONTEXT.md`：当前状态和文档导航
- `TASK.md`：唯一活动任务（当前为 `TASK-0002`）
- `TESTING.md`：命令、测试矩阵和质量门槛
- `ARCHITECTURE.md` / `PRD.md` / `SECURITY.md`：目标架构、产品和安全基线
- `packages/contracts`：OpenAPI/JSON Schema 唯一契约源

## 已验证的本地命令

```bash
cd services/api
uv sync --locked
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
uv run pytest -m "not integration"

cd ../../apps/web
pnpm install --frozen-lockfile
pnpm format:check
pnpm lint
pnpm typecheck
pnpm test
pnpm build

cd ../..
docker compose -f infra/compose/compose.yml config
```

Flutter SDK 当前位于本地工作区的 `flutter/`（已加入忽略规则），`apps/child_flutter/pubspec.lock` 已生成；原生 iOS/Android 构建仍需要完整 Xcode/CocoaPods 或 Android SDK。

## 安全边界

开发和测试只使用合成数据。不要提交密钥、令牌、真实儿童资料、题目图片、生产转储或 Provider 凭据。未经授权的教材、题库和教辅内容不进入仓库。
