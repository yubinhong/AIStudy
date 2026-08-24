# ADR-0028：可切换的本地 Qwen 模型路由

- 状态：`Accepted`
- 日期：`2026-08-23`
- Owner：项目 Owner + API/运维负责人
- 决策者：项目 Owner（用户；要求在部署服务中增加 Qwen3.5-4B Q4_K_M，并以环境变量切换本地/云端）
- 关联：`ADR-0004`、`ADR-0015`、`ADR-0022`、`ADR-0023`
- 替代/被替代：补充并细化现有 NewAPI Provider 路由；不取消题目确认、教材审核、Tutor Policy 或单 Provider 安全边界

## Context

当前 API 和两个 AI worker 通过同一个 OpenAI-compatible `NewApiVisionProvider` 访问 NewAPI。图片分析、教材分析、Tutor、看图写话和推荐规划都依赖该适配器，但部署层没有可复用的本地多模态模型服务。需求是在不让业务模块分别判断 Provider 的前提下，在部署服务中提供 Qwen3.5-4B Q4_K_M，并允许家庭在本地模型和现有云端配置之间切换。

## Decision Drivers

- 本地模型必须能同时处理当前的文本和已确认脱敏图片请求。
- API、ImageAnalysis worker 和 CurriculumAnalysis worker 必须使用同一个路由结果，不能出现部分请求外发云端的隐式回退。
- 本地模型服务不能把 GGUF/模型下载端口暴露到宿主或 LAN；模型缓存需要持久化以避免每次重启重新下载。
- 关闭本地开关时保持现有 NewAPI 行为和既有 Provider 关闭保护。
- 本地模型输出仍必须经过现有固定 Schema、Tutor Policy、来源校验和人工确认，不因“本地”而放宽儿童数据边界。

## Considered Options

1. 继续只使用 NewAPI，在各业务路由中加入本地分支。改动分散，容易遗漏 worker 或产生云端旁路。
2. 使用 Ollama 作为本地服务。部署体验较简单，但对指定 GGUF、多模态 projector 和当前 OpenAI-compatible 结构化响应行为需要额外适配。
3. 使用 `llama.cpp` server，以 Q4_K_M GGUF 和自动发现的视觉 projector 提供内部 OpenAI-compatible `/v1/chat/completions`。它与现有 Adapter 契约最接近，CPU 可运行，也可以通过镜像替换为硬件加速构建。

## Decision

选择选项 3。

1. Compose 增加 `local-model` 服务，默认使用 `ghcr.io/ggml-org/llama.cpp:server-b9603`，通过 `-hf` 从 `bjivanovich/Qwen3.5-4B-Vision-GGUF:Q4_K_M` 加载 Q4_K_M 权重，并自动加载可用的视觉 projector。模型缓存挂载到 `local-model-cache`，服务不发布宿主端口。
2. `STUDY_LOCAL_MODEL_ENABLED=true` 时，API 和两个 AI worker 的 `NewApiConfig.from_environment()` 强制生成 `local_qwen` 配置，忽略云端 NewAPI URL、key 和模型；本地请求统一指向 `http://local-model:8080/v1`，并通过 `chat_template_kwargs.enable_thinking=false` 关闭 Qwen reasoning，保证固定 JSON Schema 请求有可解析的 `content`。关闭时仍只读取 `STUDY_NEWAPI_*` 配置。
3. Compose 在开关关闭时让本地容器保持空闲，在开启时等待 `/health` 通过后再启动 API/相关 worker。这样同一 Compose 拓扑支持两种模式，不把模型下载和推理端口暴露给家庭 LAN。
4. Provider、模型名和 Tutor Policy 记录使用实际路由名称；云端历史继续使用 `newapi`，本地新记录使用 `local_qwen`。不增加公共 OpenAPI 字段或数据库迁移。

## Consequences

### Positive

- 所有现有文本/视觉模型调用共享一个开关和同一 Provider Adapter，避免云端旁路。
- Q4_K_M 模型缓存可复用，CPU 部署默认可运行；有 GPU 的部署者可以替换 llama.cpp 镜像和运行参数。
- 本地模式下儿童题目、确认后的脱敏图、教材页派生图和 Tutor 上下文只在家庭 Compose 网络内流转。

### Negative / Trade-offs

- Qwen3.5-4B Q4_K_M 的 GGUF 与视觉 projector 默认来自外部量化仓库，首次启动需要网络和约数 GB 的缓存；在真实儿童数据前必须复核来源、许可证、文件摘要和模型质量。
- 本地 4B 模型的速度、结构化输出、中文教学质量和视觉识别不能由配置代码推断，必须用固定合成 eval 和目标硬件实测。
- 本地模型服务关闭或加载失败时不会自动回退到云端；需要显式关闭本地开关并重启 API/worker，避免违反“全量本地”预期。

## Compatibility, Migration, and Rollback

- 无数据库迁移和公共 OpenAPI 变更；旧客户端无需升级。新增环境变量缺省为关闭，旧 `.env` 继续选择现有 NewAPI 路径。
- 启用顺序为：备份配置和数据 → 更新 Compose/API → 设置本地变量 → 首次下载并检查 `local-model` 健康 → 运行 synthetic text/vision/schema eval → 再使用家庭数据。
- 回滚只需设置 `STUDY_LOCAL_MODEL_ENABLED=false` 并重启 API、ImageAnalysis worker 和 CurriculumAnalysis worker；保留模型缓存和已有学习事实，不执行数据库 downgrade，不自动把失败请求发往云端。
- 若模型仓库、镜像或模型质量异常，停用本地服务并恢复已验证的 NewAPI 配置；不得把未经评测的本地输出直接当作 VerifiedQuestion、标准答案、教材知识点或掌握事实。

## Validation

- 单元测试验证本地开关优先于云端配置、关闭时保留 NewAPI 配置、记录实际 Provider/model，以及本地结构化请求关闭 reasoning。
- `docker compose config` 验证服务、健康检查、依赖和模型缓存配置；本机 Linux ARM64 已在本地开启后验证 `/health`、`/v1/models` 和一个不含儿童数据的文本/图片 Schema 请求。
- 固定 AI eval 必须覆盖 JSON Schema 失败、题目/作答四态、Tutor L1/L2 答案泄露、教材来源键、中文看图写话边界和成本/延迟记录。真实 PDF、儿童图片、设备质量和生产开放仍是独立门禁。
