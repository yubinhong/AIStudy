# ADR-0025：供应商中立的儿童英语口语练习插件

- 状态：`Accepted`
- 日期：`2026-07-29`
- Owner：项目 Owner + Flutter/API/Web 负责人
- 决策者：项目 Owner（批准“英语学科与合规口语练习框架”实施计划）
- 关联：`PLAN-0022`、`TASK-0011`、`TODO-218`、`ADR-0004`、`ADR-0006`、`ADR-0017`
- 替代/被替代：将 TODO-202/203 的首个有界增量提升为实现；不改变数学核心任务/会话模型

## Context

孩子登录后需要在数学与英语间明确选择。英语首版是 5–8 分钟的打招呼、校园交流、点餐情景练习，不是无限自由聊天。当前 Gemini API 与 Google Cloud 生成式 AI 服务条款不允许把服务用于可能由 18 岁以下用户访问的应用，因此不能在本项目接入 Gemini、下发云密钥或把测试通道描述为 Gemini Live。

## Decision Drivers

- 入口始终可见，但真实语音处理必须同时经过家长逐孩子启用、当前同意版本、Provider 合规批准、配额和单会话门禁。
- App 只携带现有可撤销 Session 连接 API；Provider 凭据、URL 和消息形状不能进入客户端。
- 不保存原始音频、完整转写、Provider 原始消息或恢复缓存。
- 英语是独立插件，不向数学 `Subject`、`StudyTask` 或 `StudySession` 增加枚举值。

## Considered Options

1. Flutter 直接连接 Gemini Live，并由 API 签发临时令牌。
2. 新建独立英语微服务，先接入 Gemini 再补家长同意与儿童门禁。
3. 在 FastAPI 模块化单体内建立供应商中立接口、摘要事实和 WebSocket 中继，只提供默认 `disabled` 与测试 `fake` Provider。

## Decision

选择选项 3。

1. Flutter 首页固定显示数学和英语；数学继续进入现有学习桌，英语未启用或 Provider 不可用时保持锁定。英语只包含三个固定情景和 5–8 分钟引导式对话。
2. 家长按孩子保存 `enabled`、`Pre-A1/A1/A2`、同意版本和乐观版本号。启动同时校验孩子绑定、家长所有权、同意、Provider、每天 10 分钟、单活动会话和单次 8 分钟。
3. 客户端通过 Bearer Session 连接 API WebSocket。二进制帧为单声道 PCM16 little-endian，输入 16 kHz、输出 24 kHz、20/40 ms；JSON 仅承载版本化控制事件。
4. API 只提供 `EnglishLiveProvider` 接口、`disabled` 和显式测试用 `fake`。仓库不增加 Google SDK、Gemini Adapter、`GEMINI_API_KEY`、云端临时令牌或 Provider URL。真实 Provider 需条款变化或书面例外、合规评审和新 ADR 修订。
5. 对话 Policy 只允许选定情景/等级的短英语；连续两次沟通失败才给一句中文提示；禁止索取姓名、学校、地址、联系方式，禁止成人/危险/自由话题、搜索、工具、视频和外链。
6. PostgreSQL 只追加保存主题、等级、时间、时长、轮数、输入/输出音频毫秒、Provider/model/Policy、成本和最多三条非敏感标签。它们不是掌握度事实。音频、完整转写和 Provider 消息不落库、不进导出、不进日志。

## Consequences

- 正面：当前可交付可审计的学科入口、权限、生命周期和实时传输骨架，同时避免不合规 Provider 锁定客户端架构。
- 代价：`fake` 只能验证协议和 UI，不能代表真实口语质量；SoLoud 原生引擎增加客户端构建体积和供应链审查面。
- 风险控制：部署默认 `STUDY_ENGLISH_LIVE_ENABLED=false`、`STUDY_ENGLISH_LIVE_PROVIDER=disabled`。部署环境不能启用测试 Provider；`fake` 只允许测试代码通过依赖注入构造。

## Compatibility, Migration and Rollback

- OpenAPI 增量升级为 `0.12.0`；既有 `ChildProfile.subjects`、数学任务和会话不变，旧客户端可忽略新路径与表。
- `0029_english_speaking_practice` 只增加设置、摘要会话和英语幂等表；孩子删除由复合外键级联，不存在音频对象清理。
- 回滚先关闭全局开关并保持新表。数据库 downgrade 会在设置或摘要非空时拒绝，只有明确确认无需保留记录后才能执行。

## Validation

- API 覆盖授权、同意、版本、幂等、配额、并发单会话、PCM 帧、断线/空闲、会话撤销、导出和级联删除。
- Flutter 覆盖两学科、数学路由、锁定/可用、三个情景、按住说话、播放打断、权限和前后台生命周期；Web 覆盖 Cookie/CSRF/幂等代理与 Provider 门禁。
- 固定英语安全评测覆盖个人信息、成人/危险话题、自由聊天、中文兜底、回答长度和 Provider 失败。真实 Provider 上线前另做质量、延迟、成本和儿童安全评测及实体设备验收。
