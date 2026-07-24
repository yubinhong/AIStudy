# TASK.md — TASK-0010 教材原页、知识图谱与可用任务整改

## 当前任务元数据

- 状态：`IN_PROGRESS（PLAN-0018 已部署 Ubuntu 0.11.0/0025；真实教材/NewAPI/E2E 待验收）`
- 类型：`FEATURE / API CONTRACT / DEVICE`
- 优先级：`P0`
- Owner：Codex（执行）；项目 Owner（用户，要求教材图片语义、整本知识归纳和错题任务立即可用）
- 创建/更新：`2026-07-18`
- 关联：`PLAN-0018`、`ADR-0020`、`ADR-0021`、`ADR-0022`、`ADR-0023`

## 当前目标与验收

修复教材 PDF 丢失图片语义和任务推荐使用残缺文字的问题：保留受鉴权原页，云端分批理解页面并归纳整本知识图谱，家长批准后才允许发布和推荐；推荐只使用开放错题与已批准知识点/具体练习。

- [x] PDF 逐页生成有界私有 JPEG，原件/页图不返回对象键、MinIO URL 或预签名地址。
- [x] NewAPI 每批最多 4 页多模态理解，再以严格 Schema 归纳整本章节、知识点、目标、先修关系和练习来源。
- [x] `0025` 保存页图、页级分析、知识图谱、知识点和 AI 版本/指纹/延迟/token/成本字段。
- [x] Web 以原页为主、文字为辅助，展示知识图谱并提供家长批准；批准前 PDF 不可发布。
- [x] 推荐不再读取 `CurriculumChunk.text` 抽题，只使用批准知识点中的来源题与全部开放错题。
- [x] OpenAPI `0.11.0`、API 非集成测试、mypy/相关 ruff、Web test/build、Flutter test/analyze、迁移 offline SQL 和本机 PostgreSQL 前滚已通过。
- [x] 依赖教材图片的任务在 Flutter 显示视觉说明，并通过孩子 Session 受鉴权打开对应原页；客户端限制 JPEG/2 MiB。
- [ ] 真实 118 页 PDF/NewAPI 输出质量、费用和失败重试验收；浏览器/设备 E2E。

回滚：停止 `curriculum-analysis-worker` 并禁用知识图谱推荐；保留原 PDF、已生成私有页图和既有学习事实。`0025` 只新增表/可空外键，可在无新引用时 downgrade；不得恢复残缺文字抽题。

## 2026-07-24 Ubuntu 前滚记录

- 结果：在不读取家庭或教材内容的前提下，Ubuntu 单家庭 Compose 已从 API `0.10.0`/Alembic `0024_intelligent_recommendations` 成对前滚到 API `0.11.0`/`0025_curriculum_knowledge_map`；API、Web、ImageAnalysis、MaterialParse、CurriculumAnalysis 和 DataLifecycle worker 均健康，MinIO `9000` 仍无宿主端口映射。
- 发布前：修复备份脚本遗漏教材 worker 且使用 `docker compose start` 无法满足已完成 migrate 依赖的问题。脚本现在冻结所有实际存在的写入 worker，并直接恢复其原容器；`/home/syin/study-backups/20260724T015356Z` 已通过 SHA-256、隔离 PostgreSQL 恢复（28 张 public 表）和 29 个 MinIO 文件快照校验。
- 烟雾：远端 API `/healthz` 返回 `0.11.0`，Alembic current/head 都是 `0025_curriculum_knowledge_map`；教材分析和受鉴权原页 OpenAPI 路径存在，所有 Compose 服务健康。未上传、解析或发送真实教材。
- 本地复核：API 非集成 `189 passed, 24 deselected`、迁移表结构断言、从初始版本到 `0025` 的 Alembic 静态 SQL、Mypy（56 source files）、教材相关 Ruff lint/format、Tutor Policy synthetic eval（5 cases）、Flutter `43` 项和 Analyze、OpenAPI/JSON Schema 结构检查均通过。Web 复跑受本机缺少锁定 Node `24.18`（仅有 Node 16/20/22）阻塞，未把 Node 20 的 engine warning 结果计为通过。

## 2026-07-23 PLAN-0018 本地完成记录

- 结果：本地实现已满足“原页视觉 → 页级多模态理解 → 整本知识图谱 → 家长批准 → 错题/知识点任务 → 孩子原页”的代码验收；本机开发 PostgreSQL 已从 `0023` 前滚至 `0025` 并通过实际表结构测试。Ubuntu 未部署。
- 验证：API 非集成 188 项、教材/Provider/推荐定向 31 项、迁移表结构 1 项、Mypy 56 source files、相关 Ruff/格式通过；Web 20 项、Lint、类型、格式和 Next production build 通过；Flutter 43 项、Analyze 和格式通过；OpenAPI `0.11.0` 共 51 paths/81 refs 闭合，6 个 JSON Schema 可解析。
- 未执行：真实 118 页教材/NewAPI 多模态调用、全书知识点人工质量评分、token/费用基线、浏览器 E2E、iPad/Nova 9 原页查看与弱网回归、教材个人信息自动检测和依赖/镜像安全扫描。
- 剩余风险：真实教材可能超出模型上下文或产生章节合并偏差；当前用家长“无个人信息”声明阻断教材批注风险，自动门禁由 TODO-213 跟踪；Compose 本机缺少被忽略的 `infra/compose/.env`，本轮只更新配置未完整展开或启动。
- 回滚：停止 `curriculum-analysis-worker`，回退匹配 API/Web/App 并保留 `0025` 新表、私有原件/预览和既有审批事实；不得恢复旧文本规则抽题。

## 历史任务记录

- [x] 新增孩子绑定的即时拍题会话 API，并覆盖内存/PostgreSQL 幂等、事务和反向越权。
- [x] Flutter 自动取得会话，完成流式上传、视觉任务轮询、错误/超时兜底和人工确认；旧预签名传输仅作为历史实现事实保留。
- [x] 按 ADR-0018 将图片传输收敛为 App 携带 Session 只上传到 API，API 有界流式校验并写入内部私有 MinIO；生产 Flutter 删除预签名 URL/确认流程。
- [x] 本地 Compose 不再向宿主/LAN 暴露 `9000`，示例配置删除 `OBJECT_STORAGE_PUBLIC_ENDPOINT_URL`/`MINIO_API_PORT`；OpenAPI 不返回 `upload_url` 并合并为单一上传操作。
- [x] API/OpenAPI/Flutter 单元、格式、Lint、类型和 PostgreSQL/MinIO 集成门槛通过。
- [x] Ubuntu API/Web/worker 已部署，健康版本 `0.10.0`、迁移 `0024_intelligent_recommendations`；教材解析 worker 已稳定运行，Nova 9 既有登录验证保持有效。
- [x] 使用 synthetic 大图在 Ubuntu 完成真实 NewAPI `upload → analysis → extraction → verify → tutor`，确认有界压缩、人工确认、TutorTurn 持久化和派生对象删除。
- [x] PostgreSQL/MinIO 备份已生成并在隔离 PostgreSQL 16.10 容器恢复校验；数据生命周期 worker 已部署。
- [ ] 由 iPad 验证 `capture-session → API streaming upload → image-analysis（自动四态候选）→ 人工确认 → 状态分支提示 → 完整解答`；现有预签名直传不再作为最终发布验收。
- [x] 修复 L1/L2 题意无关问题：云端生成受约束提示，L2 基于实际 L1 递进，同时关系题固定回归且两级不泄露答案（本地代码/自动化通过，真实 Provider 待验收）。
- [x] 刚形成但尚未到期的开放错题可以从“复习错题”入口提前复习，不再显示成“没有错题”（Flutter 回归通过，真机待验收）。
- [x] 任务推荐遍历已发布 PDF 和全部开放错题，生成带具体教材题、页码、知识点、题量、预计时间和未来日期的待审批计划；批准后孩子端显示同样内容（本地代码/自动化通过，真实 PDF/Provider 待验收）。

## 2026-07-23 PLAN-0017 整改记录

- Tutor：L1/L2 改为 NewAPI 文本生成，L2 必须绑定持久化 L1；增加答案泄露、重复、结构递进和题意相关校验。针对“多人同时经历同一段时间”建立本地安全回退与固定回归，题意无关的“增加/减少/平均分”提示会被拒绝。
- 复习：Flutter 先请求到期错题；若为空则请求全部开放错题，并明确提示“可提前复习”，重新作答和 ReviewAttempt 路径保持不变。
- 推荐：API 本地遍历已发布 Snapshot 的全部 CurriculumChunk 和全部开放错题，统计薄弱知识点频次、抽取具体教材题并排序；只把最多 30 个候选及不透明来源键交给 NewAPI。计划引用未知来源、忽略已有错题/教材、未把到期错题排到当天或超过每日 3 项时整体失败。
- 下发：新增 `0024_intelligent_recommendations` 和 OpenAPI `0.10.0`；推荐/Task 保存来源类型、原始具体题、教材页码、知识点、预计时长和未来日期。Web 审核页展示同样依据，Flutter 今日任务显示当天全部任务而非第一条。
- 本地验证：API 178 项非集成测试通过；本轮 Tutor/推荐定向 30 项通过；Mypy、相关 Ruff、OpenAPI/JSON Schema、Alembic offline SQL、5-case Tutor eval 通过；Web 16 项测试、Lint、类型、格式和 production build 通过；Flutter 全量 40 项测试与 analyze 通过。
- 已执行：使用 `rsync` 同步最新工作区，排除 `.env`、`.git` 和本地缓存；Ubuntu Compose 以 `DOCKER_BUILDKIT=0` 重建，保留 PostgreSQL/MinIO/Redis 数据卷；API/Web `/healthz` 通过，API 返回 `0.10.0`，Alembic current/head 均为 `0024_intelligent_recommendations`，API/Web/四个 worker 重启次数均为 0。
- 未执行：真实 NewAPI L1/L2/推荐、真实已上传 PDF 选章/抽题、iPad 立即复习与多任务页面、浏览器 E2E，以及 planner 的 token/延迟/成本完整审计。回滚需保持 API/Web/App/迁移成对；`0024` 新列不删除既有任务/推荐事实。

## 2026-07-23 本轮实现记录

- [x] M1：新增 `/mistake-closeout`，PostgreSQL 事务内校验活动 StudySession、已确认 VerifiedQuestion 和 `worked/blank` AttemptEvidence，完成会话并幂等创建 MistakeRecord/ReviewSchedule。
- [x] M2：复习接口返回实际题目；Flutter 提交作答文本与确认标记；服务端写入 ReviewAttempt，并按 `review-policy.v2` 与 1/3/7/14/30 天间隔确定结果，客户端不再直接决定掌握状态。
- [x] M3：教材上传合同收缩为 PDF-only；新增 `0021`～`0023`、pdfplumber 解析 worker、扫描 PDF `needs_ocr`、危险/加密文件隔离、页级 CurriculumChunk 和已发布 Snapshot 来源检索。
- [x] M4：TutorTurn 保存教材来源、L1/L2 目标、递进来源、孩子动作和答案暴露级别；Flutter 展示下一步可执行动作。
- [x] 自动验证：API 全量测试在本机 PostgreSQL/MinIO 前滚到 0023 后通过；Ruff/Mypy/compileall、PDF parser synthetic、Flutter analyze/test、Web test/lint/typecheck/format/build 通过。
- [x] 远端/设备验证：使用 rsync 同步并在 Ubuntu 重建 Compose，迁移头为 `0024_intelligent_recommendations`，API/Web 健康检查通过，ImageAnalysis/DataLifecycle/MaterialParse worker 修复后稳定运行；iPad mini 6 已安装 Xcode 自动签名调试包并成功启动。
- [ ] 未执行：真实 PDF/扫描 PDF 上传、iPad/Nova 9 相机闭环、浏览器 E2E、固定 Tutor/教材 eval、四设备弱网/权限回归、SBOM/镜像扫描。Ubuntu 已完成前滚与重建；剩余风险与回滚见 `RUNBOOK.md` 和 ADR-0021。

## 兼容、回滚与风险

## 2026-07-23 教材解析与客户端收口修复

- [x] 将教材单文件上限统一为 `50 MiB`（`52,428,800` 字节），修复原先后端/解析器使用十进制 `50,000,000` 字节而使 47.8 MiB 文件被 `413` 拒绝的问题；Web 在选择与失败响应中均显示同一精确上限。
- [x] 修复教材解析 worker 错用仅允许 `captures/`、最多 8 MB 的对象读取接口；worker 现仅能以受限 `curriculum/` 前缀和同一 50 MiB 上限读取私有 PDF，解析页块可进入审核发布和具体题推荐。
- [x] 家长工作台增加教材删除：删除一个快照时级联移除其私有 PDF、解析任务/页块和失效推荐引用；删除请求有会话、CSRF、家庭/孩子授权和幂等保护。旧“已发布但未解析正文”的范围会明确标记，需删除并重新上传实际 PDF 才能用于具体题推荐。
- [x] 孩子端完整解答出现后将第二操作改为“返回首页”，不再继续显示“查看完整解答”。
- [x] 回归与部署：教材 API/私有对象读取/PDF parser `27` 项、API 全量 `181` 项/Mypy、Web `17` 项/Lint/类型/格式/production build、Flutter 全量 `41` 项与 analyze 通过；已安全 rsync 到 Ubuntu 并重建。API/Web/三类 worker/数据服务均 healthy，运行容器确认 `curriculum_limit=52428800`、`read_document=True` 和删除 OpenAPI 路径存在；真实家庭 PDF 上传/解析/发布/推荐仍待用户现场验收。

## 2026-07-23 家长教材阅读与推荐详情

- [x] 教材快照列表不再直接渲染页级全文；新增仅限家长、同家庭/孩子授权的分页解析阅读接口，返回页码、标题、正文和置信度，不返回原始 PDF、对象键或 MinIO URL。
- [x] Web 教材审核改为摘要卡片后显式打开分页阅读器；长文本按段落排版、可切换页码，草稿和已发布快照均可在发布前后审阅。
- [x] 推荐列表改为摘要，点击“查看计划”才展示每道题、教材页码/错题来源、推荐理由及批准/忽略操作，避免在工作台堆叠完整题干。
- [x] PDF 解析器仅过滤 `pdfminer.pdfinterp` 已知的灰度图形操作数兼容警告（`/P0` 等），保留其他警告与所有真实解析失败状态，避免 worker 日志被无关噪声淹没。
- [x] 本地验证：API 定向 14 项与完整非集成 183 项、Mypy/Ruff；Web 18 项测试、Lint、类型、格式和 production build；OpenAPI YAML 解析与差异空白检查通过。
- [ ] 未执行：本批可读性改动尚未部署 Ubuntu，真实家庭 PDF 的阅读版式和浏览器 E2E 待部署后现场验收。

- Ubuntu API/Web/worker 已切换到 ADR-0018 的单一流式合同；已部署 Flutter 仍需在设备可用时重新验收。正式 OpenAPI 不再暴露预签名入口，旧实现仅保留为代码级受控回滚材料。
- 回滚应用/API 不删除已创建任务、会话、Capture 或确认题目；新链路异常时只允许整体回滚匹配的 API/App，并在隔离受信 LAN 临时恢复旧 `9000`/配置，不得公开 Bucket 或下发密钥。
- ImageAnalysis 仍依赖用户确认后的脱敏副本和单一 NewAPI Provider；超时/失败允许手工填写，不把未确认提取作为 Tutor 事实。

## 本轮全仓收口记录

- `2026-07-23`：项目 Owner 将教材首版范围进一步收窄为“只支持 PDF 上传，DOCX/PPT 暂不支持”。PLAN-0016/ADR-0021 现要求 Web/OpenAPI/API 同步收缩 allowlist，Word/PPT/Excel 返回稳定不支持错误；文本 PDF 进入隔离解析，扫描 PDF 进入待 OCR。既有非 PDF 对象只保留用于兼容/删除，不解析、不发布、不进入 Tutor/推荐。本轮仍仅修改规划文档，当前运行时代码尚未执行合同收缩。

- `2026-07-23`：项目 Owner 指出三项尚不可用能力：拍题记录未进入真实复习、上传教材未解析并用于讲解/推荐、Tutor 第 1/2 级提示过浅。代码审计确认：Flutter 完成拍题会话时未创建 MistakeRecord，复习页只提交客户端“会了/不会”而没有 Question/ReviewAttempt；教材路由只写入 MinIO 和占位草稿；多数 L1/L2 模板没有稳定递进语义。已建立 PLAN-0016、TODO-020 和 Proposed ADR-0021，明确原子错题 closeout、证据化复习、隔离教材解析/审核发布、两类教材消费和 Tutor Hint 新版本；教材格式随后由上一条记录进一步收窄为 PDF-only。本轮仅完成规划，没有修改运行时代码。

- `2026-07-20`：OpenAPI/API 前滚为 `0.9.0`，新增 `0020_answer_evidence`。视觉提取现在必须返回四态候选、置信度和可见作答步骤；确认后写入 VerifiedQuestion，Tutor 不再信任客户端临时状态。`worked/blank` 在第三级通过已配置 NewAPI 仅传已确认文字生成完整步骤、答案和验算并持久化；`unclear/answer_area_missing` 明确要求确认或补拍。Flutter 去除硬编码 `2/4` 和练习页二次手选，家长 Web 增加 Household-scoped 逐题详情。Ubuntu 已在备份后 rsync、重建并健康前滚到 `0020`；合成题现场返回正确 3 步、答案 17 只和验算。iPad 已安装 profile App 并完成账号/档案/任务 200 启动 smoke，实际相机闭环仍待人工操作。

- `0013_tutor_turn_persistence`～`0015_child_data_export` 已部署：Tutor 只读取服务端 VerifiedQuestion，TutorTurn 追加写；会话完成/复习和周报可追溯；导出为 24 小时不可变 JSON 快照并随孩子删除级联。
- Flutter 使用真实任务与活动会话，确认题目后进入真实 Tutor；离线 Attempt 队列使用 SQLite 并按服务端/账号隔离。同一天重复拍题使用新的流程幂等 nonce，避免复用已完成会话。
- 家长 Web 可创建当天数学任务、查看周报摘要、下载孩子数据导出；API 删除孩子档案会按依赖顺序清理学习、Capture/OCR、视觉、VerifiedQuestion、Tutor 和导出数据。
- 自动验证：API 162 项非集成测试、Ruff/Mypy；Web 14 项测试/类型/Lint/生产构建；Flutter 39 项测试/analyze、Android release APK 和 iOS release 无签名构建（以 `TESTING.md` 最新记录为准）。
- 未执行：用户当前不在实体设备旁，Nova 9/iPad 的最终相机、权限拒绝/允许、弱网、横竖屏和重启人工回归保留。自动视觉检测器仍未实现，当前外发门禁依赖规则信号、手动涂抹和用户确认，不得宣传为绝对匿名。
- `2026-07-17` 架构变更：项目 Owner 接受 ADR-0018，要求 App 不再直连 MinIO；随后完成 API/Flutter/契约/Compose 迁移，关闭 Compose 的 MinIO `9000` 宿主入口。
- `2026-07-18` PLAN-0012 远端收口：Ubuntu API/Web/两个 worker 已重建并运行，迁移到 `0016_child_account_uniqueness`；旧 `.env` 中残留的公开 MinIO 地址已清除，worker 使用 `http://minio:9000` 内部地址。synthetic 请求已到达 NewAPI，但 Provider 返回 HTTP `402`，属于额度/余额配置问题，不是上传链路失败。
- `2026-07-18` 并行规划说明：项目 Owner 要求 Web 将孩子档案/账号合并为一个创建与管理体验，并支持首页当前孩子选择；PLAN-0013 已完成 API/Web 首版、唯一约束迁移和 Ubuntu 部署，浏览器 E2E 与双孩子实体验收仍待执行。
- `2026-07-18` 产品主线规划：项目 Owner 批准“教材范围 → 错题讲解 → 错题沉淀 → 到期复习 → 今日任务”方向及详细建议，已建立 Accepted ADR-0020、PLAN-0014 和 TODO-016～019。随后先实现错题/复习最小闭环：`MistakeRecord`/`ReviewSchedule`、`0017`、到期查询、确定性复习、导出覆盖和 Web/Flutter 调用，并部署 Ubuntu；教材、作答四态和三入口仍待后续阶段。
- `2026-07-18` 错题讲解规划补充：Owner 确认拍题会包含孩子解答，答题区确认空白表示“没有思路”并允许从头讲解。ADR-0020/PLAN-0014 已改为四态作答 Schema：`worked/blank/unclear/answer_area_missing`；空白必须用户确认，未拍入/不清不得自动当空白。当前 `MistakeRecord` 只接受服务端已确认 `VerifiedQuestion` 与会话引用，未伪造四态作答证据。
- `2026-07-18` PLAN-0012 实现与部署：新增 Session 鉴权的单一 API 原始流上传，服务端用 boto3 S3 multipart 有界写入私有 MinIO，增量校验大小/SHA-256，完成后重新读取并完整解码图片，失败清理 multipart/对象；API/Flutter/契约/Compose 相关回归通过，Ubuntu 已成对部署。未完成：Nova 9/iPad 新链路人工验收、并发/断连现场压测和 Provider 额度恢复后的真实识别。
- `2026-07-18` PLAN-0014 最小闭环：新增错题创建/列表/到期过滤/复习提交 API，使用 `0017_mistake_review` 和 PostgreSQL 事实源，连续三次正确关闭错题，非正确结果按确定性策略回退；导出包含错题/复习计划，Web 显示到期错题，Flutter 客户端可读取并提交复习结果。API 159 项非集成、Web 11 项、Flutter 29 项回归通过，Ubuntu 已前滚到 `0017`。
- `2026-07-18` PLAN-0014 纵向实现：新增 `0018_curriculum_answer_recommendations`，教材授权 manifest 导入/草稿/家长发布快照、Attempt 四态与 Tutor 分支、Flutter 数学三入口、任务推荐审批及批准后 Task 创建；新增 API/Web/Flutter 回归。真实 PDF 二进制解析、Provider 识别额度恢复后的联调、浏览器 E2E 和设备回归保留为最后验收。
- `2026-07-18` Ubuntu 部署收口：使用 rsync 同步 API/Web/迁移/契约/Compose，修正 Alembic revision 长度后将远端 PostgreSQL 前滚到 `0018_curriculum_recommendations`；API、Web、两个 worker、PostgreSQL、MinIO、Redis 均 healthy，OpenAPI 已暴露教材/推荐新路径，远端 `.env` 未覆盖。
- `2026-07-18` 教材上传增量：新增 `0019_curriculum_documents`、`python-multipart` 和多文档 multipart API；Web 支持多选 PDF/DOC/DOCX/PPT/PPTX/XLS/XLSX，逐文件流式写入私有 MinIO 并生成 `uploaded` 草稿。Ubuntu 已备份后前滚、重建并验证健康和 OpenAPI 路径；真实文档解析仍待完成。
- `2026-07-20` 教材上传修复：浏览器在非安全上下文中不提供 `crypto.randomUUID()`，导致选择教材后点击上传立即抛出 TypeError；已改用 `crypto.getRandomValues` 并保留无 Web Crypto 时的随机回退，Web 12 项测试通过，Ubuntu Web 已重建并健康。
- `2026-07-20` 教材上传 CSRF 修复：教材页面写请求补齐登录 Cookie 对应的 `X-CSRF-Token`，覆盖手工导入、文档上传、发布和任务推荐；新增 CSRF Cookie/header 回归，Web 14 项测试通过，待 Ubuntu Web 重建后复测上传。
- `2026-07-20` iPhone 11 真机调试：Xcode 26.6/CoreDevice 识别 iOS 17.5.1 设备，开发者模式和 DDI 服务已启用；Flutter Debug App 已安装启动。真机发现登录卡片在紧凑窗口发生 58px 底部溢出，已改为可滚动布局，新增回归后 Flutter 30 项测试通过并热重载验证。
- `2026-07-20` iPhone 局域网连接修复：确认 Mac 可访问 Ubuntu `3000/8000` 且 API 健康，但 iPhone 请求未到达服务端；定位到 Runner 缺少 `NSLocalNetworkUsageDescription` 与 iOS 17 局域网 IP 的 ATS 声明。已加入用途说明及 `NSAllowsLocalNetworking`，校验编译产物并重新安装真机；等待用户允许系统本地网络权限后复测登录。
- `2026-07-20` iPhone 局域网诊断：经用户授权卸载 `com.example.studyChild` 清除本地权限/会话状态后重新安装，并在登录页增加 `/healthz` 检测、手动重试和不含凭据的安全网络错误信息；Flutter 真机返回 `errno 65: No route to host`，Ubuntu API 没有收到请求。iPhone Safari 对 Ubuntu `192.168.1.4:8000` 以及同 Wi-Fi 网段 Mac `192.168.100.158:18080` 的请求也均未到达，当前阻塞定位为 iPhone 本地网络权限状态、VPN/过滤器或 Wi-Fi 客户端隔离，不是 Flutter HTTP、账号或 API 故障。临时 HTTP 端口和 RVI 诊断接口已关闭。
- `2026-07-20` iPad mini 6 真机回归：Flutter 识别 `00008110-0011356E0E41801E`，完成构建、安装、启动和热重启；启动期间 API 收到来自局域网 `192.168.1.100` 的 `/healthz` 并返回 200，证明同一客户端版本在 iPad 网络链路可用。登录、相机/相册权限及拍题人工确认仍待设备端点击验收。
- `2026-07-20` 拍题失败恢复优化：识别失败页保留已确认脱敏照片，新增“重新识别当前照片”和“重新拍题”；重新识别使用新的幂等键创建新 OCR/ImageAnalysis 任务，不复用失败任务；同时修复从拍题返回学习桌时把异步刷新误放入 `setState` 的 iPad 真机运行时错误。Flutter 33 项测试/analyze 通过，已热重启到 iPad。
- `2026-07-20` 拍题体验优化：脱敏完成后立即进入独立上传进度页，上传期间保持题目照片和转圈状态，不再回到拍题页；成功后自动进入题目确认，失败可在原页重新上传或返回拍题。确认题目改为大尺寸多行编辑框，可在框内上下拖动查看长文本。新增 3 项 Flutter Widget 与安全会话存储回归，Flutter 共 37 项通过。
- `2026-07-20` 孩子端账号体验优化：登录后隐藏服务端切换入口，学习桌顶部增加账号入口；账号页支持安全保存的会话切换、添加账号和注销当前账号，不保存密码，服务端地址仍只在登录流程中配置。已在 iPad 热重启验证启动无运行时异常。
- `2026-07-20` 修复确认题目点击后可能一直卡住：Capture HTTP 请求增加 8 秒连接与 20 秒响应上限，确认流程补齐非业务异常兜底并恢复按钮状态，按钮在请求期间显示“正在确认题目……”。Flutter 37 项测试/analyze 继续通过。
- `2026-07-20` 根因修复：Flutter `HttpClientRequest.write()` 默认 Latin-1，中文题目序列化时抛出非法字符异常；Capture、登录和改密 JSON 请求统一改为 UTF-8 字节写入，并用中文题目回归验证确认请求。
- `2026-07-20` 修复同一照片重试失败：首次 ImageAnalysis 失败后服务端会清理派生对象，重试不再复用原 Capture 上传幂等键，而是使用新的上传键创建新 Capture/对象/识别任务；错误提示不再把 Provider/配置失败误报为照片不清晰。Ubuntu 数据库确认原问题为旧重试任务的 `image_analysis_failed`，首个任务为 `provider_http_402`。
- `2026-07-20` 修复脱敏后进入上传页提示照片大小不合规：相机 JPEG 经不可逆 PNG 重编码后可能膨胀超过 API 的 8 MB 上限；PrivacySanitizer 现在按 1800/1500/1200/960/720 像素上限逐级等比缩放、同步换算遮挡区域并重新编码，上传副本控制在 7.5 MB 内，仍超限时要求用户只裁剪题目区域。Flutter 38 项测试/analyze 通过。
- `2026-07-20` 修复真机练习页身份和提示链路：标题改用当前安全会话对应的登录用户名，不再使用原型默认“小禾”；真实题目进入练习页自动请求第一级 Tutor 提示，零成本本地策略按“减少/剩余、比较、平均分组、求总量、分数”等已确认题目结构生成分级提示。视觉确认形成的 `VerifiedQuestion` 可在 Capture `needs_correction` 状态进入 Tutor，不再被旧 OCR `corrected` 门禁误拒绝为 409；Flutter 使用提示专属错误信息。API 162 项、Flutter 39 项及静态检查通过，Ubuntu API 已重建健康，iPad 已热重启。
- `2026-07-22` 家长 Web 按已选“方案 1”完成后台化重构：统一固定分组导航、当前孩子上下文、今日优先事项、本周趋势、可展开逐题详情、孩子/账号聚合管理和教材/推荐工作区；统计继续读取 Household-scoped API，没有写入演示数据或认证旁路。新增 Phosphor Icons `2.1.10` 与 Recharts `3.10.0`（MIT、精确锁定），14 项 Web 单测、Lint、类型和 Next 生产构建通过；使用独立合成 API 在真实登录流程中完成 1280 桌面与 736 窄屏视觉/交互 QA，结果记录于 `design-qa.md`。Web 已通过 rsync 同步 Ubuntu、使用锁定 Node 24.18/pnpm 11.7 重建并健康启动；Nova 9 安装因本轮 ADB 本机访问授权被拒绝未执行，release APK 已就绪。
- `2026-07-23` 修正家长后台信息架构：孩子切换移到所有页面共用的顶栏，下拉选择通过 `?child=` 保持工作台、教材和孩子管理作用域；侧栏删除与工作台卡片重复的今日任务、待复习、最近学习和学习周报，只保留三个顶层目的地。教材链路审计确认已发布小节仅用于生成带 `snapshot_id`、小节标题和学习目标的家长审批任务推荐，Tutor 尚未消费教材正文；上传 PDF/Word/PPT/Excel 仍只是私有存储和待解析草稿。为避免误用，待解析文档现在不能发布，Web 明确显示“待解析 · 尚未使用”。Web 16 项测试、Lint、类型、格式和生产构建及 API 教材定向 5 项测试通过；同尺寸参考图/实现图浏览器对照记录于 `design-qa.md`。相关 Web/API/worker 已 rsync 到 Ubuntu 并重建，API `0.9.0`、Web 和两个 worker 运行正常，API/Web healthcheck 均通过。

---

# 历史任务：TASK-0008 孩子档案 PostgreSQL 持久化

## 当前任务元数据

- 状态：`COMPLETE（代码、迁移与 Ubuntu 持久化验收完成；华为登录生命周期继续由 PLAN-0008 跟踪）`
- 类型：`FEATURE / DATA MIGRATION`
- 优先级：`P0`
- Owner：Codex（执行）；项目 Owner（用户，明确要求生产标准持久化）
- 创建/更新：`2026-07-17`
- 关联：`PLAN-0009`、`ADR-0005`、`ADR-0009`、`ADR-0017`

## 当前目标与验收

将孩子档案和设备登记从进程内 synthetic 仓储切换到 PostgreSQL 业务事实源，保持现有 OpenAPI 字段与 Household/角色授权不变。新增/编辑/删除必须事务化且支持幂等重放；孩子账号与档案的 Household 绑定由数据库约束保护；Compose 重启后档案仍存在。

- [x] 新增可前滚的 Profile/Device 数据库迁移，并兼容现有账号绑定和旧合成默认档案。
- [x] 新增 PostgreSQL ProfileRepository，覆盖读取、新增、编辑、删除、设备登记、审计、并发与幂等冲突。
- [x] Compose 默认启用 PostgreSQL ProfileRepository；内存仓储只保留给 unit/local synthetic 测试。
- [x] API 单元/集成、迁移往返、OpenAPI/Web/Flutter 兼容检查通过。
- [x] Ubuntu 应用迁移并重启后验证档案持久化；不输出凭据或真实儿童数据。

## 兼容、迁移与回滚

- OpenAPI 请求/响应保持兼容，不要求 Web 或 Flutter 修改字段。
- 迁移优先前向修复；部署前记录 Alembic 版本和表计数。不得为回滚删除现有档案、账号、学习记录或图片。
- 旧内存档案无法从进程外可靠读取；迁移使用既有确定性默认档案及已持久化孩子账号绑定生成兼容行，部署后以 PostgreSQL 为唯一事实源。

## 完成记录

- `0012_profile_persistence` 建立 `child_profiles`/`devices`、Household 查询索引、字段约束，以及 `accounts(child_id, household_id)` 到档案的级联复合外键；旧确定性档案和已持久化孩子账号绑定被前向兼容。
- PostgreSQL 仓储使用事务、通用幂等表和稳定审计事件实现档案/设备 CRUD；并发同键创建只产生一个资源，跨 Household 返回不可枚举结果，删除档案级联孩子账号和会话。
- 本机 127 项 API 单元、21 项 PostgreSQL/MinIO 集成、`0012 → 0011 → 0012` 往返、Ruff、Mypy 40 源文件、OpenAPI、Web 6 项测试/类型/构建、Flutter analyze/17 项测试通过。
- Ubuntu 部署前生成权限 600 的 PostgreSQL 压缩备份；远端从 `0011` 前滚 `0012`，API/PostgreSQL/Web healthy，孤儿孩子账号绑定为 0。临时 synthetic 档案经 API 重启后可重新读取，随后档案、幂等和审计测试记录已清理，正式档案计数恢复为 1。
- 修复 PostgreSQL 重复孩子用户名触发未处理 `IntegrityError` 的缺陷：只识别账号 Household/用户名唯一约束并转换为领域冲突，API 返回 409，Web 提供可操作提示；本机 128 项非集成、22 项集成、Web 7 项测试及生产构建通过。Ubuntu API/Web 重建后，对现有用户名的只回滚 smoke 返回 `duplicate_conflict=ok`，所有基础容器保持运行且健康，未修改现有账号。
- 修复 Flutter 把首次改密门禁误显示为“API 尚未连接”的缺陷：登录响应和 `/auth/me` 会话恢复均识别 `must_change_password`，新增孩子首次改密、Token 轮换和安全存储 UI；API 将孩子档案列表/详情限制到账号绑定档案。本机 API 129 项非集成/22 项集成、Flutter analyze/21 项测试及 176 MB Debug APK 通过；Ubuntu API 已重建并健康，Nova 9 实机完成改密与档案读取，显示“小汤圆”学习桌和“在线”。手机竖屏标题溢出亦已修复并覆盖安装验证。
- 华为 Nova 9 已重新由 ADB 稳定识别，App 冷启动到登录页，服务端地址正确且手机可达 API，日志无 Flutter 崩溃；真实密码登录和档案读取需用户在设备输入凭据，继续由 `PLAN-0008` 跟踪。

---

# 历史任务：TASK-0007 认证面收敛与 Flutter 服务端地址配置

## 任务元数据

- 状态：`COMPLETE（代码与本地质量门槛完成；远端部署和真实设备验收保留在 PLAN-0008）`
- 类型：`FEATURE / SECURITY`
- 优先级：`P0`
- Owner：Codex（执行）；项目 Owner（用户，明确要求）
- 创建/更新：`2026-07-16`
- 关联：`PLAN-0008` 阶段 5a、`ADR-0017`、`TODO-012`

## 1. 目标与范围

运行时只保留家长/孩子“用户名+密码”登录，登录成功后分别使用 Web HttpOnly Cookie 或 Flutter Bearer Session 承载同一类可撤销会话。删除 HMAC Token、Demo Header、Web 认证旁路、签发脚本和对应契约/测试/配置。

Flutter 登录界面在用户提交账号密码前提供服务端基础地址编辑和持久化；仅允许无用户信息、查询和片段的 HTTP(S) 地址。服务端地址变更必须清除本地旧会话，防止将旧 Token 发往新服务端。

## 2. 验收标准

- [x] API 不再读取 `STUDY_AUTH_MODE`/`STUDY_AUTH_SECRET`，不接受 HMAC 或 `X-Demo-*` Header，运行时只认可密码登录产生的未撤销会话。
- [x] OpenAPI 业务端点只声明 `SessionCookie`/`BearerSession`，Web 无免登录开关或 Demo Header 回退，Compose 无旧认证配置。
- [x] Flutter 登录前可编辑并保存服务端地址；登录、孩子资料和 Capture 共用该地址，地址变更不复用旧会话。
- [x] API/OpenAPI/Web/Flutter 相关单测、格式、Lint/类型和构建门槛通过；无密钥、真实数据或意外生成物。
- [x] 同步 ADR、架构、安全、测试、运行手册和变更记录，记录该破坏性契约收敛的升级与回滚方案。

## 3. 兼容、回滚与风险

- 这是用户明确批准的破坏性安全收敛；旧 HMAC/Demo 客户端必须升级，不保留运行时兼容开关。
- 已签发的 HMAC Token 在升级后立即失效；现有密码账号和会话表不迁移、不删除。
- 回滚只能回滚到上一应用版本，不保证旧 HMAC/Demo 路径安全；若必须临时回退，需项目 Owner 再次明确批准并限制在隔离环境。
- 自托管 LAN 可使用 HTTP 调试；公网或生产必须由反向代理提供 HTTPS。

## 4. 完成记录

- 删除 API HMAC/Demo 认证器、旧 Token 签发脚本、环境开关和对应契约；业务测试改用真实账号密码创建的可撤销会话，并覆盖旧凭据被拒绝。
- Web 删除 Demo Profile、静态 Token 和免登录回退，工作台、账号管理和首次改密路由统一由 Session Cookie 保护。
- Flutter 新增登录前服务端根地址校验与安全持久化；登录、孩子档案和 Capture 统一读取该地址，更换地址先删除旧会话。
- 验证：API Ruff/Mypy、122 项非集成和 18 项 PostgreSQL/MinIO 集成通过；OpenAPI/JSON Schema 和认证 Scheme 检查通过；Web 格式/Lint/类型/2 项单测/生产构建通过；Flutter 格式/分析/17 项测试通过；Compose 本机配置解析通过；`git diff --check` 通过。
- 未执行：未重新部署远端 Ubuntu，未运行浏览器 E2E、实体 iPad 登录/退出/重启生命周期和备份恢复。Web 本地验证使用 Node 20/pnpm 9，虽全部通过但产生 engine warning；锁定容器仍使用 Node 24.18/pnpm 11.7。
- 回滚：优先前向修复；如必须回退应用版本，保留 `Account`/`AuthSession`/审计数据，不恢复已撤销会话。重新启用 HMAC/Demo 需项目 Owner 另行批准并限制在隔离环境。

---

# 历史任务：TASK-0006 Capture 与人工校正安全基础

## 任务元数据

- 状态：`COMPLETE（代码闭环；真实 Provider/设备/备份验证作为环境验收项保留）`
- 类型：`FEATURE`
- 优先级：`P1`
- Owner：Codex（执行）；项目 Owner（用户，明确要求继续 TODO-008）
- 创建/更新：`2026-07-15`
- 基线分支/提交：`master`；最近提交 `c3a107e`；工作区含本轮 OCR 入队/调度增量
- 关联：`TODO-008`、`PLAN-0006`、`ADR-0001`、`ADR-0002`、`ADR-0004`、`ADR-0005`、`ADR-0006`、`ADR-0009`、`ADR-0010`、`ADR-0011`、`ADR-0012（已被替代）`、`ADR-0013`、`ADR-0014`、`ADR-0015`、`ADR-0016`；后续认证任务 `TODO-012`、`PLAN-0007`、`ADR-0017`

## 1. 目标与范围

实现 Capture 与低置信度人工校正的安全基础：孩子只能在自己的 Household/StudySession 内登记一份图片采集元数据，服务端不把未验证 OCR 结果当作事实；在没有获准 OCR Provider 时，Capture 必须进入人工校正状态，校正记录以追加写保存。

本任务包含：Capture OpenAPI 增量、API 领域/仓储/迁移、Household/child 授权、版本冲突与幂等、合成 PostgreSQL 集成测试，以及必要的架构/安全/运行记录。

本任务不包含：商业化、多地区、第三方 IdP、复杂监护人流程或外部商业 Provider。按 ADR-0010～0016，本地 synthetic 环境已实现相机/相册选择、MinIO 私有上传、服务端确认（含对象实际 SHA-256 核验）、旧 OCR 入队/Job 状态轮询/候选人工确认、Provider-neutral Schema、PrivacySanitizer 核心/规则信号、Flutter 本地脱敏预览确认、ImageAnalysis queued/blocked API、Bearer 认证、NewAPI Adapter、0009 提取结果持久化、可恢复 worker、人工确认生成 VerifiedQuestion 和无 Provider offline Tutor Policy 降级提示；不把真实原图发出，也不把未确认提取伪装成业务事实。S3/OCR 运行时和模型版本已锁定，真实视觉检测器、实际 NewAPI 联调和备份恢复仍属于环境验收项。local/CI 已提供合成孩子档案删除入口、OCR 输入规范化边界、候选结果持久化和 Tutor synthetic eval 边界。

`2026-07-15` 架构调整：项目 Owner 接受 ADR-0015，目标路线改为本地 `PrivacySanitizer` 只用 OCR/规则/轻量视觉检测敏感区域，用户确认不可逆脱敏副本后由单一获批云端视觉 Provider 解析照片。现有 text/formula OCR Job/结果链路是已实现的旧路线和可关闭回滚能力，不再是目标默认解析器。本轮先实现不依赖云 Provider 的脱敏核心、Provider-neutral Schema 和 synthetic eval，不接入云 Provider 或真实图片。

随后项目 Owner 接受 ADR-0016 并明确本产品按自用、自托管 NewAPI 推进；因此当前实现增加了自用 Bearer、显式 NewAPI 开关和 queued worker，但实际 Provider 联调与人工确认仍单独保留为未完成项。

项目 Owner 随后批准用家长/孩子账号密码和可撤销会话替换 HMAC Bearer。该变更已记录为 ADR-0017、PLAN-0007 和 TODO-012；本任务完成后已自动进入 PLAN-0007，认证代码、OpenAPI、数据库和 Compose 切换不再属于本 Capture 任务。

## 2. 已知冲突与实施假设

- `ASSUMPTION-01`：直接登记的 Capture 以 `needs_correction` 状态创建；预签名上传 Capture 先处于 `upload_pending`，服务端确认私有对象的声明 MIME/大小和实际 SHA-256 后才转为 `needs_correction`。不调用外部服务，也不产生伪造 OCR 内容。
- `ASSUMPTION-02`：本阶段的业务请求仅接收受限媒体声明（类型、大小、不可逆内容哈希），不接收原始图片、对象键或完整题目文本；短期签名 URL 仅出现在上传响应中，永不进入数据库业务模型、审计、错误响应或日志。人工校正内容只进入业务库，永不写入审计事件或错误响应。
- `ASSUMPTION-03`：校正是追加事件；Capture 的派生状态以服务端 `version` 明确合并，不能用最后写入覆盖已有校正。
- `ASSUMPTION-04`：local MinIO 预签名 PUT URL 默认有效期为 300 秒，并通过环境变量配置；生产值须在 staging 前复核。OCR Adapter 只接受预置模型目录，禁止运行时自动下载模型。
- `ASSUMPTION-05`：自用 NewAPI 只通过 `STUDY_NEWAPI_ENABLED=true` 显式开启；queued job 仅在本地配置通过、脱敏副本用户确认且 SHA-256 与 Capture 一致时产生。worker 失败只写稳定错误码，QuestionExtraction 必须保持 `needs_confirmation=true`，不得直接进入 Tutor。

## 3. 验收标准

- [x] OpenAPI 定义 Capture、人工校正、版本化请求/响应、错误与兼容策略；不引入手工漂移的跨端公共模型。
- [x] 仅绑定孩子可为自己的 Session 创建、读取、校正 Capture；跨 Household、同家庭其他孩子、无绑定主体和枚举 ID 均被拒绝。
- [x] Capture 初始必须要求校正；校正追加写、幂等重放和版本冲突可验证，审计中无原始题目或校正文本。
- [x] PostgreSQL 迁移和仓储在同一事务处理 Capture、校正、幂等记录与审计；验证迁移回滚/前滚、重复请求和并发校正。
- [x] 已记录真实媒体、OCR Provider、设备权限/离线 SQLite 与生产生命周期仍未实现的原因、回滚方式和下一步。
- [x] 已以 ADR-0015/0016 记录本地脱敏/自托管视觉职责、原图不外发、单 Provider、识别/Tutor 分离、临时副本删除、旧 OCR 兼容迁移与回滚；当前已实现 Adapter、queued worker、未确认提取落库、人工确认生成 VerifiedQuestion 和成功/失败清理分支。真实视觉检测器、NewAPI 实例联调、iPad 回归和备份生命周期演练仍未执行。

## 4. 验证与回滚

- 计划验证：OpenAPI 结构检查、API Ruff/Mypy/单元与 local PostgreSQL 集成测试、Alembic downgrade/upgrade；不运行真实 Provider 或真实图片。
- 回滚：合同仅新增；优先关闭 Capture 路由或前向修复迁移。不得删除 CaptureCorrection/AuditEvent、不得把校正文本写进日志、不得清空客户端队列。

## 5. 当前进度

- `2026-07-13`：项目 Owner 明确授权执行 `TODO-008`；已复核 PRD、架构、安全、测试、ADR 和现有 Learning 持久化边界，建立本任务与计划。
- `2026-07-13`：OpenAPI `0.4.0` 已增加 Capture 元数据、人工校正和显式版本冲突合同。Capture 创建只接收 MIME、大小和 SHA-256 声明，且始终进入 `needs_correction`；不接收原始媒体或调用 OCR Provider。
- `2026-07-13`：API 已实现 child-only Capture 创建/查询和追加校正；`0002_capture_manual_correction` 在 PostgreSQL 中保存 Capture/Correction、幂等记录和无原文审计事件。19 项 API 测试及 migration downgrade/upgrade 演练通过。
- `2026-07-13`：项目 Owner 已接受 ADR-0010（本地 MinIO/私有 Bucket/预签名上传）、ADR-0011（24 小时/7 天/30 天保留、家长控制、级联删除）与 ADR-0012（本地 PaddleOCR、人工确认、外部默认 0 元）。
- `2026-07-13`：项目 Owner 已锁定 `boto3==1.43.46`、`paddleocr[doc-parser]==3.7.0`、`paddlepaddle==3.3.1`、CPU/`paddle_static` 与普通/方向/公式模型清单；macOS Docker 的 linux/amd64 synthetic 真实模型烟测已通过，Ubuntu 24.04 x86_64 原生性能基准和真实题型评测仍未执行。
- `2026-07-13`：依赖已写入 `pyproject.toml`/`uv.lock` 并在本机 API 虚拟环境安装；本地 MinIO healthy。`S3ObjectStorage` 仅签发 300 秒、JPEG/PNG、最多 8 MB、`captures/` 前缀的 PUT URL；集成测试以随机 synthetic JPEG 上传后立即删除。
- `2026-07-13`：`LocalPaddleOcrAdapter` 已要求五个锁定模型目录全部预置后才构建 CPU 引擎，绝不在运行时自动下载；假工厂测试验证普通/方向/公式模型参数。
- `2026-07-13`：临时 uv 可执行路径在本轮清理后不可发现；已使用项目 `.venv` 完成等效静态/测试验证，标准 uv 恢复已记录为范围外 `TODO-011`。
- `2026-07-13`：OpenAPI `0.5.0` 新增私有上传签发与确认端点；`0003_capture_object_upload_state` 仅在 PostgreSQL 内保存不含身份的对象键。确认端会先读取 MinIO 对象 MIME/大小，再把 `upload_pending` 转为 `needs_correction`；跨 Household/同家庭兄弟孩子均返回 404，确认和签发均可幂等重放。
- `2026-07-14`：已应用本地 `0003`～`0006` 迁移，并使用 `.venv` 执行 Ruff、Mypy、60 项单元与 14 项 PostgreSQL/MinIO 集成测试（合计 74 项）；新增有界对象读取、SHA-256、JPEG/PNG 容器头和尺寸/像素数/EXIF 边界测试。端到端测试只上传后立即删除 synthetic JPEG。对象存储配置不再有代码凭据兜底，未注入环境值时安全地拒绝上传。
- `2026-07-13`：Capture 上传写入原图 24 小时到期时间；清理器使用数据库行锁抢占过期对象，删除成功标记 `deleted`，失败标记 `failed` 并允许后续重试，审计仅写稳定事件名和资源 ID。OCR 失败 7 天、裁剪图 30 天策略已统一为固定时间函数；OCR 失败入口随后由 `LocalOcrJob` 接入，裁剪入口仍待实现。
- `2026-07-13`：新增 `model_provisioning.py`、官方五模型清单入口与 API 多阶段 Dockerfile：构建阶段只接受 HTTPS 归档、逐项校验 SHA-256、拒绝路径穿越/软链接并写入构建标记；运行时 Adapter 要求五个预置目录和标记，显式使用 CPU/`paddle_static`，不自动下载或更新。
- `2026-07-13`：按 `linux/amd64` 目标完成 `study-api:local` 镜像构建；依赖层锁定安装成功，五个 PaddleOCR 官方归档均在构建阶段通过清单 SHA-256，模型复制到运行层，运行层无模型下载/更新逻辑。Mac arm64 仅通过 Docker 模拟构建，Ubuntu 24.04 x86_64 是目标部署形态。
- `2026-07-13`：新增 OCR 前置有界对象读取、声明大小/SHA-256、JPEG/PNG 容器头、尺寸/像素数校验、Pillow 完整像素解码和无 EXIF/元数据规范化重编码；新增 PaddleOCR 文本结果纯解析、临时文件执行边界、置信度边界和强制人工确认标记。真实题型模型实测仍未实现。
- `2026-07-13`：修复镜像内 PaddleOCR 真实启动缺少的 `libgl1`/`libglib2.0-0`/`libgomp1`，关闭未锁定的 `UVDoc` 去畸变和模型源检查；五个锁定模型在无网络 linux/amd64 容器中完成 1×1 synthetic PNG CPU 烟测，空结果仍要求人工确认。
- `2026-07-13`：新增按 Household/Child 边界原子认领 Capture 对象的级联删除编排；对象逐项删除，失败标记 `failed` 并可重试，成功/失败均写稳定审计事件且不记录对象键。内存单元与 PostgreSQL 集成回归覆盖成功、重试、幂等和错误 Household。
- `2026-07-13`：新增 local/CI 家长删除孩子档案 API；只有 Capture 级联全部成功后才删除合成 Profile，失败返回 503 且档案保持可见，同一幂等键可重试/重放；OpenAPI 增加向后兼容的 DELETE 路径。生产 Profile 持久化、数据库元数据、派生缓存/向量和备份仍未接入。
- `2026-07-13`：新增 `0005_ocr_result_persistence` 与 PostgreSQL OCR 仓储；只保存 Provider/模型/Schema 版本、置信度和规范化候选文本，空结果也持久化，结果始终要求人工确认。事务内绑定 Capture 的 Household/Child，支持幂等重放并拒绝跨家庭/跨孩子读取；审计不写候选原文。
- `2026-07-13`：新增家长保存/立即删除单张图片入口；保存和删除都要求家长 Household 授权与幂等键，单对象删除先抢占再调用私有存储，失败可重试，成功不删除 Capture 元数据，审计仅记录稳定事件名和资源 ID。
- `2026-07-14`：新增 `evals/ocr_synthetic_v1.json` 与无外部服务的固定 OCR 合同评测入口；6 个 synthetic cases 全部通过，覆盖正常候选、低置信度人工校正、空结果、空行过滤及输入拒绝，评测明确 `provider_calls: false`。
- `2026-07-14`：新增 `LocalOcrJob` Worker 边界，串联已确认 Capture 的私有对象有界读取、图片规范化、本地 OCR Adapter 和候选结果仓储；未确认上传、非法图片和 Provider 失败均不会持久化结果，Redis/持久化 Worker 和真实题型模型基准仍未接入。
- `2026-07-14`：Worker 失败会把未删除的 Capture 标记为 `ocr_failure`，从失败发生时起最多保留 7 天；重复失败不会延长期限，清理器仍可按既有行锁/失败重试机制删除对象，审计只记录稳定事件名和资源 ID。
- `2026-07-14`：此前 OCR 基线门槛通过：60 项单元、14 项 PostgreSQL/MinIO 集成、Ruff lint/format、Mypy 23 个源文件，以及 `ocr-synthetic-v1` 6/6；仅使用合成数据，未调用外部 Provider。
- `2026-07-14`：新增 child-only 幂等 OCR 入队端点和 local/CI `InMemoryOcrJobQueue`；`LocalOcrDispatcher` 一次只领取一个任务，成功写入结果 ID，失败只写稳定错误码并允许用新幂等键重试，不保存 Provider 错误详情。
- `2026-07-14`：入队调度切片定向测试、OpenAPI 结构检查、Ruff、Mypy（24 个源文件）通过；完整 64 项单元与 15 项 PostgreSQL/MinIO 集成门槛通过。
- `2026-07-14`：新增 `0006_ocr_job_ledger`；PostgreSQL 队列按 Household/Capture/幂等键唯一，使用 `FOR UPDATE SKIP LOCKED` 领取任务，失败只保留稳定错误码，超过租约的 running 任务可重新领取；定向迁移/队列集成测试通过。
- `2026-07-14`：新增独立一次性 `run_ocr_worker.py` 入口；启动强制校验本地 MinIO、PostgreSQL 和五个带 SHA-256 构建标记的模型目录，CLI 只输出 idle/succeeded/failed/startup_error/worker_error 稳定状态，不输出 Provider 或配置详情。
- `2026-07-14`：Worker 入口相关全量门槛通过：67 项单元、15 项 PostgreSQL/MinIO 集成、Ruff、格式、Mypy 25 个源文件、`ocr-synthetic-v1` 6/6 和 `git diff --check`。
- `2026-07-14`：新增 child-only OCR 结果读取接口与 `OcrResultWithCandidates` 合同；服务端再次校验 Household/Child/Capture 绑定，兄弟孩子、家长、跨家庭和 Capture 不匹配均拒绝，候选结果仍要求人工确认；定向路由测试 4 项通过。
- `2026-07-14`：结果读取增量全量门槛通过：71 项单元、15 项 PostgreSQL/MinIO 集成、OpenAPI 结构检查、Ruff、格式、Mypy 25 个源文件、`ocr-synthetic-v1` 6/6 与 `git diff --check`；仅使用 synthetic 数据，未调用外部 Provider。
- `2026-07-14`：新增 child-only OCR 候选确认；只提交候选 ID 与 Capture 版本，服务端重新校验结果/候选/绑定关系后复用 CaptureCorrection 追加写，用户幂等键保持 128 字符边界内，OCR 结果仍不可变。
- `2026-07-14`：候选确认增量质量门槛通过：73 项单元、16 项 PostgreSQL/MinIO 集成、OpenAPI 结构检查、Ruff、格式、Mypy 25 个源文件与 `git diff --check`；仅使用 synthetic 数据。
- `2026-07-14`：按顺序继续客户端 UI 实现；Flutter 第 1/2/3 张横屏学习桌、拍题输入、OCR 确认和分数思考提示原型已落地，加入合成头像/分数示意/题目照片资源，拍照/相册选择/示例题目入口可进入人工确认页，iOS 相机和相册权限声明已加入；新增 `CaptureApiClient`，实现 JPEG/PNG 校验、SHA-256、短期签名 PUT、服务端确认、幂等 OCR 入队、Job 轮询和候选人工确认/纠正，Flutter pub get、format、analyze、9 项测试通过；页面已由显式 `STUDY_CAPTURE_SESSION_ID` 调试开关接入，带开关时上传后显示等待状态，不展示合成候选。iOS 已锁定横屏，含原生 `image_picker` 的无签名 `Runner.app` 构建成功并重新安装到实体 iPad，用户已实机确认拍照、权限和“已选择题目照片”页面通过。Flutter 不支持该实体设备截图，目标 landscape QA 仍 blocked。实体上传 smoke test 已完成；下一项是让合成 StudySession 的 OCR Worker 结果可被 iPad 读取。
- `2026-07-14`：实体 iPad local Capture smoke test 通过；API 日志确认预签名上传 201、服务端对象确认 201、OCR 入队 202，且页面未展示合成 OCR 候选。仅使用合成 StudySession 和本地 MinIO，未接入真实儿童图片；OCR Worker 结果状态/轮询仍待实现。
- `2026-07-14`：新增 child-only OCR Job 状态读取接口和 Flutter `getOcrJob` 解析；服务端只返回 queued/running/succeeded/failed、attempt 和 result_id 等稳定字段，跨孩子读取返回 404；定向 API、OpenAPI 和 Flutter 测试通过。
- `2026-07-14`：Flutter 确认页已接入有界 OCR Job 轮询、`result_id` 候选读取、候选确认和手工纠正；候选返回前保持等待，候选返回后仍必须人工确认。客户端测试覆盖 queued/succeeded 读取、候选字段、确认/纠正路径和幂等键；Flutter 总测试数增至 9。
- `2026-07-14`：增加显式 local durable mode：API 的 Learning/Capture、OCR Job 和 OCR 结果仓储可统一切换到 PostgreSQL；Worker 增加可选 `--watch` 轮询模式，默认一次性命令保持不变。Ruff、Mypy、74 项 API 非集成测试和 `git diff --check` 通过。
- `2026-07-14`：新增 PostgreSQL/MinIO synthetic API + Worker 闭环集成测试；真实走私有 MinIO、Job Ledger、`LocalOcrJob`、结果持久化和 child-only 结果读取，Provider 使用 synthetic adapter。完整 API 集成回归 17 项通过，测试结束删除 synthetic 对象。
- `2026-07-14`：新增 `check_ocr_runtime.py` 只读预检和固定门禁测试；严格要求 Ubuntu 24.04、x86_64、Python 3.12、PaddlePaddle 3.3.1、PaddleOCR 3.7.0 及五个带 SHA-256 构建标记的模型目录。当前 macOS 预检稳定返回 `blocked`，未执行真实模型推理。
- `2026-07-14`：新增 `ocr-model-synthetic-v1` 锁定模型 smoke runner；输入由脚本内存生成，调用前强制运行时预检，输出只含每题状态和延迟，不接受图片路径、不保存 OCR 原文。当前 macOS 按预期阻塞，Ubuntu 真实 CPU 推理未执行。
- `2026-07-14`：优化 `LocalPaddleOcrAdapter`：文本与公式引擎在实例内按需初始化并复用，每次使用前仍校验五个预置模型目录和 SHA-256 标记；新增工厂调用次数与实例复用回归测试，避免 Worker 对每张图片重复加载模型。
- `2026-07-15`：补齐按需公式 OCR 执行边界与 `rec_formula` 解析；公式结果没有 Provider 置信度时按 0.0 保守处理，始终保持人工确认；锁定模型 smoke fixture 增加公式 case。81 项 API 非集成测试、Ruff、Mypy 和 `git diff --check` 通过，当前 macOS 真实模型 smoke 仍按预检阻塞。
- `2026-07-15`：将 OCR mode 贯穿 OpenAPI、Flutter `CaptureApiClient`、内存/PostgreSQL Job Ledger 和 Worker：旧请求默认 `text`，显式 `formula` 才调用公式模型；新增 `0007_ocr_job_mode` 前滚迁移、模式幂等冲突保护和 API/Worker/Flutter 回归。83 项 API 非集成、17 项 PostgreSQL/MinIO 集成、Flutter 10 项测试、Mypy/Ruff 均通过。
- `2026-07-15`：完成 `0007_ocr_job_mode` 在本地 synthetic PostgreSQL 的 downgrade/upgrade 往返验证；固定 `ocr-synthetic-v1` 评测 6/6 通过，模型 smoke 在当前 macOS 按平台预检稳定返回 `blocked`，未执行真实推理。
- `2026-07-15`：根据项目 Owner 提供的架构讨论，接受 ADR-0015 并完成文档级路线调整：原图留在家庭边界，本地 OCR 仅参与脱敏，单一获批云视觉 Provider 解析脱敏副本，人工确认后再进入 Tutor。ADR-0012 标记为 Superseded；未修改现有代码、合同或数据库。
- `2026-07-15`：新增 Provider-neutral 的 PrivacySanitization/ImageAnalysisJob/QuestionExtraction/VerifiedQuestion Schema；实现本地 PrivacySanitizer 的元数据清除、检测区域实色覆盖、不可逆重编码、低置信度/大或歧义人脸/缺失区域阻断，并完成 6-case synthetic eval。上传确认同时核验对象实际 SHA-256；新增 0008 receipt-only ImageAnalysis ledger/API，未实现真实视觉检测器、云 Provider 或临时副本生命周期。
- `2026-07-15`：新增无 Provider 的 `offline-tutor-policy.v1`，只消费 `VerifiedQuestion` 的结构字段，提供 1～3 级提示、直接答案为空和 0 元成本的固定响应；新增 synthetic eval。Flutter 思考页同步支持第 3 级提示。该降级策略不代表任何云 Tutor 已获批准。
- `2026-07-15`：接入 `LocalPrivacyDetector` 的敏感标签/规则区域信号，新增 Flutter 本地脱敏预览、手动涂抹、不可逆 PNG 生成与 SHA-256 计算；拍题上传路径只接受确认后的脱敏字节，原图不进入上传客户端。Widget/analyze 已通过；真实 iPad 渲染和手动涂抹仍需设备人工验证。
- `2026-07-15`：项目 Owner 接受 ADR-0016，明确自用单家庭 Bearer 令牌和项目 Owner 自行部署 NewAPI；新增 HMAC token 签发/解析、OpenAI-compatible Adapter、显式开关和 Web/Flutter Bearer 注入边界，默认 Provider 关闭。
- `2026-07-15`：ImageAnalysis 从 receipt-only blocked 扩展为安全条件满足且 NewAPI 开启时 queued；新增 `0009_question_extraction`、未确认提取结果仓储、PostgreSQL 行锁/stale lease worker、提取读取合同和失败稳定状态。110 项 API 非集成、18 项 PostgreSQL/MinIO 集成、OpenAPI 21 paths/34 schemas/6 JSON schemas、Flutter/Web 门槛通过；当时实际 NewAPI 联调和人工确认接口仍待完成，后续已补齐人工确认代码，真实 Provider 联调仍保留为环境验收。
- `2026-07-15`：补齐自用 Docker Compose 部署：API 镜像复制 `migrations/`、`alembic.ini` 和 worker 脚本；Compose 增加 PostgreSQL/Redis/MinIO 持久卷、一次性 `migrate`、API healthcheck、默认 ImageAnalysis worker 和家长 Web；新增 `infra/compose/.env.example` 和自动读取的 `infra/compose/.env` 部署方式。Compose config、`linux/amd64` API/迁移镜像构建、ARM64 Web standalone 镜像、Web 格式/Lint/类型/测试/构建、镜像内容检查和 110 项 API 非集成测试通过；完整容器启动、真实 NewAPI 联调、人工确认接口、脱敏副本清理和备份恢复仍待完成。
- `2026-07-15`：按本机 Apple Silicon 调试需求增加 Flutter 1.2 秒有限启动过渡，首页档案加载与动画并行，减少动态效果时跳过；Compose 的 ImageAnalysis worker 移入默认 profile，NewAPI 关闭时以空闲实现保持健康且不读取图片/连接 Provider。Dockerfile 取消固定 amd64，依赖标记保留 macOS ARM64 和 Linux x86_64 Paddle，同时为缺少 PaddlePaddle 3.3.1 Linux aarch64 wheel 的原生 ARM 调试镜像跳过 Paddle/模型和专用系统库。Compose 静态配置无额外 profile，`linux/arm64` 镜像构建、110 项 API 单元、13 项 Flutter 测试及静态检查通过；当时完整 Compose 启动未执行，后续已在 Ubuntu x86_64 VM 完成基础启动验收。
- `2026-07-15`：项目 Owner 批准下一阶段改用账号密码。已接受 ADR-0017，建立 PLAN-0007/TODO-012，并同步 PRD/架构/安全/测试/运维边界；一次性 `admin/admin123456` 仅允许空库、本机首次登录，改密前阻断家庭数据。当前 HMAC Bearer 仍是运行时事实，本轮未修改代码、合同、迁移或 Compose。
- `2026-07-16`：完成 `0010_verified_question`、人工确认/读取 API、VerifiedQuestion 内存/PostgreSQL 仓储和迁移测试；验证请求带 Capture 版本、Household/Child 绑定和幂等键，未确认提取保持不可变。
- `2026-07-16`：ImageAnalysis worker 成功后立即删除脱敏派生对象，失败路径也尝试删除并保留稳定失败状态；新增清理成功/失败回归测试。TASK-0006 的代码验收完成，真实 NewAPI、真实视觉检测器、iPad 回归和备份恢复仍是环境验收项。
- `2026-07-16`：在 Ubuntu 24.04 x86_64 VM 完成自用 Compose 基础验收：Docker/Compose、PostgreSQL/Redis/MinIO/API/Web/迁移/worker 健康，`0011` 前滚、loopback bootstrap login、重启恢复和内存 synthetic OCR smoke 通过；容器内 OS 预检因 Debian 13 运行层而保持 blocked。NewAPI key 未提供，Provider 保持关闭；首次改密、Cookie/CSRF、孩子账号/iPad 生命周期、真实视觉链路和备份恢复仍未完成。
- `2026-07-16`：修复 OCR 预检与发布镜像运行层的契约：宿主继续要求 Ubuntu 24.04，amd64 镜像通过显式 `STUDY_OCR_CONTAINER_RUNTIME=true` 接受锁定 Debian 13；新增单元覆盖，远端完整 4-case OCR eval 待重建镜像后执行。
- `2026-07-16`：远端重建 x86_64 API 镜像后，OCR 预检输出 `ready`，`ocr-model-synthetic-v1` 4/4（普通文本 3、公式 1）通过；未发送图片到 NewAPI。
- `2026-07-16`：项目 Owner 配置 NewAPI key 后启用远端 Provider；新增可清理的合成 live eval，主机和 API 容器访问 `newapi.iuhui.site` 均收到 HTTP 403，未取得 Extraction。worker 新增稳定 Provider 错误码，失败任务、MinIO 对象和合成数据库记录已清理。
- `2026-07-16`：定位 HTTP 403 为 Cloudflare 1010 对 Python 默认 `urllib` User-Agent 的拦截；Adapter 新增受限 `STUDY_NEWAPI_USER_AGENT`（默认 `study-api/0.5`）、`Accept: application/json` 和完整 `question-extraction.v1` 字段提示。远端重建 API/worker 后，synthetic live eval 成功得到 `needs_confirmation=true` 的 Extraction，脱敏派生对象删除，PostgreSQL synthetic Job 残留为 0；不输出原始 Provider 响应或发送真实图片。远端人工确认生成 VerifiedQuestion 仍待 PLAN-0008 验收。
- `2026-07-17`：家长 Web 增加孩子档案新增、编辑和删除入口；修复 POST/PATCH 代理遗漏 `application/json` 导致 FastAPI 返回 422，并增加代理 Header 回归测试。Web 镜像已部署到 Ubuntu，API/Web 容器及健康端点正常。Profile 仍使用进程内 synthetic 仓储，API 重启后改动不会保留，不把本轮描述为 PostgreSQL 持久化完成。
- 下一步：继续执行 `PLAN-0008` 的远端人工确认、Cookie/CSRF、iPad 会话生命周期和备份恢复验收；真实视觉检测器和固定视觉评测仍作为后续实现项。
