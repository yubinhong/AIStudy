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

- 默认 Provider 为本地运行的 PaddleOCR；图片默认不发送到任何外部服务，默认外部费用上限为 `0 元`。
- 普通文字 OCR 优先使用轻量模型；公式使用 PaddleOCR 的公式识别能力。
- 整页文档理解不进入当前 P1 Capture 范围；未来需要时通过独立 Adapter 接入 PP-StructureV3。
- 所有 OCR 结果都必须由孩子或家长人工确认/校正后，才能进入后续 Tutor、错因或掌握度流程；OCR 输出不作为标准答案或业务事实。
- 商业 OCR Provider 仅能作为可选插件，通过同一 Provider Adapter 接入，并需单独批准数据处理条款、区域、训练退出、预算、固定评测和功能开关；默认关闭。

## Consequences

- 本地算力、模型下载、镜像/包许可证、模型版本、延迟和设备资源成为实施时需要验证的成本。
- PaddleOCR 与公式模型的具体运行时/包版本尚未加入依赖；实现前必须锁定版本，记录许可证、维护状态、替代方案、供应链风险和服务端体积，并更新测试/评测入口。
- `0 元` 仅约束默认外部 Provider 调用成本，不代表本地硬件、电力或维护成本为零。

## Compatibility and Migration

- Capture `0.4.0` 当前只支持人工校正；未来 OCR 结果以向后兼容的候选结果、置信度、模型/Provider 版本和确认状态增量引入。
- Provider 路由变化必须保留可回滚版本，不能改变已确认校正记录的含义。
- 回滚时关闭 OCR Adapter，Capture 继续进入人工校正路径；不得降级为外部默认传图。

## Validation

- 建立固定 synthetic OCR 评测集，覆盖普通文字、公式、低置信度、空结果、模型失败、人工确认、延迟和本地资源上限。
- 验证默认网络路径没有向外部 OCR 服务发送图片；商业插件默认关闭且无凭据时不可调用。
