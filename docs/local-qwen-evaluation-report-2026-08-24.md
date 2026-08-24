# Qwen3.5-4B Q4_K_M 本地部署测试与重新选型调研输入

- 测试日期：2026-08-24
- 测试环境：家庭自用 Ubuntu 24.04 x86_64，12 GB 内存，先后使用 4 核和 8 核 CPU
- 当前结论：`Qwen3.5-4B Q4_K_M` 不满足本项目的本地多模态生产使用要求
- 当前运行状态：Ubuntu 已关闭本地模型并显式恢复现有 NewAPI 云端配置；模型缓存保留供后续重新选型
- 数据边界：全部使用 synthetic 文本和 synthetic 图片；未使用真实儿童数据、教材 PDF 或设备照片

## 1. 执行摘要

当前方案可以在 12 GB 内存的 CPU 服务器上稳定加载，短文本 JSON 请求可在约 1.4 秒返回，8 核视觉推理也能使用接近全部 CPU。但是，本项目真正需要的 `question-extraction.v1` 图片结构化请求在两次目标机测试中都未通过：

1. 12 GB / 4 核：600 秒内未得到可接受的 Schema 输出，评测不收敛。
2. 12 GB / 8 核：373.128 秒生成到 2048 token 上限后返回，但输出不符合 Schema，错误为 `provider_response_schema_invalid`。

增加 CPU 只改善了吞吐和完成时间，没有解决结构化输出质量。单次合成图片仍需约 6 分 13 秒，而且最终不可用。由于所有 AI 请求在本地模式下都统一路由到该模型，视觉失败会直接阻断拍题解析、教材理解和依赖图片的学习流程。因此，当前模型不能作为本项目默认本地 AI Provider。

## 2. 项目需要本地模型承担的工作

本地模式通过同一个 OpenAI-compatible Provider Adapter 服务以下能力：

- 确认脱敏后的单题图片解析，输出严格的 `question-extraction.v1` JSON。
- 教材页图片分批理解，形成带页码和来源证据的结构化知识图谱草稿。
- 数学 Tutor 的分层提示、错题讲解和完整讲解。
- 语文看图写话的观察问题和句式支架，禁止直接代写作文。
- 基于服务端提供的有界候选进行来源受限的任务推荐。

其中图片解析和教材理解是硬门槛。模型输出必须通过既有 JSON Schema、来源校验、Tutor Policy 和人工确认，不能因为模型运行在本地而放宽验证。

## 3. 已部署配置

| 项目 | 配置 |
| --- | --- |
| 推理服务 | `ghcr.io/ggml-org/llama.cpp:server-b9603` |
| GGUF 仓库 | `bjivanovich/Qwen3.5-4B-Vision-GGUF` |
| 模型权重 | `Qwen3.5-4B.Q4_K_M.gguf`，约 2.708 GB |
| 视觉 projector | `Qwen3.5-4B.BF16-mmproj.gguf`，约 675 MB |
| 服务别名 | `Qwen3.5-4B-Q4_K_M` |
| 上下文 | 8192 tokens |
| 并发 | 1 |
| 最大输出 | 2048 tokens |
| 请求超时 | 600 秒 |
| 最大图片请求 | 600,000 bytes，服务端有界压缩 |
| reasoning | 结构化请求关闭 thinking |
| 路由 | 本地开关开启时只访问本地模型，不自动回退云端 |
| 网络 | 模型端口仅在 Compose 内网开放 |

llama.cpp 在 4 核启动时报告 `n_threads = 4`，扩容重启后报告 `n_threads = 8`。8 核视觉请求期间容器 CPU 约为 778% 至 795%，说明不是因为只使用了部分 CPU 核心而失败。

## 4. 测试方法

### 4.1 短文本 JSON smoke

通过 OpenAI-compatible `/v1/chat/completions` 请求模型只返回：

```json
{"ok": true}
```

请求使用 `temperature=0`、`max_tokens=32`、`response_format=json_object`，并关闭 thinking。该测试只验证基础文本生成、JSON 模式和服务连通性，不代表 Tutor 或视觉质量通过。

### 4.2 完整 synthetic 视觉评测

运行仓库既有命令：

```bash
docker compose -f infra/compose/compose.yml exec -T api \
  python scripts/run_newapi_live_eval.py
```

评测动态生成一张 2200 x 1600 的噪声背景 PNG，其中包含白色题目区域和文本 `Math: 3/4 + 1/8 = ?`。图片经过与实际 Provider 请求相同的有界压缩，再要求模型返回完整 `question-extraction.v1` 结构。评测结果仍须通过应用层 Schema 校验。

重新调研时可直接核对以下实现，而不必根据本报告猜测合同：

- JSON Schema：`packages/contracts/schemas/question-extraction.v1.json`
- Provider 提示词和本地配置：`services/api/src/study_api/newapi_provider.py`
- synthetic 图片和完整清理流程：`services/api/scripts/run_newapi_live_eval.py`
- llama.cpp 启动参数：`infra/compose/compose.yml`
- 环境变量样例：`infra/compose/.env.example`

为避免常驻 worker 与前台评测竞争同一任务，测试期间只暂停 ImageAnalysis worker；评测结束后恢复。脚本通过 `finally` 删除 synthetic 任务、会话、Capture、Job、Extraction、幂等记录和审计记录。

## 5. 实测结果

| 指标 | 12 GB / 4 核 | 12 GB / 8 核 |
| --- | ---: | ---: |
| 模型推理线程 | 4 | 8 |
| 短文本总耗时 | 约 1.7 秒 | 1.387 秒 |
| 短文本生成速度 | 约 10 token/s | 12.03 token/s |
| 完整视觉评测耗时 | 600 秒内未收敛 | 373.128 秒 |
| 视觉 prompt | 未取得完整最终统计 | 2556 tokens / 107.732 秒 / 23.73 token/s |
| 视觉生成 | 超过合理 Schema 长度 | 2048 tokens / 260.608 秒 / 7.86 token/s |
| 视觉最终状态 | 失败 | 失败 |
| 视觉错误 | 600 秒内无可接受结果 | `provider_response_schema_invalid` |
| 模型内存 | 初始约 3.8 GiB；长请求缓存后约 6.4 GiB | 运行中约 5.87 GiB |
| Swap | 0 | 0 |

8 核完整视觉请求的 llama.cpp 最终统计：

```text
prompt eval time = 107731.96 ms / 2556 tokens (23.73 tokens per second)
eval time        = 260607.57 ms / 2048 tokens (7.86 tokens per second)
total time       = 368339.54 ms / 4604 tokens
```

应用层评测输出：

```json
{
  "dispatch_status": "failed",
  "error_code": "provider_response_schema_invalid",
  "input_exceeds_provider_limit": true,
  "job_attempt": 1,
  "job_status": "failed",
  "model": "Qwen3.5-4B-Q4_K_M",
  "provider_enabled": true
}
```

评测后 synthetic 任务数和对应幂等记录数均为 0。API `0.17.0`、Web、本地模型和四个 worker 均恢复运行；模型内存未挤占 Swap。

## 6. 结论与判定

### 已通过

- 模型和视觉 projector 可加载，服务健康检查通过。
- OpenAI-compatible 文本请求和简单 JSON 对象可用。
- 12 GB 内存可承载当前完整 Compose 栈和模型，测试中没有使用 Swap。
- 8 核推理线程生效，长视觉任务能使用接近全部 CPU。
- 本地/云端显式切换、私有端口和失败不自动外发的路由边界有效。

### 未通过

- 严格视觉 JSON Schema 输出。
- 可接受的图片交互延迟。
- 在 2048 输出 token 上限内收敛。
- 拍题、教材理解和看图写话等真实多模态质量门槛。
- 固定真实题型、真实 PDF 和设备照片评测。

### 最终判定

`Qwen3.5-4B Q4_K_M` 在当前 llama.cpp、GGUF、projector 和 CPU-only 部署组合下判定为 **不可用于本项目的统一本地模型**。不能用“短文本 smoke 通过”替代多模态验收，也不建议通过增加超时或输出 token 上限掩盖失败：当前 8 核已经生成 2048 tokens，仍无法形成合法 Schema，继续放宽只会增加延迟和资源占用。

在完成重新选型前，应关闭 `STUDY_LOCAL_MODEL_ENABLED`，让已配置的云端 Provider 承担 AI 请求；系统不会自动跨 Provider 回退。

## 7. 请 ChatGPT 重新调研的问题

请基于截至 2026-08-24 的官方模型卡、官方推理文档和 llama.cpp 兼容性资料重新调研，并明确区分已证实事实、推断和需要实机验证的项目。不要只按参数量或宣传 benchmark 推荐。

1. 在 8 核 x86_64 CPU、12 GB 总内存、无已配置 GPU 加速且需与 API/PostgreSQL/Redis/MinIO/Web 共存的条件下，是否存在真正可用的本地多模态模型？
2. 候选必须支持中文、小学数学题图、OpenAI-compatible 调用、严格结构化 JSON、至少 8192 context，并在 12 GB 内存内稳定运行。请给出 3 至 5 个有官方依据的候选和明确淘汰项。
3. 分别核对每个候选的原始模型许可证、GGUF 发布来源、量化版本、视觉 projector、推荐 chat template、llama.cpp 最低版本和已知兼容问题。不要把第三方仓库名称当成官方兼容证明。
4. 判断当前失败更可能来自模型能力、Q4_K_M 量化、视觉 projector、chat template、llama.cpp multimodal 支持、JSON Schema 约束方式，还是 4B 参数规模；给出可验证的排查顺序。
5. 调研 llama.cpp grammar/JSON Schema constrained decoding 是否适用于候选多模态模型，以及它能否防止 2048-token 非法结构输出，而不只是事后解析失败。
6. 比较“一个统一视觉语言模型”和“本地 OCR/版面分析 + 文本模型”的方案。本项目已有本地 PaddleOCR，是否应让 OCR/确定性图像处理负责识别，再由更可靠的文本模型生成受限结构？
7. 给出每个候选在该硬件上的预估内存、prompt 处理速度、生成速度和单图延迟范围，并标注估算依据及不确定性。不得把 GPU benchmark 外推成 CPU 结论。
8. 建议一个最小实机淘汰矩阵：简单 JSON、单题图片、手写/空白/未拍到答题区四态、中文教材页、4 页教材批次、Tutor L1/L2、Schema 合法率、P50/P95 延迟和峰值内存。
9. 给出明确的 Go/No-Go 标准。当前项目尚未批准交互延迟 SLO，请提出合理候选值并标记为需要项目 Owner 确认，而不是当成既定需求。
10. 如果 12 GB / 8 核 CPU 无法达到可用标准，请直接说明，并分别给出最低可行的内存、CPU、GPU/统一内存升级路线和继续使用云端模型的成本/隐私权衡。

## 8. 期望的调研输出格式

请按以下结构返回：

1. 一页结论：12 GB / 8 核是否可行，推荐继续本地还是回到云端。
2. 候选对比表：能力、结构化输出、运行时兼容、内存、CPU 延迟、许可证、来源风险。
3. 当前 Qwen 失败根因假设：按概率和验证成本排序。
4. 首选方案与备选方案：包括精确模型文件、量化、projector、运行时版本和启动参数。
5. 可复制执行的 synthetic 测试步骤和淘汰阈值。
6. 需要项目 Owner 决定的成本、隐私、硬件和延迟取舍。

任何推荐都必须先通过 synthetic Schema 门禁，再允许使用脱敏家庭图片；不能用真实儿童数据做初次模型筛选。
