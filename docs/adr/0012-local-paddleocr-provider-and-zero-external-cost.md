# ADR-0012：本地 PaddleOCR Provider、人工确认与零外部成本

- 状态：`Accepted`
- 日期：`2026-07-13`
- Owner：`项目 Owner（用户）`
- 决策者：`项目 Owner（用户；2026-07-13 对话确认）`
- 关联：`TASK-0006`、`TODO-008`、`TODO-009`、`ADR-0004`
- 替代/被替代：细化 `ADR-0004` 的 OCR Provider 默认路由
- 批准记录：项目 Owner 选择本地 PaddleOCR 为默认 OCR，外部商业 Provider 仅作为将来可选插件；默认外部费用上限为 0 元，图片不得默认发送到外部服务。

## Context

OCR 是 Capture 闭环的一部分，但商业 Provider 会引入儿童图片外传、数据处理条款、区域、成本和供应商锁定风险。项目已要求 Provider Adapter 与人工确认，尚未选择默认 OCR 实现。

## Decision

- OCR 服务运行时固定为 Python `3.12.x`，默认 Provider 为本地运行的 `paddleocr[doc-parser]==3.7.0` 与 CPU 运行时 `paddlepaddle==3.3.1`；运行设备固定为 `cpu`，推理引擎固定为 `paddle_static`。图片默认不发送到任何外部服务，默认外部费用上限为 `0 元`。
- 普通拍题默认使用 `PP-OCRv6_medium_det` 检测与 `PP-OCRv6_medium_rec` 识别；照片方向使用 `PP-LCNet_x1_0_doc_ori`，文本行方向使用 `PP-LCNet_x1_0_textline_ori`；公式按需使用 `PP-FormulaNet_plus-M`。
- 未列入锁定清单的文档去畸变模型（例如 PaddleOCR 默认可能尝试使用的 `UVDoc`）关闭；Provider 工厂禁用模型源连通性检查，缺少镜像内模型时直接失败，不触发外部检查、下载或更新。
- 五个模型的推理归档必须在镜像构建阶段从锁定来源下载，并与版本控制中的模型清单逐项比对 SHA-256；清单缺失、摘要不匹配、归档结构异常或模型目录不完整时构建失败。运行时只读取镜像内的预置目录，禁止自动下载、更新或切换模型来源；当前仓库的构建清单以 Paddle 官方归档为来源。
- 整页文档理解不进入当前 P1 Capture 范围；未来需要时通过独立 Adapter 接入 PP-StructureV3。
- 所有 OCR 结果都必须由孩子或家长人工确认/校正后，才能进入后续 Tutor、错因或掌握度流程；OCR 输出不作为标准答案或业务事实。
- 商业 OCR Provider 仅能作为可选插件，通过同一 Provider Adapter 接入，并需单独批准数据处理条款、区域、训练退出、预算、固定评测和功能开关；默认关闭。

## Consequences

- 本地算力、模型下载、镜像/包许可证、模型版本、延迟和设备资源成为实施时需要验证的成本。
- PaddleOCR 与公式模型版本按本 ADR 锁定。依赖只增加 API/Worker 服务端体积、模型文件和 CPU 资源消耗，不进入 Flutter/Web 客户端；替代方案是商业 Provider 插件或其他本地 OCR 引擎，但它们默认关闭且须独立评审。锁文件更新后仍须复核许可证、维护状态、传递依赖、模型来源/校验和、CPU 延迟和内存上限，并建立固定 synthetic eval。
- `0 元` 仅约束默认外部 Provider 调用成本，不代表本地硬件、电力或维护成本为零。

## Compatibility and Migration

- Capture `0.5.0` 已有私有上传签发/确认和人工校正；未来 OCR 结果以向后兼容的候选结果、置信度、模型/Provider 版本和确认状态增量引入。
- Provider 路由变化必须保留可回滚版本，不能改变已确认校正记录的含义。
- 回滚时关闭 OCR Adapter，Capture 继续进入人工校正路径；不得降级为外部默认传图。

## Validation

- 建立固定 synthetic OCR 评测集，覆盖普通文字、公式、低置信度、空结果、模型失败、人工确认、延迟和本地资源上限。
- 验证默认网络路径没有向外部 OCR 服务发送图片；商业插件默认关闭且无凭据时不可调用。
