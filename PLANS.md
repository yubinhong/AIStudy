# PLANS.md — PLAN-0012 Capture 服务端流式上传收敛

## 计划元数据

- 计划 ID：`PLAN-0012`
- 关联任务：`TASK-0009`、`TODO-014`、`ADR-0018`
- 状态：`IN_PROGRESS（API/Flutter/契约/Compose 已迁移并部署 Ubuntu；最终设备/Provider 验收未完成）`
- 优先级：`P0 / SECURITY / API CONTRACT`
- Owner：Codex（后续执行）；项目 Owner（用户，架构决定已批准）
- 创建/更新：`2026-07-18`

## 目标与现状冲突

目标链路统一为：

```text
App → API：携带可撤销 Session 上传图片
API：有界流式校验大小、类型、文件头、尺寸/像素和 SHA-256
API → 私有 MinIO：只通过 Compose 内部地址流式写入
API → App：返回已完成对象校验的 Capture
```

当前 OpenAPI/API `0.8.0`、Flutter、Compose 和 Ubuntu 已执行“Session → API 原始流 → 内部 MinIO multipart”，并已移除正式契约中的预签名/独立确认；远端旧 `.env` 中残留的公开 MinIO 地址已清理，MinIO `9000` 未向宿主/LAN 暴露。隐藏旧路由仅作为测试与受控回滚兼容，不能作为正式客户端合同。

## 范围与不变量

- 修改范围：`packages/contracts`、`services/api`、`apps/child_flutter`、`infra/compose` 及测试/部署文档；不改变图片保留、脱敏、单 Provider、VerifiedQuestion 或 Tutor 信任边界。
- App 只连接用户配置的 API 基础地址，不解析、保存或请求任何 MinIO URL，不持有对象存储密钥。
- API 必须在读请求体前验证 Session、Household、角色、孩子和 StudySession；上传写接口继续要求 `Idempotency-Key`。
- API 必须分块读取、增量计数/哈希并向随机 staging 对象流式写入；禁止无界 `request.body()`/完整 `bytes` 聚合。超过 8 MB、超时或断连必须立即中止并清理。
- 声明 MIME、JPEG/PNG 文件头、宽高/总像素、完整解码、实际 SHA-256 和声明值必须由服务端独立验证；客户端计算值只作声明与幂等材料。
- MinIO Bucket 保持私有，服务端内部继续使用 S3 兼容 Adapter；宿主/LAN 不发布 `9000`。对象键、图片、会话、存储凭据和内部 URL 不得进入响应、日志或审计。

## 实施阶段

- [x] 1. 契约收缩：发布单一 Session 鉴权上传操作接收单文件原始流并返回 `Capture`；正式 OpenAPI 删除 `upload_url`、`upload_expires_at`、`CaptureUpload`、`ConfirmCaptureUploadRequest` 和独立确认端点。
- [x] 2. 存储 Adapter：用现有 boto3/S3 边界实现带背压的 staging/multipart 流式写入；失败中止，完成后验证失败删除对象，不新增依赖。
- [ ] 3. API 信任边界：在读取字节前完成授权；实现实际字节上限、媒体/文件头、宽高/像素、完整解码、增量 SHA-256、请求/空闲超时、并发/账号限速、幂等重放/冲突及稳定错误码。
- [x] 4. Flutter 迁移：只向 API 上传并展示服务端错误；删除生产上传客户端中的预签名 URL、MinIO 直连和独立确认，保留脱敏预览、手动涂抹与确认哈希。
- [x] 5. Compose 收口：示例配置删除 `OBJECT_STORAGE_PUBLIC_ENDPOINT_URL`、`MINIO_API_PORT` 和预签名 TTL；取消 `9000`/`9001` 宿主机端口映射，只允许 API/worker/备份通过内部 `minio:9000` 访问。
- [ ] 6. 质量门槛：已通过 API Ruff/Mypy/单元、Flutter format/analyze/test 和 OpenAPI 运行时路径检查；仍需完整契约差异、Compose 有真实 `.env` 的 config、断连/超时/并发/端口扫描测试。
- [x] 7. 部署迁移：先备份并部署匹配的 API/Web/worker，移除旧端点和 MinIO LAN 端口；Ubuntu synthetic 请求已走到 NewAPI，但 Provider 返回 HTTP `402`。Nova 9/iPad 真机回归和额度恢复后的 Extraction/VerifiedQuestion/Tutor 验收仍待执行。

## 验收标准

- [x] OpenAPI 和 Flutter 上传客户端响应模型中不存在 `upload_url`、`upload_expires_at`、对象键或独立上传确认合同。
- [ ] App 网络测试证明图片只发送到配置的 API 地址；代码、日志、SQLite 和错误中无 MinIO 地址或存储凭据。
- [ ] 0 字节、超过 8 MB、伪造 MIME/文件头、异常尺寸/像素、截断、哈希不一致、慢速/断连和并发请求均被服务端有界拒绝，失败无残留 staging 对象。
- [ ] 最大允许图片与批准并发下，API 内存受块大小和并发上限约束，不随请求体无界增长；MinIO/数据库部分失败可安全重试且不产生重复 Capture。
- [ ] `docker compose config` 与主机/LAN 端口检查证明没有发布 `9000`，运行配置不存在 `OBJECT_STORAGE_PUBLIC_ENDPOINT_URL`/`MINIO_API_PORT`，内部 API/worker/备份仍可访问私有 Bucket。
- [ ] synthetic 与真机均完成 `API upload → confirmed Capture → ImageAnalysis → Extraction → VerifiedQuestion`，不读取或输出真实题目内容；当前 Ubuntu synthetic 已完成上传/Provider 到达，因 HTTP `402` 尚未完成后半段。

## 兼容、部署与回滚

- 这是用户批准的破坏性预发布合同变化；API 和 Flutter 必须成对升级。不得让新 App 调旧 API，或让旧 App 在 `9000` 已关闭后继续使用预签名 URL。
- 迁移窗口只在测试环境保留旧端点；正式 OpenAPI 不同时暴露两套上传方式。确认新 App/API 通过后才关闭 MinIO LAN 端口和删除旧配置。
- 回滚必须使用上一套匹配的 API/App 镜像，并仅在隔离受信 LAN 临时恢复旧端点、`9000` 和旧配置；Bucket 继续私有，客户端永不获得长期密钥。不得删除已确认 Capture 或用清卷回滚。

---

# PLANS.md — PLAN-0013 Web 统一孩子管理与多孩子工作台

## 计划元数据

- 计划 ID：`PLAN-0013`
- 关联事项：`TODO-015`、`FR-001`、`FR-016`、`ADR-0005`、`ADR-0017`、`ADR-0019（Proposed）`
- 状态：`IN_PROGRESS（API/Web/首页选择已实现；PostgreSQL 迁移与真实部署验收待完成）`
- 优先级：`P0 / WEB UX / IDENTITY`
- Owner：Codex（后续执行）；项目 Owner（用户，交互方向已批准）
- 创建/更新：`2026-07-18`

## 问题与当前证据

- `apps/web/src/app/accounts/page.tsx` 已改为加载孩子管理聚合并用一个表单创建档案和账号；账号启停、重置密码、资料编辑、导出和删除入口集中在孩子条目。
- `apps/web/src/app/page.tsx` 已支持 `?child=<uuid>` 当前孩子选择，任务请求带孩子作用域，周报和档案卡使用同一授权孩子。
- `0016_child_account_uniqueness` 增加“一份孩子档案最多一个孩子账号”的条件唯一索引；迁移遇到历史重复绑定会明确失败，不静默删除账号。

## 目标与设计边界

- Web 将“孩子”作为一个管理聚合：一次填写姓名、年级、用户名和初始密码，一次提交后原子创建 ChildProfile 与绑定的 child Account；用户不再理解或手动选择两张表。
- 数据库不把认证与档案物理合表。`Account` 继续隔离密码哈希、锁定、状态和会话生命周期，`ChildProfile` 继续承载姓名、年级、教材和科目；API 用事务命令和聚合读模型提供单一产品体验。
- 家长账号与孩子列表分区展示。孩子卡片同时显示档案和登录状态，并集中提供编辑资料、启停账号、重置密码、导出和删除入口。
- 首页增加带可见标签、支持键盘和读屏的“当前孩子”下拉选择器。问候、今日任务、当前档案和周报必须全部按同一个已授权 `child_id` 查询；家庭孩子总数保持家庭级，设备数在设备尚未绑定孩子前也保持家庭级。
- 选择器只改变展示范围，不改变服务端授权。任意 URL、Cookie 或客户端状态中的 `child_id` 都必须重新校验 Session、Household 和角色，禁止跨家庭/跨孩子枚举。

## API、数据与兼容方案

- 在 `packages/contracts` 定义聚合写入与读取模型，例如 `CreateChildRequest { display_name, grade, curriculum_version, subjects, username, initial_password }` 和不含密码/哈希的 `ChildManagementView`。最终路径沿用 `/children` 还是新增显式聚合路径，在实现前通过 OpenAPI 差异确认；Web 不再串联两个公开创建请求。
- 单一受鉴权、带 `Idempotency-Key` 的事务同时创建 Profile 与 Account；用户名冲突、字段校验、密码策略或数据库错误时整体回滚，不留下孤立档案或孤立账号。响应不得返回初始密码、密码哈希或会话材料。
- “编辑档案”和“重置/启停账号”可保持不同内部命令与再认证策略，但 Web 统一从同一孩子管理卡进入；删除继续执行现有孩子数据级联和会话撤销。
- 实施前生成只读数据审计：已绑定的一对一记录直接聚合；无账号档案显示“未开通登录”并允许补建；同一档案绑定多个孩子账号时阻断自动迁移并要求人工选择，不静默删除。清理后增加 `(household_id, child_id)` 的 child-role 唯一约束或等价条件唯一索引，并提供前滚修复方案。
- 首页以 URL 查询参数作为本次选择的显式来源，并可持久化最近一次已授权选择；优先级为“有效显式选择 → 有效最近选择 → 稳定排序后的首个孩子”。孩子被删除或失权时清除旧选择并安全回退，零孩子时展示创建入口。
- 任务查询必须由 API/数据层按 `child_id` 过滤，周报继续要求同一 `child_id`；不得先拉取全家庭学习明细再只在浏览器隐藏其他孩子。

## 实施阶段

- [ ] 1. 契约与数据审计：确认现有账号—档案基数，补充聚合 Schema、稳定错误码、幂等语义和 OpenAPI 兼容说明。
- [ ] 2. API 事务聚合：实现原子创建/补建孩子登录、聚合查询和一对一约束迁移；保留现有档案数据并覆盖并发、回滚和反向越权。
- [ ] 3. 管理页重构：合并孩子档案/孩子账号创建表单和列表，家长账号移到独立区域；已有无账号档案提供“开通登录”，不要求输入或选择 UUID。
- [ ] 4. 首页孩子选择：增加可访问的选择器和无脚本/空状态回退；选择后统一刷新问候、任务、档案与周报，并在 URL/安全持久化状态中恢复最近选择。
- [ ] 5. 质量与发布：运行 OpenAPI 差异、迁移、API/Web 单元与集成、浏览器 E2E、生产构建、授权/CSRF/日志检查；先部署数据库/API，再部署 Web，并用两个 synthetic 孩子验证。

## 验收标准

- [ ] 新建孩子只出现一个表单和一次提交；成功后同时存在一份档案和唯一绑定账号，任一环节失败均为零新增记录，重复幂等请求不产生第二个孩子。
- [ ] 管理页每个孩子只显示一张聚合卡；卡片能区分“登录已启用/已停用/未开通”，家长账号不混入孩子卡片。
- [ ] 两个孩子场景中，选择任一孩子后，问候、今日任务数量/内容、档案卡和周报均属于同一个孩子；刷新后选择仍有效，删除当前孩子后安全回退。
- [ ] 家庭级孩子总数不随选择变化；设备在无 child 绑定模型时明确显示家庭级数据，不伪装成所选孩子的设备。
- [ ] 篡改其他 Household/未绑定孩子的 `child_id` 返回统一 403/404 且无数据泄漏；孩子会话不能使用选择器访问兄弟姐妹数据。
- [ ] 旧数据审计、重复绑定处置、约束迁移、前滚修复和 Web/API 成对回滚均有记录；日志不含密码、用户名明文或儿童姓名。

## 回滚

- Web 可回退到旧展示，但不得在已启用一对一约束后重新允许为同一档案创建多个孩子账号；API 优先保持新聚合端点并向前修复。
- 数据库迁移只新增校验/索引，不合并或删除 `accounts`/`child_profiles`。若约束上线阻塞旧写入，回滚应用并暂时移除新约束前必须保留审计结果，不删除任何孩子数据。
- 首页选择状态仅是显示偏好；回退版本忽略未知查询参数/Cookie，不影响学习事实。

---

# PLANS.md — PLAN-0014 教材驱动的数学错题学习闭环

## 计划元数据

- 计划 ID：`PLAN-0014`
- 关联事项：`ADR-0020`、`TODO-016`～`TODO-019`、`FR-002`、`FR-005`、`FR-006`、`FR-011`、`FR-017`～`FR-020`
- 状态：`IN_PROGRESS（错题/复习最小 API、契约、0017 迁移和客户端调用已实施；教材、三入口和完整复习 UI 待完成）`
- 优先级：`P0 产品主线 / P1 分阶段交付`
- Owner：Codex（后续执行）；项目 Owner（用户，方向与本计划原则已批准）
- 创建/更新：`2026-07-18`

## 1. 目标产品主线

将当前偏“今日任务 + 拍题 + 最小 Tutor”的实现收敛为数学首科的教材驱动错题学习系统：

```text
家长设置孩子年级/学期/教材版本
→ 导入家庭有权使用的教材与课程资料
→ 系统解析章节/知识点并由家长审核发布
→ 孩子选择“数学”
→ 错题讲解 / 复习错题 / 今日任务
→ VerifiedQuestion + 已确认作答状态（有作答 / 空白）+ 已发布知识依据
→ 分模式讲解、错题沉淀、到期复习和任务建议
```

成功标准不是“AI 给出答案”，而是每道错题都有可追溯题目、已确认的孩子作答状态、年级/教材/知识点依据、匹配作答状态的讲解记录、复习计划和后续掌握证据。

## 2. 当前实现事实与缺口

- `ChildProfile` 只有 `grade`、单个 `curriculum_version` 字符串和 `subjects=[math]`，没有学年、学期、教材版本实体、孩子教材绑定或发布快照。
- 当前没有教材文件上传、格式/版权校验、章节解析、知识点审核、来源定位、版本更新或内容删除链路。
- `VerifiedQuestion`、TutorTurn、Attempt、StudySession 已持久化，但 Attempt 只有简短 `answer_summary`，没有正确性、错误步骤、错误类型或知识点依据。
- 当前已新增正式 `MistakeRecord`、`ReviewSchedule`、到期查询、确定性间隔算法和三次连续正确后的关闭状态；StudySession 的 `needs_review` 仍只作为历史投影，教材 grounding、作答四态和完整复习 UI 尚未接入。
- 当前 Task 只有家长创建的标题/日期/科目，没有来源、推荐、教材/错题引用、家长审批或系统生成规则。
- Flutter 当前首页只加载今日任务并提供拍题入口，没有“学科 → 错题讲解 / 复习错题 / 今日任务”信息架构。
- PLAN-0012 的 API 流式图片上传和 PLAN-0013 的统一孩子管理/多孩子选择仍未实现；本计划不能覆盖或绕过它们。

## 3. 产品与交互定义

### 3.1 家长端：孩子学习范围

- 家长先选择孩子、数学、年级、学期、教材出版社/版本和适用学年，形成 `CurriculumAssignment`；更换年级/学期不覆盖历史学习记录。
- P1 首批导入以 PDF 为主，文本 PDF 与扫描 PDF 的处理器可以不同；DOCX/图片包属于后续兼容项。精确大小、页数和格式上限在实现任务中按压测批准，未批准格式明确拒绝。
- 每份 `LearningMaterial` 必须记录家庭、SHA-256、文件类型、版本、来源/授权声明、导入者和处理状态。重复文件幂等返回既有结果。
- 解析产物先进入草稿：目录、章节、知识点、页码/段落来源和置信度。家长必须审核、编辑并发布不可变 `CurriculumSnapshot` 后，Tutor/任务系统才能引用。
- 更新教材生成新版本快照；既有错题/讲解继续引用原快照，不静默漂移到新知识结构。

### 3.2 孩子端：数学三入口

- 登录并取得唯一绑定档案后显示学科页；当前只显示可用的“数学”，不制造尚未实现的语文/英语入口。
- 进入数学后固定呈现三个低干扰主入口：`错题讲解`、`复习错题`、`今日任务`。一次只进入一种模式，页面始终标明当前模式。
- 无教材、无错题、无到期复习或无今日任务时显示可操作空状态；不能用演示数据伪装真实内容。

### 3.3 错题讲解模式

1. 孩子拍摄做错或没有思路的题，画面应尽量同时包含完整题目和孩子的答题区。沿用 PLAN-0012 的 Session 鉴权 API 上传、隐私脱敏、云视觉解析和人工确认，生成 `VerifiedQuestion`。
2. 云视觉 Schema 必须分开提取题目与孩子作答，输出候选 `answer_state`：`worked`（看到作答）、`blank`（答题区可见且空白）、`unclear`（无法判定）、`answer_area_missing`（未拍到答题区），并返回置信度和作答步骤候选。该结果必须由孩子确认/修正后才成为 `AttemptEvidence`。
3. `worked` 记录可见的原答案/步骤，并允许补充审题错误、概念不清、方法错误、计算错误、粗心/抄写错误或其他自述；`blank` 在用户确认后记录为 `blank_confirmed/no_approach`，不强迫孩子先编造一次错误作答。`unclear` 或 `answer_area_missing` 必须请孩子重拍或手工选择真实作答状态，不得自动当作空白。
4. 系统按孩子的已发布 CurriculumSnapshot 检索章节、知识点和最小来源片段。无可靠匹配、超出当前年级或来源冲突时明确标记 `needs_grounding_review`，不伪造教材依据。
5. `mistake_explanation` 按作答状态分支：`worked` 优先指出第一个可验证的错误步骤，解释“错在哪里/怎样改”；`blank_confirmed` 视为“没有思路”，可从题意、已知/所求和知识点开始完整讲解，无需再要求一次尝试。两个分支都要给出逐步过程、答案校验和一道低风险变式练习。
6. Schema、算术/单位等可确定规则、知识点范围和安全策略通过后，保存 `MistakeRecord` 与版本化讲解；AI 输出本身不能直接成为标准答案或掌握度事实。
7. 讲解后鼓励孩子完成一次重新作答；结果写入追加式 Attempt，并创建首个 ReviewSchedule。失败仍可保存为待家长复核，不丢原题、空白事实或已有作答。

### 3.4 复习错题模式

- 默认进入“今日到期”队列，而不是每次无差别遍历全部历史；另提供“复习全部”入口按筛选后的稳定顺序逐题过关。
- 每题先隐藏历史答案和完整讲解，要求孩子重新作答；错误时先给提示，再允许查看已批准讲解。
- `review-policy.v1` 使用可版本化的确定性间隔，初始建议为 1、3、7、14、30 天：正确晋级，错误回到 1 天并保留新 Attempt；具体间隔在实现前用家庭试用确认，AI 不直接决定到期时间。
- 每题结果原子更新 ReviewSchedule 派生状态并追加 ReviewAttempt/Attempt；重复提交幂等，历史不覆盖。连续达到批准门槛后标记“已掌握”，再次答错可重新激活。

### 3.5 今日任务模式

- `parent_assigned`：家长手工选择教材章节、已有练习或错题。
- `review_due`：系统按确定性复习策略把到期错题组成建议；在家长开启对应家庭设置后可自动下发。
- `system_suggested`：根据反复出错知识点和当前教材范围生成 `TaskRecommendation`，默认只作为家长可审核/修改/拒绝的建议，不能静默变成孩子任务。
- P1 第一阶段只从已有错题和家庭导入且已发布的练习中选题。AI 生成新变式题后置到固定正确性/难度/版权 eval 通过，并默认要求家长确认。
- Task 保存来源类型、Mistake/KnowledgePoint/Material 引用、推荐/批准者、策略版本和生成原因；周报可以解释“为什么安排”。

## 4. 领域与契约目标

### 4.1 新增或扩展实体

| 实体 | 最小职责 | 关键不变量 |
| --- | --- | --- |
| `CurriculumAssignment` | 孩子某学期的学科、年级、教材版本 | Household/Child scoped；历史不可覆盖 |
| `LearningMaterial` / `MaterialIngestionJob` | 导入文件、授权、哈希和解析状态 | 私有、版本化、幂等；原文不进入日志/Prompt |
| `CurriculumSnapshot` | 家长审核发布的章节/知识点/来源图 | 发布后不可变；Tutor 只引用已发布版本 |
| `KnowledgePoint` / `KnowledgeEvidence` | 知识点及页码/段落来源 | 每个结论可追溯到材料版本 |
| `MistakeRecord` | VerifiedQuestion、首次作答状态证据、错因/无思路、知识点和状态 | 必须有孩子/家庭、确认题目和已确认 AttemptEvidence；缺失答题区不等于空白 |
| `ReviewSchedule` | 到期时间、间隔、阶段和策略版本 | AI 不直接修改；并发/重试不重复晋级 |
| `TaskRecommendation` | 系统建议与依据 | 默认需家长批准；拒绝不生成 Task |

- 复用 `StudySession`、`Attempt`、`TutorTurn`，增加明确 `mode/source/mistake_id` 等引用；不为每个页面复制一套会话/作答模型。
- Attempt 继续追加写，扩展结构化 `answer_state`、`result`、有限答案/步骤表示和错误自述；`blank_confirmed` 是有效学习事实而不是空数据。儿童原始作答属于 Confidential，不进入普通日志或 AI 调试。
- `AttemptEvidence` 首批作为 Attempt 内的版本化值对象/Schema，不预设独立物理表；包含作答状态、区域覆盖/置信度、有限步骤候选、用户确认来源和 Schema 版本。若后续查询/保留数据证明有独立表需求，再通迁移/ADR 调整。
- OpenAPI/Schema 统一由 `packages/contracts` 提供；所有写操作带 Idempotency-Key，列表使用稳定游标/排序和 Household/Child 过滤。

### 4.2 目标接口族

- 家长：`/children/{id}/curriculum-assignments`、`/materials`、`/material-ingestions`、`/curriculum-snapshots`、`/task-recommendations`。
- 孩子：`/subjects`、`/mistakes/explanations`、`/mistakes`、`/reviews/due`、`/reviews/{id}/attempts`、`/tasks/today`。
- 精确路径、分页和兼容版本在每个实施 TODO 的 OpenAPI 差异中确认；本计划不提前把示例路径描述成已发布合同。

## 5. AI、知识依据与安全门禁

- 图片解析和讲解保持两次独立调用：云视觉产出待确认题目以及与题目分开的作答区/作答状态候选；Tutor 只消费 VerifiedQuestion、已确认 AttemptEvidence、孩子 CurriculumAssignment 和已发布的最小知识片段。
- 教材文件和解析文本是不可信内容，不得把其中指令当系统 Prompt；检索结果以数据字段/引用传入，Prompt 采用固定边界和 Schema。
- Tutor 输出必须包含 `mode`、`curriculum_snapshot_id`、`knowledge_point_ids`、来源引用、逐步解法、最终答案、校验结果、置信/阻断状态和 Policy/Prompt/模型版本。
- “精确讲解”是质量目标，不作绝对保证。低置信度、题目识别未确认、教材不匹配、计算校验失败或超纲时阻断发布并要求重拍、校正或家长复核。
- `guided_practice/review` 模式仍先作答、再提示；`mistake_explanation` 在已确认 `worked` 或 `blank_confirmed` 后允许完整过程。`unclear/answer_area_missing` 不得自动降级为空白；普通任务与复习也不得借讲解模式绕过它们各自的先作答规则。
- Provider 只接收完成当前讲解所需的最少片段，不发送整本教材、对象 URL、无关家庭历史或其他孩子数据；单 Provider、有界重试、成本与审计规则继续有效。

## 6. 分阶段交付

- [ ] M0 — 前置安全与契约：完成 PLAN-0012；确定 PLAN-0013 对每孩子课程配置的聚合入口；按已接受 ADR-0020 补全 OpenAPI/迁移差异和特性开关。
- [ ] M1 — 教材基线（TODO-016）：CurriculumAssignment、PDF 导入、授权/哈希、解析草稿、家长审核发布、版本/删除和来源引用；Tutor 暂不消费未发布内容。
- [ ] M2 — 数学入口与错题讲解（TODO-017）：Flutter 学科/三入口、题目+作答区拍摄引导、作答状态确认、有作答错因讲解/确认空白从头讲解、知识检索、Policy/Schema、MistakeRecord 创建及失败恢复。
- [ ] M3 — 错题本与到期复习（TODO-018）：API 已完成错题记录、到期列表和确定性 ReviewSchedule v1；仍需错题列表/详情/筛选、Flutter 逐题作答、家长查看、重激活 E2E 和复习证据追加写。
- [ ] M4 — 今日任务建议（TODO-019）：父母任务来源、到期复习自动建议、知识薄弱点推荐、家长批准/拒绝、可解释来源和每日上限。
- [ ] M5 — 质量与发布：固定教材解析、知识匹配、讲解正确性、错因、复习和任务推荐 eval；双孩子/跨家庭、弱网、迁移恢复、成本与删除验收后分阶段启用。

## 7. 核心验收

- [ ] 家长能为两个孩子分别设置不同年级/教材，导入一份 synthetic PDF，审核章节/知识点并发布；未发布/跨家庭内容无法被 Tutor 检索。
- [ ] 孩子端登录后先看到数学，数学页准确显示三个入口；每个空状态和失败状态都能恢复。
- [ ] 一道错题必须完成安全上传、题目确认和作答状态确认后才能进入完整讲解；有作答时定位可验证错误，确认空白时从头讲解，答题区缺失/不清时不得自动当空白；讲解引用当前孩子已发布知识范围，并通过 Schema/计算校验。
- [ ] 讲解完成原子创建一条 MistakeRecord 和一个 ReviewSchedule；重试不重复，删除/导出覆盖其题目、作答、讲解和复习历史。
- [ ] 到期复习队列逐题展示且先作答；正确/错误按同一 Policy 产生可复算结果，刷新、断网重试和并发提交不覆盖历史或重复晋级。
- [ ] 今日任务能区分家长安排、到期复习和系统建议；系统建议默认未经家长批准不进入孩子任务，所有安排可解释到错题/知识点/教材来源。
- [ ] 固定数学 eval 覆盖题目识别错误、有作答多步骤提取、真实空白、浅色铅笔字/涂改被误判空白、答题区未入镜、人工修正、教材错版/超纲、计算/单位错误、Prompt 注入、低置信度、Provider 失败、模式绕过和成本上限。

## 8. 兼容、迁移与回滚

- 先扩展现有 Task/Session/Attempt，不重写既有历史；当前 `needs_review` 会话可迁移为“待人工补全”的 Mistake 候选，不能凭一个布尔结果伪造错误答案、`blank_confirmed` 或知识点。
- Curriculum/Mistake/Review/Recommendation 使用新迁移和独立开关。部署顺序为数据库 → API/worker → Web 家长审核 → Flutter 三入口；未达到当前里程碑时入口保持隐藏或明确不可用。
- 回滚应用时保留新表和历史引用，优先前滚修复；不得删除教材、错题、Attempt、复习结果或把 ReviewSchedule 倒退覆盖。关闭 AI 时保留手工建档、手工错因和已有复习队列。
- 教材解析结果、AI 讲解和任务推荐均为可重算派生数据；家长已发布的 Snapshot、VerifiedQuestion、Attempt 和审批事实不可静默重算覆盖。

## 9. 明确后置范围

- 多题整页自动分割、语文/英语、语音、公开题库、教师/学校组织、社交排名继续后置。
- 视频讲解只有在来源版权、年龄适配、题目匹配、字幕/可访问性和离线降级通过独立评审后再接入；当前完整文字/图示解题流程是必达兜底。
- AI 自动生成全新练习题、无需家长审核的个性化课表和 AI 自动判定永久掌握不属于首批实现。

---

# PLANS.md — PLAN-0001 项目上下文建档

> 当前计划只覆盖 `TASK-0001` 的文档初始化，不创建业务代码或部署资源。

## 计划元数据

- 计划 ID：`PLAN-0001`
- 关联任务：`TASK-0001`
- 状态：`COMPLETE`
- Owner：Codex（执行）；项目 Owner `TBD`
- 基线：`master`，无 commit，全部文件 untracked
- 创建/更新：`2026-07-12 14:36 CST`

## 1. 目标结果

完成后，新会话能在 3 分钟内通过 `AI_CONTEXT.md` 理解家庭 AI 学习助手的当前零实现状态、P0/P1/P2 目标、唯一事实源、硬约束、开放决策、风险和推荐第一项任务。

## 2. 上下文与约束

- 当前行为：只有设计稿和通用上下文模板；无代码、依赖、CI、测试或部署。
- 目标行为：所有根目录上下文主文档具体、交叉一致，未知项有 Owner/截止条件，不虚构实现。
- 不变量：孩子端低干扰、AI 不直接代答、家庭强隔离、数据最小化、离线不丢、契约/模型可替换、内容版权边界。
- 禁止事项：不修改 DOCX/Prompt/ADR 模板；不写业务代码；不安装依赖；不部署、提交或推送；不自行批准许可证/法域/Provider/SLO。
- 关键依赖：`家庭AI学习助手_架构设计_v1.0.docx`、`AGENTS.md`、`PROJECT.md`、`prompts/00-project-bootstrap.md`。

## 3. 相关文件与入口

| 路径 | 作用 | 本计划输出 |
| --- | --- | --- |
| `AI_CONTEXT.md` | 3 分钟项目入口 | 当前事实、导航、约束、下一步 |
| `PRD.md` | P1 产品事实源 | 用户、流程、需求、NFR、验收、开放项 |
| `ARCHITECTURE.md` | 目标系统事实源 | 组件、数据流、接口、数据、NFR、边界 |
| `TESTING.md` | 质量事实源 | 当前可运行检查和 P0/P1 目标命令/门槛 |
| `SECURITY.md` | 安全事实源 | 儿童数据、身份、AI、供应链和生产阻塞 |
| `RUNBOOK.md` | 运维事实源 | NOT_DEPLOYED 状态和生产前契约 |
| `TASK.md`/`TODO.md` | 当前执行与队列 | 关闭建档任务，推荐首个 P0 任务 |
| `DECISIONS.md` | ADR 索引 | 明确无已接受 ADR，列优先候选 |
| `CHANGELOG.md` | 已发布变化 | 明确暂无产品发布 |

## 4. 分阶段计划

### Milestone 1 — 证据扫描

结果：确认仓库、Git、DOCX、依赖/入口/测试/CI/部署现状。

- [x] 按 AGENTS 顺序读取所有主文档和 bootstrap Prompt。
- [x] 使用 `rg/find/git` 验证仓库结构和 Git 状态。
- [x] 提取 DOCX 段落/表格并渲染、检查全部 3 页。
- 验证：31 段落、6 表格、3 页；Git `master` 无提交；无代码/清单/CI/部署。

### Milestone 2 — 主文档项目化

结果：产品、架构、质量、安全和运维事实源可审查。

- [x] 更新 `PROJECT.md` 的 Git 现状和文档状态。
- [x] 完成 `PRD.md`、`ARCHITECTURE.md`、`TESTING.md`、`SECURITY.md`、`RUNBOOK.md`。
- [x] 目标架构全部标记为尚未实现，开放阈值保留 `TBD`。
- 验证：逐文档核对设计稿和唯一事实源职责。

### Milestone 3 — 状态与交接

结果：当前任务、计划、决策、队列和变更状态一致。

- [x] 刷新 `AI_CONTEXT.md`、`TASK.md`、`TODO.md`、`DECISIONS.md`、`CHANGELOG.md`。
- [x] 推荐 `TODO-001` 为首个 P0 任务并限制范围。
- [x] 运行占位符、表格、引用、敏感信息和工作区检查。
- [x] 填写 Closeout，将 TASK/PLAN/AI_CONTEXT 状态改为完成。

## 5. Progress

- `2026-07-12 14:36 CST` — `[done]` 完成仓库与 DOCX 扫描；发现 Git 已初始化但无提交，所有文件未跟踪。
- `2026-07-12` — `[done]` 完成 PRD、架构、测试、安全、Runbook 项目化。
- `2026-07-12` — `[done]` 刷新状态文档；13 份上下文、32 个表格结构检查 0 错误，引用和敏感信息检查通过。

## 6. Surprises & Discoveries

- `2026-07-12` — 发现：相较上一轮，目录现已是 Git 仓库，但 `master` 无 commit；证据：`git status --short` 和 `git log`；影响：更新 `PROJECT.md`，同时强调 Git 无法恢复未跟踪文件。
- `2026-07-12` — 发现：设计稿在当前 LibreOffice 环境渲染中文缺字，但 OOXML 文本/表格完整；证据：DOCX 提取与 3 页 PNG；影响：产品/架构事实可读取，视觉发布需 `TODO-006`。
- `2026-07-12` — 发现：无任何业务代码、依赖、配置、迁移、测试、CI 或部署；证据：全文件扫描；影响：所有工程命令只能作为 P0 验收目标，不能报告通过。

## 7. Decision Log

- `2026-07-12` — 决定：不创建业务脚手架；原因：bootstrap Prompt 明确只建档；替代方案：同时初始化代码会扩大范围；ADR：否。
- `2026-07-12` — 决定：把 v1.0 设计写成 Draft/目标架构，不标为已实现或已接受 ADR；原因：无代码、无具名批准/权衡；ADR：后续需要，见 `DECISIONS.md`。
- `2026-07-12` — 决定：未知性能、合规、保留、Provider 和运维数值保留带 Owner/截止条件的 `TBD`；原因：缺少测量和授权；ADR：部分需要。

## 8. 验证与验收

```bash
rg -n '\{\{|\}\}' AGENTS.md AI_CONTEXT.md ARCHITECTURE.md CHANGELOG.md DECISIONS.md PLANS.md PRD.md PROJECT.md RUNBOOK.md SECURITY.md TASK.md TESTING.md TODO.md
git status --short
git diff --check
```

- [x] 非模板上下文无双花括号模板占位符，Markdown 表格列数和引用正确。
- [x] 常见密钥/凭据模式无命中，工作区无意外生成物。
- [x] `TASK.md`、本计划和 `AI_CONTEXT.md` 完成状态一致。
- [x] 最终汇报列出冲突、未知、风险、建议 ADR/TODO 和首个任务。

## 9. 回滚与恢复

- 可逆步骤：所有变更仅为 Markdown，可按文件回退。
- 不可逆步骤：无；未提交、未部署、未改 DOCX。
- 回滚流程：由于无基线 commit，只能使用编辑器本地历史或会话前内容逐文件恢复；不要用 `git clean` 删除未跟踪文件。
- 数据恢复：不适用；仓库没有业务数据。

## 10. Closeout

- 实际结果：所有根目录上下文主文档已项目化，目标/现状/开放决策分离；`AI_CONTEXT.md` 可作为下一会话入口，`TODO-001` 可转为首个 P0 任务。
- 与原计划的差异：发现 Git 已初始化而非完全无仓库；其余按 bootstrap 范围执行。
- 未解决事项：Owner、远程/许可证、版本/工具链、法域/保留、身份/Provider、SLO/RPO/RTO 和生产平台。
- 经验：在零代码阶段，最重要的是区分已验证现状、目标设计和待批准决策；工程命令不能凭技术栈推断为已可用。

---

# PLANS.md — PLAN-0002 P0 仓库骨架与质量门槛

## 计划元数据

- 计划 ID：`PLAN-0002`
- 关联任务：`TASK-0002`
- 状态：`COMPLETE`
- Owner：Codex（执行）；项目/技术 Owner `TBD`
- 创建/更新：`2026-07-12`

## 目标与边界

建立 `TODO-001` 所需的 contracts、API、Web、Flutter、evals、Compose 和 CI 最小边界，生成唯一锁文件并运行可用的质量命令。只建立健康端点和空壳消费者，不进入家庭业务、身份、迁移、离线同步、AI Provider 或真实数据。

## 阶段

- [x] 1. 读取上下文和设计基线，确认 `TODO-001` 是用户“开始开发”对应的最小首项。
- [x] 2. 写入目标目录、入口、合同、Compose、CI、忽略规则和脱敏环境样例。
- [x] 3. 使用批准/可用的 uv、pnpm、Flutter 工具链生成三类锁文件并修正解析版本。
- [x] 4. 运行 API/Web/Flutter/Compose 验证，补齐 `TESTING.md` 的实际状态；原生平台构建阻塞原因已记录。
- [x] 5. 工作区和安全审查，更新 `TASK.md`、`AI_CONTEXT.md`、`TODO.md`、ADR 与变更记录。

## 关键假设与阻塞

- 版本基线暂记录在 `docs/adr/0007-toolchain-and-scaffold-baseline.md`，状态为 Proposed，不等同于 Owner 批准。
- API/Web/Flutter 依赖已解析；Flutter 原生构建仍依赖本机 Android SDK、完整 Xcode 和 CocoaPods。
- Docker CLI 可用，但 Compose 启动会创建本地服务；在确认配置无外部连接且完成静态检查前不自动启动持久化服务。

## 回滚

本计划只产生未提交的本地文件。回滚时逐文件恢复本轮改动，不使用 `git clean`、强制 checkout 或删除用户未知文件。

## Closeout

- `TASK-0002` 和 `TODO-001` 已完成；P0 代码、锁文件、验证入口和文档状态一致。
- 原生平台构建保留为环境前置项，不扩大任务范围安装 Android Studio、Xcode 或 CocoaPods。

---

# PLANS.md — PLAN-0003 家庭/孩子/设备首个纵向切片

## 计划元数据

- 计划 ID：`PLAN-0003`
- 关联任务：`TASK-0003`
- 状态：`COMPLETE`
- Owner：Codex（执行）；产品/技术 Owner `TBD`
- 创建/更新：`2026-07-12`

## 阶段

- [x] 1. 读取 PRD/架构/安全边界，确认只做合成数据和 local/CI demo 主体。
- [x] 2. 建立 OpenAPI children/devices 增量和 Proposed 契约 ADR。
- [x] 3. 建立 API domain/repository/auth adapter/routes，并覆盖家庭隔离、角色和幂等。
- [x] 4. 补充 Web/Flutter 的契约入口，不复制手工领域模型。
- [x] 5. 运行质量门槛、更新文档并完成回滚/残余风险记录。

## 不变量

- Household 是每个资源的授权边界；跨 Household 访问返回 404。
- Demo principal 仅是测试适配器，不能被描述为真实认证。
- 内存仓储仅用于合成 vertical slice，不替代 PostgreSQL 事实源。
- 所有写接口带 `Idempotency-Key`，重复请求不产生重复副作用。

## Closeout

- `TASK-0003` 和 `TODO-003` 已完成；API、契约、Web/Flutter 合成消费入口和验证记录已同步。
- 真实认证、PostgreSQL 持久化和 SDK 生成器继续由后续 ADR/任务决定。

---

# PLANS.md — PLAN-0004 核心 ADR 起草与审批准备

## 计划元数据

- 计划 ID：`PLAN-0004`
- 关联任务：`TASK-0004` / `TODO-002`
- 状态：`COMPLETE`
- Owner：Codex（起草）；项目/技术/安全/产品/法务/运维 Owner `TBD`（审批）
- 创建/更新：`2026-07-12`

## 目标与边界

为八项核心决策建立可审批 ADR，并同步主文档。ADR 只起草为 `Proposed`；本计划不指定具名 Owner、不批准真实数据/Provider/部署，也不实现后续业务任务。

## 阶段

- [x] 1. 复读项目、架构、产品、安全、测试、Runbook、决策和当前任务，确认 TODO-002 的依赖与审批边界。
- [x] 2. 使用 `/usr/local/flutter/bin/flutter` 复核迁移后的 SDK；记录 iOS/Android 原生构建事实。
- [x] 3. 建立/补齐 ADR-0001 至 ADR-0008，保证模板字段、选项、权衡、迁移与验证完整。
- [x] 4. 同步 DECISIONS、TASK、TODO、AI_CONTEXT、架构/安全/运维/测试事实，运行文档与工作区验证。

## 审批清单

| ADR | 需要的具名审批 |
| --- | --- |
| ADR-0001/0002/0003/0007 | 技术负责人；需要时项目 Owner |
| ADR-0004/0005 | 产品、技术与安全 Owner |
| ADR-0006 | 项目、产品与安全/法务 Owner |
| ADR-0008 | 项目、技术、运维与安全 Owner |

## 回滚

变更仅为 Markdown；逐文件恢复本轮内容即可。不得通过 Git 清理未跟踪文件，也不得把 `Proposed` 自动改为 `Accepted`。

## 当前结果

- 项目 Owner（用户）已于 `2026-07-13` 批准 ADR-0001～0008；所有 ADR 改为 `Accepted`，但其中定义的真实数据、Provider、法域和 staging 前置条件未被解除。
- Flutter 3.44.6 已通过交互式 PATH 验证；Android/iOS 原生构建均已验证，详细结果见 `TESTING.md`。

---

# PLANS.md — PLAN-0005 Task/Session/Attempt 与离线同步基础

## 计划元数据

- 计划 ID：`PLAN-0005`
- 关联任务：`TASK-0005` / `TODO-007`
- 状态：`COMPLETE`
- Owner：Codex（执行）；项目 Owner（用户，ADR 已批准）
- 创建/更新：`2026-07-13`

## 目标与边界

实现数学任务、StudySession、Attempt 和版本化离线同步的第一条安全数据流。先完成契约、领域规则、API 和 Flutter 待同步队列边界；随后在同一任务中接入 PostgreSQL 迁移/持久仓储和集成测试。禁止以进程内状态作为完成声明，禁止接入真实数据、Capture、Tutor 或生产认证。

## 阶段

- [x] 1. 复核 PRD、架构、安全、已接受 ADR、现有 API/合同和工具链，建立活动任务。
- [x] 2. 在 `packages/contracts` 定义 Task/Session/Attempt/SyncBatch 的向后兼容合同与 Schema 版本。
- [x] 3. 在 API 的 Plan/Task/Session 模块实现授权、状态机、追加 Attempt、事件幂等与冲突结果，并写正反向测试。
- [x] 4. 建立 Flutter 待同步队列边界和最小测试；公共模型仍以合同生成策略为目标，避免复制完整领域语义。
- [x] 5. ADR-0009 已 Accepted；Docker Desktop/local PostgreSQL、依赖锁定、首个 migration 与 downgrade/upgrade 演练已完成；PostgreSQL 仓储、连接池重连、并发版本冲突与回滚/前滚验证通过。
- [x] 6. 审查差异和 synthetic 数据边界，更新测试/架构/任务/上下文并填写完成记录。

## 不变量

- Household 授权优先于资源披露；跨 Household 统一 404。
- Attempt/AuditEvent 追加写；客户端事件、时间和版本均不可信。
- 同键同载荷重放同一结果，同键异载荷冲突；任务状态不用最后写入覆盖。
- local/CI 仅使用 synthetic fixtures；Docker 持久卷只有在检查本地配置后才启动。

## 回滚

新增合同只做兼容性增量。迁移阶段先扩展、再迁移、最后收缩；优先前向修复，绝不通过删除 Attempt、AuditEvent 或客户端队列来恢复。

## Closeout

- `TASK-0005` / `TODO-007` 已完成：`0.3.0` Learning 合同、Household/角色边界、追加 Attempt/Audit、幂等同步队列、Alembic schema 和可选 PostgreSQL 仓储均已交付。
- 验证包含 11 项 API 单元测试、4 项本地 PostgreSQL 集成测试、迁移 downgrade/upgrade、OpenAPI 结构检查和 Flutter 4 项测试；只使用 synthetic 数据。
- 未包含真实认证、Flutter SQLite 持久化、真实设备离线或 staging/production 恢复演练；后续必须以新任务处理。

---

# PLANS.md — PLAN-0006 Capture 与人工校正安全基础

## 计划元数据

- 计划 ID：`PLAN-0006`
- 关联任务：`TASK-0006` / `TODO-008`
- 状态：`COMPLETE`
- Owner：Codex（执行）；项目 Owner（用户，明确授权 TODO-008）
- 创建/更新：`2026-07-13`

## 目标与边界

建立 Capture 的服务端安全数据流：受限媒体声明 → 必须人工校正 → 追加校正事件；已按 ADR-0010～0012 完成本地 MinIO 与本地 PaddleOCR 的 synthetic 安全基础。`2026-07-15` 起目标由 ADR-0015 调整为“本地 PrivacySanitizer → 用户确认脱敏副本 → 单一获批云视觉解析 → 题目人工确认”；现有本地完整 OCR 保留为迁移事实/关闭的回滚能力。真实儿童图片、生产保留/备份和具体云 Provider 仍不在范围内。

## 阶段

- [x] 1. 复核 PRD、架构、安全、测试、已接受 ADR、工作区和现有 Learning 代码，记录文档与代码基线冲突。
- [x] 2. 在 `packages/contracts` 增加向后兼容 Capture/Correction `0.4.0` 合同和结构检查。
- [x] 3. 在 API 建立 Capture 领域模型、child-only 授权路由、内存参考仓储与 PostgreSQL 事务仓储，禁止原始媒体/文本进入审计。
- [x] 4. 新增版本化迁移与 local PostgreSQL 集成测试，覆盖家庭隔离、幂等、校正追加和 downgrade/upgrade；真实多请求并发仍待下一里程碑。
- [x] 5. 已锁定并安装 `boto3==1.43.46`、Pillow `12.3.0`、PaddleOCR `3.7.0`、PaddlePaddle CPU `3.3.1` 与模型清单；私有 MinIO 预签名 Adapter、`0.5.0` 上传签发/服务端确认端点、`0003`～`0006` 对象键/生命周期/OCR Job Ledger 迁移、过期清理器、按 Household/Child 的 Capture 对象级联删除编排、local/CI 家长删除顺序与幂等入口、家长保存/立即删除图片、synthetic PostgreSQL/MinIO 测试、预置模型目录的 OCR Adapter、对象有界读取、图片容器头部校验、完整像素解码/无 EXIF 规范化重编码、PaddleOCR 文本结果纯解析、临时文件执行边界、`0005` OCR 候选结果事务持久化、幂等 OCR 入队/PostgreSQL 行锁队列、固定 `ocr-synthetic-v1` 评测和 linux/amd64 synthetic 真实模型烟测已完成。Redis/外部 Worker 适配、Ubuntu 原生基准/真实题型评测与生产 Profile/派生对象/备份级联仍在后续范围。
- [x] 6. 已执行相关质量门槛、安全审查和文档同步；真实设备、备份/法域和商业 Provider 的未完成项已记录。
- [x] 7. 读取项目 Owner 提供的架构讨论，建立并接受 ADR-0015；同步产品、架构、安全、决策、任务、测试和运维边界，明确旧代码与新目标冲突，本轮不修改代码/合同/迁移。
- [x] 8. 兼容实现里程碑已建立：Provider-neutral 脱敏/图片分析 Schema、PrivacySanitizer synthetic eval、本地检测信号、Flutter 脱敏预览/手动涂抹、旧 Capture 对象 SHA-256 核验、ImageAnalysis ledger/API、无 Provider offline Tutor Policy、Tutor hints API 和固定 Tutor synthetic eval 已完成。
- [x] 9. 自用部署边界已实现：ADR-0016 HMAC Bearer 令牌、Web/Flutter token 注入、OpenAI-compatible NewAPI Adapter、显式 enabled gate、0009 QuestionExtraction 持久化、ImageAnalysis queued worker、stale lease/稳定失败状态和提取读取合同已完成；NewAPI 仍默认关闭。
- [x] 10. 自用 Compose 交付边界已补齐：API/迁移镜像包含 Alembic 与 worker 入口，Compose 编排 PostgreSQL/Redis/MinIO/API/迁移、家长 Web 和默认 ImageAnalysis worker，配置样例与启动/升级/回滚文档已建立；完整启动、真实 NewAPI 联调、备份恢复和生产监控仍未验证。
- [x] 11. 优化本地开发体验：Flutter 首帧后提供有限时长启动过渡并与档案加载并行；ImageAnalysis worker 进入 Compose 默认 profile 且 Provider 关闭时安全空闲；API 镜像移除固定 amd64，验证 Linux/arm64 原生调试构建，同时保留 amd64 Paddle OCR 发布能力。

## Progress

- `2026-07-13` — `[done]` 为 OCR 边界增加 `read_object` 有界读取、声明大小/SHA-256 校验，以及 JPEG/PNG 容器头、尺寸、像素数和 JPEG EXIF 拒绝测试；完整像素解码和 EXIF 清理仍未宣称完成。
- `2026-07-13` — `[done]` 增加 PaddleOCR `rec_texts/rec_scores` 结果纯解析器；结果形状、置信度、控制字符和长度经校验，低置信度和空结果均保留人工确认路径。
- `2026-07-13` — `[done]` 增加本地 OCR 执行边界：安全输入仅写入临时文件供 `predict` 使用，调用结束后清理；引擎错误统一脱敏为 `OcrExecutionError`。
- `2026-07-13` — `[done]` 增加 Pillow `12.3.0` 显式锁定依赖；OCR 前对 JPEG/PNG 执行完整像素解码、EXIF 方向归一化和无元数据重编码，截断/无法解码的像素不会进入 PaddleOCR。linux/amd64 最终镜像无网络 synthetic PNG 烟测通过。
- `2026-07-13` — `[done]` 增加 `0005_ocr_result_persistence`、Provider-neutral 候选草稿和 PostgreSQL 事务仓储；保存候选文本及 Provider/模型/Schema 版本，空结果也保存，强制人工确认，支持幂等重放和 Household/Child 读取隔离，审计不保存候选原文。
- `2026-07-14` — `[done]` 增加 `evals/ocr_synthetic_v1.json` 与无 Provider/无网络的固定 OCR 合同评测 runner；6 个 cases 覆盖正常候选、低置信度、空结果、空行和拒绝路径，结果仅输出聚合摘要。
- `2026-07-14` — `[done]` 增加 `LocalOcrJob` Worker：已确认 Capture 才能进入有界对象读取、图片规范化、本地 OCR 和候选结果持久化；未确认上传、非法图片或 Provider 失败均不落库，Redis/外部 Worker 仍保留在后续范围。
- `2026-07-14` — `[done]` 增加 child-only 幂等 OCR 入队端点、`InMemoryOcrJobQueue`、PostgreSQL Job Ledger 和单次 `LocalOcrDispatcher`；成功只关联结果 ID，失败只记录稳定错误码，新的幂等键可重试，stale lease 可恢复。
- `2026-07-14` — `[done]` 将 OCR 失败接入 ADR-0011 生命周期：从失败发生时设置 `ocr_failure` 七天期限，重复失败不延长，到期清理继续复用现有行锁和可重试删除流程。
- `2026-07-14` — `[done]` 新增 `0006_ocr_job_ledger` 并完成 PostgreSQL 迁移/队列集成回归；完整 API 门槛为 64 项单元、15 项 PostgreSQL/MinIO 集成。
- `2026-07-14` — `[done]` 增加独立一次性 `run_ocr_worker.py` 入口；组装 PostgreSQL Queue、MinIO、预置 PaddleOCR 模型和 `LocalOcrJob`，启动/运行错误只输出稳定状态码。
- `2026-07-14` — `[done]` 增加 child-only OCR 结果读取路由与 `OcrResultWithCandidates` 合同；重新校验 Household/Child/Capture 绑定，候选结果只能进入人工确认流程；定向路由测试覆盖兄弟孩子、家长、跨家庭和 Capture 不匹配。
- `2026-07-14` — `[done]` 增加 child-only OCR 候选确认路由；只提交候选 ID 与 Capture 版本，复用 CaptureCorrection 追加写、版本冲突和幂等事务，OCR 结果保持不可变；PostgreSQL 组合回归覆盖候选确认。
- `2026-07-13` — `[done]` 增加按 Household/Child 边界原子认领 Capture 对象的级联删除编排；对象逐项删除，成功标记 `deleted`，失败标记 `failed` 并可重试，内存单元与 PostgreSQL 集成回归覆盖成功、失败重试、重复运行和错误 Household。
- `2026-07-14` — `[done]` 按客户端原型顺序实现 Flutter 第 1/2/3 张横屏 UI：学习桌、拍题输入页、OCR 题目确认页与分数思考提示页；加入 `image_picker 1.2.3` 相机/相册入口、iOS 权限声明、合成图片、候选文本编辑/确认、两级提示和思考状态交互，6 项 Widget 测试与静态分析通过。含原生插件的无签名 iOS `Runner.app` 已构建并重新安装到实体 iPad，用户已实机确认拍照、权限和“已选择题目照片”页通过。Flutter 不支持实体设备截图，目标 landscape QA 仍待 Xcode 设备查看器或手动截图。
- `2026-07-14` — `[done]` 增加 Flutter `CaptureApiClient`：使用 `crypto 3.0.7` 计算 SHA-256，按服务端合同完成预签名 PUT、确认和 OCR 幂等入队；本地 HTTP 合同测试覆盖请求顺序、图片头、上传字节和稳定幂等边界，Flutter 总测试数增至 8。真实设备接线仍等待有效 StudySession 和 iPad 可达的 MinIO 预签名地址。
- `2026-07-14` — `[done]` 将 `CaptureApiClient` 接入显式 `STUDY_CAPTURE_SESSION_ID` 调试开关；真实上传后页面只显示私有上传完成和 OCR 排队状态，不把合成候选当作真实结果。使用合成 StudySession 和 iPad 可达 MinIO 完成实体 smoke test，API 日志确认上传/确认/入队为 201/201/202。
- `2026-07-14` — `[done]` 增加 child-only OCR Job 状态读取路由和 OpenAPI 路径；Flutter 客户端可解析稳定 Job 状态和 `result_id`，跨孩子边界回归通过。
- `2026-07-14` — `[done]` Flutter 确认页接入有界 OCR Job 轮询、`result_id` 候选读取、人工确认和手工纠正；候选返回前保持等待，候选返回后不自动代答。客户端 HTTP 合同测试增至 3 项，Flutter 总测试数增至 9。
- `2026-07-14` — `[done]` 增加显式 local durable mode：API 的 Learning/Capture、OCR Job 和结果仓储可统一使用 PostgreSQL；Worker 增加可选 `--watch` 轮询模式，默认一次性命令保持不变。Ruff、Mypy、74 项 API 非集成测试和 `git diff --check` 通过。
- `2026-07-14` — `[done]` 完成 PostgreSQL/MinIO synthetic API + Worker 闭环回归：真实走签名对象上传、Job Ledger 领取/完成、`LocalOcrJob` 安全读取/规范化、候选结果持久化和 child-only 读取；Provider 使用 synthetic adapter，完整集成回归 17 项通过并清理对象。
- `2026-07-14` — `[done]` 增加 Ubuntu 24.04 CPU 真实模型评测预检；只检查 Linux/Ubuntu 24.04、x86_64、Python 3.12、Paddle 锁定版本和五个 SHA-256 模型目录，不读取图片、不下载模型。macOS 预检按预期阻塞。
- `2026-07-14` — `[done]` 增加 `ocr-model-synthetic-v1` 锁定模型 smoke runner；只在预检通过后生成内存 synthetic 数学题图、调用 PP-OCRv6 medium CPU Adapter，并输出 case 状态/延迟聚合，不接受图片路径或输出 OCR 原文。当前 macOS 预检阻塞，真实推理仍待 Ubuntu 环境。
- `2026-07-14` — `[done]` 优化 `LocalPaddleOcrAdapter` 的实例级引擎缓存：文本/公式引擎按需只初始化一次，重复使用前仍执行模型目录和 SHA-256 标记校验；新增复用回归测试，避免持久化 Worker 按图片重复加载模型。
- `2026-07-15` — `[done]` 补齐 `PP-FormulaNet_plus-M` 按需执行和 `rec_formula` 解析，公式无 Provider 置信度时固定走低置信度人工确认；锁定模型 smoke fixture 增加公式 case，真实推理继续受 Ubuntu 24.04 CPU 预检门禁保护。
- `2026-07-15` — `[done]` 将 OCR mode 以向后兼容的 `text` 默认值贯穿 OpenAPI、Flutter Capture 客户端、内存/PostgreSQL Job Ledger 和 Worker；新增 `0007_ocr_job_mode`、模式幂等冲突保护及普通/公式分流回归，旧客户端不发送请求体时行为不变。
- `2026-07-15` — `[done]` 完成 `0007_ocr_job_mode` 的本地 synthetic PostgreSQL downgrade/upgrade 往返验证；固定 `ocr-synthetic-v1` 评测 6/6 通过，当前 macOS 的真实模型 smoke 按预检稳定阻塞，未执行真实推理。
- `2026-07-15` — `[done]` 项目 Owner 将 OCR 定位改为本地脱敏、云端多模态解析；新增 ADR-0015 并将 ADR-0012 标记为被替代。为避免静默改写已实现行为，旧 OpenAPI/迁移/Worker/Flutter OCR 路线保持兼容。
- `2026-07-15` — `[done]` 新增 Provider-neutral PrivacySanitization/ImageAnalysisJob/QuestionExtraction/VerifiedQuestion Schema；实现本地 PrivacySanitizer 元数据清除、检测区域实色覆盖、不可逆重编码和不安全信号阻断，接入 OCR/规则敏感区域信号，6-case synthetic eval 通过。
- `2026-07-15` — `[done]` Flutter 拍题路径新增本地脱敏预览、手动涂抹、确认后不可逆 PNG 与 SHA-256；上传客户端只接收确认后的脱敏字节。Widget/analyze 通过，真实 iPad 渲染和手动涂抹仍需人工回归。
- `2026-07-15` — `[done]` Capture 上传确认新增私有对象实际 SHA-256 核验；对象存储、上传路由和 MinIO/PostgreSQL 集成回归通过，错误哈希会阻断状态推进。
- `2026-07-15` — `[done]` 新增 0008 receipt-only ImageAnalysis ledger/API；服务端绑定 Capture 版本和脱敏副本哈希，Provider 未启用时返回 `blocked/provider_not_enabled`，Flutter 新上传路径不再误启动旧 OCR。
- `2026-07-15` — `[done]` 完成 0008 receipt/API 到 queued/blocked 双态迁移，并新增 0009 QuestionExtraction 记录、PostgreSQL claim/complete/fail worker、失败稳定错误码和手工 review 读取路径；未确认提取不进入 Tutor。
- `2026-07-15` — `[done]` 新增无 Provider 的 `offline-tutor-policy.v1` 和 `tutor-hint.v1` Schema；固定输出 1～3 级提示、要求孩子回应、`direct_answer: null` 和 0 元成本，3-case synthetic eval 通过；Flutter 思考页同步支持第 3 级提示。
- `2026-07-15` — `[done]` 补齐自用 Compose 全栈部署：新增 `migrate`、API、家长 Web 和默认 ImageAnalysis worker，API 镜像复制迁移/脚本入口并保留构建期模型 SHA-256 门禁；新增 Web standalone Dockerfile、健康端点、`.env.example`、自动读取的 `.env` 与部署/升级/回滚说明。Compose 默认服务展开、Web 镜像构建和 Web 质量门槛通过，完整容器启动仍待本机执行。
- `2026-07-15` — `[done]` 按项目 Owner 的本机调试需求增加 Flutter 1.2 秒启动过渡（首页并行加载、减少动态效果时跳过）、将 ImageAnalysis worker 移入默认 Compose profile 并在 Provider 关闭时安全空闲；API 镜像改为宿主架构原生构建。Linux/arm64 无本地 Paddle OCR/模型/专用系统库的调试镜像已构建，amd64 继续保留锁定模型与旧 OCR 回滚能力。
- `2026-07-16` — `[done]` TASK-0006 代码闭环完成：人工确认接口生成 VerifiedQuestion，worker 成功/失败分支清理派生对象；synthetic NewAPI 联调、iPad 真实脱敏预览回归、备份级联和生产监控转为环境验收项。

## 不变量

- Capture 属于 Household、孩子和 StudySession；跨 Household 或未绑定孩子统一返回 404。
- 新 Capture 在 PrivacySanitizer/云视觉 Provider 未获准或不可用时必须保留重新裁剪、手工涂抹/录入和 `needs_correction` 路径；不得伪造可信解析结果或发送原图。
- 原始媒体、对象键、签名 URL、完整题目和校正文本不得进入审计、错误响应、日志或测试输出。
- 原图、对象键、签名 URL 和敏感 OCR 文本不得发送给云端；未通过安全门禁/用户确认的脱敏副本不得外发，同一图片不得自动广播给多个 Provider。
- Correction 追加写；同键同载荷重放原结果，同键异载荷冲突；派生版本由服务端控制。

## 回滚

保持 OpenAPI 兼容增量。发生安全问题时关闭云视觉/图片外发开关并降级为重新裁剪或手工录入；可显式启用已验证本地 OCR 作为不外发回滚 Provider，但不得重解释历史记录、发送原图、恢复已删除副本或删除校正/审计记录。

---

# PLANS.md — PLAN-0011 P1 核心闭环全仓收口

## 计划元数据

- 计划 ID：`PLAN-0011`
- 关联任务：`TASK-0009`、`TODO-009`、`TODO-010`、`PLAN-0007`、`PLAN-0008`、`PLAN-0010`
- 状态：`COMPLETE（非实体设备范围已全部交付并验证）`
- Owner：Codex（执行）；项目 Owner（用户，要求不依赖实体手机继续全仓完善）
- 创建/更新：`2026-07-17`

## 目标与边界

以当前可运行代码和测试为事实，对照 P1 PRD 收口不依赖实体设备的生产链路。优先修复会让客户端展示成功但业务事实未落库、让客户端提交可伪造事实、或在进程退出后丢失队列的缺口；随后补齐可自动运行的部署、恢复和核心 E2E 门槛。实体 iPad/iPhone/Nova 9 只保留最后的权限、横竖屏、弱网和真实拍题人工验收，不阻塞代码与 synthetic 自动验收。

## 阶段

- [x] 1. 全仓盘点 PRD、契约、迁移、客户端入口、部署和测试，区分已实现、只有骨架和未实现。
- [x] 2. 收紧 VerifiedQuestion → Tutor 信任边界：Tutor 只按服务端 ID 读取人工确认事实，并持久化可追溯 TutorTurn/提示级别和幂等结果。
- [x] 3. Flutter 将真实拍题确认结果接入 Tutor；移除生产路径硬编码题目/提示，补齐加载、失败、重试和无网络状态。
- [x] 4. 将端侧待同步 Attempt 队列改为 SQLite 持久化，实现进程重启恢复、有界批次、幂等确认和失败保留。
- [x] 5. 补齐任务完成、错题/复习、家长周报和家庭导出/删除的最小可追溯服务端/家长端闭环；不接入未批准内容或通知 Provider。
- [x] 6. 增加云视觉固定 synthetic eval、真实 NewAPI 合成大图验收、PostgreSQL/MinIO 备份恢复脚本和无密钥日志检查。
- [x] 7. 运行 API/Web/Flutter/契约/迁移/Compose 质量门槛，部署 Ubuntu并执行不读取真实题目内容的 synthetic smoke；同步 TASK/TESTING/RUNBOOK/CHANGELOG/AI_CONTEXT。

## 完成记录

- OpenAPI 前滚至 `0.8.0`，数据库前滚至 `0015_child_data_export`；新增追加写 `TutorTurn`、学习会话完成/复习状态、周报聚合、24 小时家庭数据导出快照和端到端级联删除。
- Flutter 生产首页改为读取真实任务/活动会话，拍题确认后只按 VerifiedQuestion ID 请求 Tutor；待同步 Attempt 使用按服务端/账号隔离的 SQLite 队列，同日新拍题不再错误复用已完成会话。
- 离线存储锁定 `sqflite 2.4.3`/`sqflite_common_ffi 2.4.2`（BSD-3-Clause、持续维护的 Flutter SQLite 插件）：只存结构化待同步事件，无服务端成本；相较 Drift 避免额外代码生成，相较键值库保留事务/查询语义。供应链与体积影响是新增 SQLite 原生插件和 iOS CocoaPods 集成，已由锁文件、两端 release 构建和重启恢复测试约束。
- Ubuntu Compose 已重建 API/Web/ImageAnalysis/DataLifecycle worker；健康版本 `0.8.0`，真实 NewAPI 仅用内存 synthetic 大图完成压缩、单 Provider、Extraction、人工确认、TutorTurn 和派生对象删除链路。
- 已生成 PostgreSQL custom dump 与 MinIO 快照并在隔离 PostgreSQL 16.10 容器恢复校验；自动生命周期 worker 已部署。实体设备相机、权限、横竖屏、弱网和重启仍按计划边界留作设备可用时人工验收。

## 不变量与回滚

- 客户端不能把自带的 VerifiedQuestion 当作 Tutor 事实；服务端必须按 Household、绑定孩子和持久化 ID 读取。
- Attempt、TutorTurn、错题依据和审计保持追加写；重试不得覆盖历史或制造重复副作用。
- 离线队列只保存必要结构化摘要，不保存图片、密码、会话或 Provider 原始响应；更换服务端/退出账号时按账号作用域隔离。
- 所有 AI/视觉自动验收只使用仓库生成的 synthetic 输入；真实儿童图片、题目原文、对象键和凭据不得进入输出或测试产物。
- 数据库变更只做向前兼容迁移；回滚应用时保留新增表和历史记录，优先前向修复，不以删库/清卷回滚。

---

# PLANS.md — PLAN-0007 自用账号密码与孩子账号管理

## 计划元数据

- 计划 ID：`PLAN-0007`
- 关联任务：`TODO-012` / `ADR-0017`；进入执行时建立 `TASK-0007`
- 状态：`IN_PROGRESS`
- 优先级：`P0（下一优先级）`
- Owner：Codex（执行）；项目 Owner（用户，方案批准）
- 创建/更新：`2026-07-16`

## 目标与边界

用 PostgreSQL 本地账号密码和可撤销不透明会话替换当前自用 HMAC 家庭 Token。家长 Web 提供登录、首次强制改密和孩子账号管理；Flutter 孩子端使用孩子账号登录并把会话保存在系统安全存储。保持单 Household 自用，不接入短信、邮箱、社交登录、OIDC 或 MFA。

本计划涉及 `services/api`、`packages/contracts`、`apps/web`、`apps/child_flutter`、数据库迁移和 `infra/compose`，必须分里程碑验收。`TASK-0006` 的代码闭环已完成，本计划按用户授权自动进入 `IN_PROGRESS`。

## 产品与安全不变量

- `admin/admin123456` 只在账号表为空时创建，是公开的一次性引导凭据，不是长期默认密码。
- 默认凭据有效时只允许本机引导；登录后只能改密/退出，所有家庭数据和管理 API 均返回 `password_change_required`。
- 密码只存 Argon2id 哈希；原始会话只交付客户端一次，服务端只存摘要。密码、哈希、会话、Cookie 不进入日志、错误、审计正文、测试夹具或客户端构建产物。
- Household 和角色授权仍在每个资源上服务端执行；孩子账号只能绑定同 Household 的一个 ChildProfile，跨 Household 继续统一 404。
- Web 使用 HttpOnly Cookie + CSRF；Flutter 使用 Keychain/Android Keystore。不得继续用 `STUDY_API_TOKEN` 或 `--dart-define` 注入长期凭据。
- 禁用账号、改密、管理员重置和退出必须撤销相应会话；恢复命令只能从服务器本机执行并审计。

## 实施阶段

- [x] 1. 契约与依赖评审：OpenAPI 已增加认证与账号管理合同；锁定 `argon2-cffi==25.1.0` 和 Flutter `flutter_secure_storage==9.2.4`，用途、替代和供应链影响已记录。
- [x] 2. 数据库与领域：新增 `0011_account_password_session`（因 `0010` 已用于 VerifiedQuestion），建立 Account/AuthSession、唯一约束、索引、并发空表初始化和兼容迁移边界。
- [x] 3. API 认证核心：已实现 Argon2id、统一登录错误、5 次失败/15 分钟锁定、256 bit 不透明会话摘要、30 天到期、退出/撤销、改密/禁用/重置联动、孩子账号管理的当前密码再验证和 Household/角色/ChildProfile 反向授权；认证生命周期已写入现有 `audit_events`，只保存稳定事件名与资源 UUID。
- [x] 4. 安全初始化：空账号库事务创建 `admin/admin123456`，设置 `must_change_password`；回环限制、改密前数据阻断和改密后会话轮换已实现并测试。
- [x] 5. 家长 Web：已增加 `/login`、首次改密、退出、账号列表、孩子账号创建/启停/重置；使用 HttpOnly/SameSite Cookie、CSRF 和服务端路由保护，孩子账号管理操作要求当前家长密码再验证。
- [x] 6. 孩子 Flutter：已增加用户名/密码登录，并使用 `flutter_secure_storage` 保存会话；Capture API 使用会话 Bearer。真实 iPad 生命周期/重启验证待执行。
- [x] 7. Compose 与迁移切换：Compose 已启用 password/postgres 认证和 Cookie 配置；随 TASK-0007 删除 auth mode、HMAC/Demo 兼容、静态 Web token 和 Web auth-required 开关。
- [ ] 8. 完整质量门槛：API/Web/Flutter 本地质量门槛、OpenAPI/Schema 解析和 18 项 PostgreSQL/MinIO 集成已通过；迁移 downgrade/upgrade 往返、浏览器 E2E、真实设备登录/退出、备份恢复和正式敏感信息扫描仍待执行。

## 验收标准

- [ ] 全新 Compose 在账号表为空时只创建一个 `admin`；使用临时密码登录后，在改密前无法读取任何 Household/孩子/学习/图片数据。
- [ ] 改密后临时密码和所有引导会话失效；数据库、日志和浏览器/客户端产物中没有明文密码或原始会话。
- [ ] 家长可以创建、查看状态、禁用/启用和重置同家庭孩子账号；不能查看既有密码，不能绑定其他家庭 ChildProfile。
- [ ] 孩子可以登录自己的 Flutter 学习桌，只能访问绑定孩子；兄弟孩子、家长 API、跨家庭和枚举 ID 均被拒绝。
- [ ] Web Cookie、CSRF、会话到期/撤销、失败锁定、退出、改密、账号禁用和管理员恢复均有正反向测试。
- [x] Compose 已移除 `STUDY_API_TOKEN`/长期 token 配置，Flutter 已移除长期 token 构建注入；TASK-0007 已删除 HMAC 签发脚本、Demo Header 和所有兼容开关。

## 发布与回滚

发布切换已完成：扩展数据库/合同、切换 Web/Flutter、再删除旧 HMAC/Demo。出现登录或授权问题时优先前向修复；回滚到含旧认证路径的版本需项目 Owner 单独批准并限于隔离环境。账号/会话表和审计保持不删，不得清空家庭数据或重写学习记录。

## 剩余风险

- 公开默认密码存在抢先登录风险，必须依赖回环引导和改密前数据阻断；如果未来要求开箱即用的局域网首次登录，应改为随机一次性密码/安装码并另行批准。
- 无邮箱/短信/MFA 时，家长忘记密码只能使用本机恢复命令；服务器主机权限等同于家庭管理员权限。
- 单家庭方案不解决公网多租户注册、账号恢复和身份合规；范围扩展必须新建 ADR。

## 2026-07-16 执行记录

- `[done]` TASK-0006 已完成代码闭环，PLAN-0007 自动启动。
- `[done]` API/Web/Flutter/Compose 认证主链路已实现；新增账号绑定反向校验和家长重置密码入口。
- `[done]` 认证生命周期审计已接入内存与 PostgreSQL 账号仓储：成功/失败/锁定/阻断登录、改密失败/成功、再认证失败、登出、孩子账号创建、启停和重置均只写稳定事件名、Household/资源 UUID 和时间；认证回归、Ruff、Mypy 通过。
- `[done]` TASK-0007 已完成唯一密码认证和 Flutter 登录前服务端地址配置；API 122 项非集成/18 项 PostgreSQL-MinIO 集成、OpenAPI/Schema、Web 与 Flutter 本地质量门槛通过。
- `[pending]` 仍需在 Compose、浏览器和 iPad 上完成迁移往返、Cookie/CSRF、真实登录退出与设备重启验收；未执行项不能报告为通过。

---

# PLANS.md — PLAN-0008 Ubuntu x86_64 与自托管 NewAPI 环境验收

## 计划元数据

- 计划 ID：`PLAN-0008`
- 关联任务：`TASK-0006`、`PLAN-0007`、`TODO-008`、`TODO-012`、`ADR-0015`、`ADR-0016`、`ADR-0017`
- 状态：`IN_PROGRESS`
- Owner：Codex（执行）；项目 Owner（用户，Ubuntu/NewAPI 已提供）
- 创建/更新：`2026-07-16`

## 范围与安全边界

在用户提供的 Ubuntu VM `192.168.1.4:22`、账号 `syin`、`x86_64` 环境验证自托管 Compose、锁定模型构建和 NewAPI OpenAI-compatible Adapter。只使用 synthetic 图片和 synthetic 题目；真实儿童图片、真实学习记录和原始 Provider 响应不得上传、写入日志或进入仓库。NewAPI 只接受用户确认且哈希绑定的脱敏副本，失败不得切换 Provider。

`2026-07-16` 项目 Owner 进一步明确：运行时只保留“用户名+密码→可撤销会话”一种认证方式，删除 HMAC、Demo Header 和 Web 免登录开关；Flutter 必须在提交登录前允许验证、保存和更换服务端地址，地址变更时不得复用旧服务端会话。该收敛作为继续环境验收的前置增量，不扩大到短信、邮箱、MFA 或设备绑定。

## 阶段

- [x] 1. SSH、架构、Python 3.12、磁盘和 Docker 前置检查。
- [x] 2. 安装 Ubuntu 官方 Docker Engine/Compose v2，启用 daemon，并加入 `syin` 的 docker 用户组。
- [x] 3. 传输脱敏工作区、生成远程 `.env`、运行 Compose config 和 Alembic `0011` 前滚迁移。
- [x] 4. 构建 Linux x86_64 API/Web 镜像，确认五份模型构建期 SHA-256 校验和运行时不自动下载；容器预检已增加显式锁定 Debian 13 运行层选项，其他版本/架构/模型门禁仍保持严格。
- [ ] 5. 启动 PostgreSQL/Redis/MinIO/API/Web/worker，验证健康、账号首次改密、Cookie/CSRF 和孩子账号授权（Compose 健康、迁移和 LAN bootstrap login 已通过；Nova 9 已恢复真实孩子会话并进入首次改密页，提交新密码后的档案读取、Cookie/CSRF 和完整设备生命周期待验收）。
- [x] 5a. 在再次部署前收敛认证面：已删除 API HMAC/Demo 路径、旧签发脚本与相关配置，OpenAPI 和 Web/Flutter 只使用密码登录后的 Cookie/Bearer Session；Flutter 登录页已提供持久化服务端地址配置，并覆盖地址验证与跨服务端会话清理测试。
- [ ] 6. 使用 synthetic 脱敏图片配置 NewAPI 视觉模型，执行单 Provider `queued → extraction → VerifiedQuestion` 联调；不发送真实数据。`queued → extraction` 已通过；远端以家长/孩子会话调用人工确认生成 `VerifiedQuestion` 仍待验收。
- [x] 7. 做停止/重启、迁移、worker 失败清理和日志敏感信息审查；新增稳定 Provider 错误码和可清理 live eval，并同步任务/测试/安全/运行文档。

## 当前进度（2026-07-17）

- Ubuntu 宿主确认 `Ubuntu 24.04 LTS`、`x86_64`、Python `3.12.3`；Docker `29.1.3`、Compose `2.40.3` 已安装。按项目 Owner 要求关闭该 VM IPv6，并为 Docker daemon 配置 `socks5://192.168.1.100:7893` 出网代理。
- `/home/syin/study` 只接收排除 `.git`、依赖缓存、构建产物、`.env` 和图片的工作区；远端 `.env` 权限为 `600`，数据库/MinIO 密码由远端随机生成，NewAPI URL、Key 和 `gemini-3.1-flash-lite` 已配置并启用；Key 未写入仓库或输出。
- Compose 已在远端启动并重启恢复：PostgreSQL、Redis、MinIO、API、Web、迁移和 worker 均正常；API/Web `/healthz`、`0011` 迁移、loopback bootstrap login、模型预置目录、无网络运行时模型路径和内存 synthetic OCR smoke 已验证。Cloudflare 曾以 1010 拦截 Python `urllib` 默认 User-Agent；Adapter 改用受控的 `study-api/0.5` 后，synthetic NewAPI live eval 已成功完成 `queued → extraction`，返回 `needs_confirmation=true`，派生副本已删除且数据库残留 Job 为 0。未发送真实图片或输出原始 Provider 响应。
- 本次发现并修复 API Docker 构建上下文的 Python 缓存与 macOS AppleDouble 元数据排除，避免 Alembic 将 `*.pyc`/`._*.py` 当迁移脚本扫描。
- 已修复 OCR 预检无法识别自身锁定 Debian 13 镜像层的问题：宿主仍要求 Ubuntu 24.04，只有镜像声明的 `STUDY_OCR_CONTAINER_RUNTIME=true` 才允许 Debian 13；远端重建后预检 `ready`，完整 4-case synthetic OCR eval 通过。
- TASK-0007 认证收敛已在本地完成：OpenAPI `0.6.0`、API/Web/Flutter/Compose 只保留密码登录后的 Cookie/Bearer Session，Flutter 可在登录前配置服务端地址。API 122 项非集成/18 项 PostgreSQL-MinIO 集成、Web 完整质量命令和 Flutter 17 项测试通过；远端栈尚未用该增量重新部署。
- 2026-07-17：为华为 Nova 9 Android 调试复核 Flutter 3.44.6、Android SDK 36.1.0/JDK 21 和全部许可证，Flutter analyze/17 项测试及 176 MB Debug APK 构建通过。Nova 9（Android 12）现已由 ADB 识别，Debug APK 已通过 Flutter tooling 安装并在前台运行；设备至 Ubuntu API `192.168.1.4` 的局域网 ICMP 连通约 32 ms。待继续执行登录、相机/相册、脱敏预览、弱网和会话生命周期的人工交互验收。
- 2026-07-17：项目 Owner 授权移除引导家长账号的 loopback 登录限制，仅保留受信 LAN 首次改密用途、改密前数据阻断和既有锁定/会话/授权保护。Ubuntu 远端副本最初只有部分 API 文件更新，造成领域模型版本不一致并使新 API 容器重启；完整同步 `services/api` 运行目录和构建清单后重建成功，API healthy，`/healthz` 返回 `0.6.0`，容器内 LAN 引导登录回归通过。未调用远端真实账号或数据库做首次改密。
- 2026-07-17：定位 Nova 9 登录后“API 尚未连接”为孩子账号 `must_change_password` 被 API 正确阻断、Flutter 却丢弃该标志。Flutter 新增登录响应/`/auth/me` 恢复、首次改密 UI、会话轮换和安全存储；API 档案列表/详情只允许孩子读取绑定档案。API 129 项非集成/22 项集成、Flutter analyze/21 项测试和 Debug APK 通过；Ubuntu API 重建健康，实机完成改密与档案读取并显示在线学习桌，竖屏溢出修复后再次覆盖安装和截图验证。
- 2026-07-17：家长 Web 创建孩子账号时，中文用户名被拼入 `Idempotency-Key` Header，浏览器因 Header 非 ISO-8859-1 而在请求前阻断。Web 改为 ASCII 随机幂等键，并让账户页自动加载/绑定首个家庭孩子档案，多个档案可选择，不再要求家长手输 UUID。4 项 Web 单测、格式、Lint、类型和生产构建均通过；完整 Web 运行目录已同步并部署到 Ubuntu，Web/API 健康检查通过。
- 2026-07-17：补齐家长 Web 孩子档案新增、编辑和删除入口；新增/编辑代理此前遗漏 JSON `Content-Type`，导致 FastAPI 在解析请求体前返回 422，现已显式转发 `application/json` 并增加 POST/PATCH 回归测试。Web 镜像已重新部署到 Ubuntu，Web/API 容器与健康端点均正常；远端无会话 POST/PATCH smoke 均返回预期 401 而非 422，未写入数据。当前 Profile 仓储仍为进程内 synthetic 实现，API 重启后档案改动不会保留，持久化到 PostgreSQL 仍是后续工作。

## 回滚

只删除本次在 `/home/syin/study` 创建的部署目录和 Compose 项目（需用户明确授权后执行）；不删除 Docker Engine、系统包、其他容器或远程用户数据。NewAPI 异常时保持 `STUDY_NEWAPI_ENABLED=false` 并停止 worker，数据库迁移优先前向修复；Cloudflare 1010 的应用侧兼容修复只设置受限 User-Agent，不修改或绕过网关安全策略。

---

# PLANS.md — PLAN-0009 孩子档案 PostgreSQL 持久化

## 计划元数据

- 计划 ID：`PLAN-0009`
- 关联任务：`TASK-0008`、`PLAN-0008`、`ADR-0005`、`ADR-0009`、`ADR-0017`
- 状态：`COMPLETE（华为登录生命周期继续由 PLAN-0008 验收）`
- Owner：Codex（执行）；项目 Owner（用户，要求按生产标准持久化）
- 创建/更新：`2026-07-17`

## 范围

用 PostgreSQL 替换当前进程内 Profile/Device 事实源；公开 API 保持兼容。迁移必须保护 Household 边界、孩子账号反向绑定、幂等、审计与删除顺序，并在 Ubuntu Compose 上验证 API 重启后数据仍存在。内存实现仅保留给不依赖数据库的单元测试。

## 阶段

- [x] 1. 核对当前 Profile/Device 内存仓储、认证绑定、通用幂等表、Compose 开关和迁移链。
- [x] 2. 新增 `0012_profile_persistence`，建立孩子档案/设备表、索引、约束和旧账号绑定兼容数据。
- [x] 3. 实现 PostgreSQL ProfileRepository，并将 Learning/认证/路由依赖改为仓储协议。
- [x] 4. 覆盖创建、编辑、删除、重启重连、跨家庭、幂等冲突、账号级联和迁移往返测试。
- [x] 5. 更新 Compose 与文档，运行 API/Web/Flutter/契约门槛。
- [x] 6. 部署 Ubuntu，迁移前备份并前滚 `0012`，验证 API 重启持久化和 synthetic 清理；回滚保留数据表。华为已由 ADB 重新识别并冷启动到登录页，真实凭据登录/档案读取返回 `PLAN-0008`。

---

# PLANS.md — PLAN-0010 真机拍题视觉识别闭环

## 计划元数据

- 计划 ID：`PLAN-0010`
- 关联任务：`TASK-0009`、`PLAN-0008`、`ADR-0003`、`ADR-0015`、`ADR-0016`
- 状态：`IN_PROGRESS（代码、部署和 APK 安装完成；真实拍题状态验收待用户操作）`
- Owner：Codex（执行）；项目 Owner（用户，要求继续完善拍题识别）
- 创建/更新：`2026-07-17`

## 范围与发现

Nova 9 的相机/相册与本地脱敏预览已经可用，但 APK 只有在编译时注入 `STUDY_CAPTURE_SESSION_ID` 才会构建 Capture 客户端。远端 PostgreSQL 的任务、学习会话、Capture 和 ImageAnalysis Job 均为 0，证明此前没有发生上传。另一个真机阻塞是预签名 URL 使用 Compose 内部主机名 `minio:9000`，手机不可解析。

## 阶段

- [x] 1. 新增 `POST /households/{household_id}/capture-sessions`，由已认证孩子身份原子创建即时数学任务与活跃会话；客户端不能提交 child ID。
- [x] 2. 在内存/PostgreSQL 仓储实现同一幂等语义，并覆盖家长拒绝、跨 Household 不可枚举、重连与任务/会话唯一结果。
- [x] 3. Flutter 删除编译期会话开关，按孩子/日期创建或复用会话；上传后轮询 ImageAnalysis，并读取 QuestionExtraction。
- [x] 4. 识别结果进入可编辑人工确认；成功写入 VerifiedQuestion，失败/阻塞/超时提供可操作信息和手工填写兜底。
- [x] 5. 历史实现：对象存储增加独立公开签名端点，服务端内部读写仍走 `minio:9000`；Ubuntu 使用 LAN `9000`，Bucket 和密钥边界不变。该目标已于 2026-07-17 被 ADR-0018/PLAN-0012 替代，不再作为最终发布架构。
- [x] 6. 完成本机 API/Flutter/契约检查，部署 API/worker，覆盖安装 Nova 9 APK 并验证登录恢复。
- [ ] 7. 由用户在真机执行一次拍题，只核对生命周期状态和资源清理，不读取或输出真实题目内容。

## 回滚

本段是预签名直传的历史回滚记录。ADR-0018 迁移后的回滚必须使用匹配的 API/App 镜像，并只在隔离受信 LAN 临时恢复旧 `9000`/配置；不删除已创建任务、会话、Capture、Extraction 或 VerifiedQuestion。失败任务继续由既有保留/清理策略处理。
