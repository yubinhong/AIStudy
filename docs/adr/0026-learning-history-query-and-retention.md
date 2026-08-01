# ADR-0026: 家长学习记录查询与详细历史保留

- 状态：`Accepted`
- 日期：`2026-07-30`
- Owner：项目 Owner
- 决策者：项目 Owner（2026-07-30 明确要求）
- 关联：`PLAN-0024`、`FR-022`
- 替代/被替代：无

## Context

家长工作台只显示待复习数量，无法判断具体题目；最近学习记录又与概览混在同一页面，缺少可控日期范围。与此同时，确认题目和 Tutor 讲解会持续增长，详细学习内容没有明确的自用保留边界。

## Decision Drivers

- 家长应在工作台直接辨认到期题目，并能在独立页面查看近期明细。
- 查询必须继续按 Session、Household 和 Child 授权，且数据量有硬上限。
- 详细题目和讲解采用最小必要保留，但不能破坏仍在复习的开放错题。
- Attempt、AuditEvent 等追加写事实不能被一次界面优化顺带删除。

## Considered Options

1. 工作台继续只显示数量，详情保持无限期保留。
2. 工作台列出题目，独立页面默认最近 30 个上海自然日并支持单日筛选；详细学习历史固定保留 180 天，开放错题例外。
3. 所有学习相关表统一在 180 天后级联删除。

## Decision

选择方案 2。工作台直接展示每道到期题目的题干和到期日；独立学习记录页默认查询最近 30 个上海自然日，也可选择 180 天窗口内的单日。API 使用 UTC 半开区间，单次跨度最多 31 天、最多 500 条。

DataLifecycle Worker 固定以当前 UTC 时间前 180 天为截止点，分批删除不再被开放错题引用的 `VerifiedQuestion`、对应 `TutorTurn`，以及超过截止点的已解决 `MistakeRecord`/派生复习链路。任何 `open` 错题及其题目必须保留。Attempt、AuditEvent、账号、教材、开放错题和其他业务事实不在本次策略范围。

## Consequences

### Positive

- 家长无需进入模糊统计即可确认要复习的具体题目。
- 页面和 API 都有明确时间、数量和授权边界。
- 详细题目/讲解不会无限增长，开放复习链路仍完整。

### Negative / Trade-offs

- 超过 180 天且已结束的题目和讲解不可从产品中恢复；备份擦除仍需在正式数据策略中另行解决。
- 清理需按外键顺序执行，并可能经过多个 worker 周期才能处理大量积压。

### Risks and Mitigations

- 风险：错误级联删除开放错题；缓解：清理查询显式排除仍有 `open` MistakeRecord 的题目，并以 PostgreSQL 集成回归覆盖。
- 风险：时区边界漏记；缓解：Web 以 `Asia/Shanghai` 自然日计算，API 统一接收带时区时间并转为 UTC 半开区间。

## Compatibility and Migration

- 兼容性：`learning-details` 只增加可选 `from_at`、`to_at` 和扩大的有界 `limit`；旧客户端不传参数时仍得到默认近 30 天。
- 迁移步骤：`0030_learning_history_retention` 只增加清理所需索引；先迁移，再发布 API/Web/worker。
- 回滚：设置 `LEARNING_HISTORY_CLEANUP_ENABLED=false` 可暂停后续删除；应用/API 可成对回退，索引保留。已经按批准策略删除的数据不通过应用回滚恢复。

## Validation

- API 覆盖默认 30 天、上海单日转 UTC、非法/过期范围和 Household/Child 授权。
- PostgreSQL 集成覆盖过期无错题、过期已解决错题、过期开放错题和近期记录。
- Web 覆盖默认窗口、日期边界、导航、空状态和生产构建。
