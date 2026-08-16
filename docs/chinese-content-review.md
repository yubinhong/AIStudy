# 语文内容教研与版权审核台账

本台账用于项目原创练习和家庭私有教材派生内容。它不替代出版单位授权、教材目录或项目 Owner 的正式签核，也不把技术测试通过描述为教研通过。

## 发布门禁

每一个准备作为正式课程发布的内容版本必须同时具备：

1. `source.type`：项目原创或家庭已授权私有教材。
2. `source.license_status`：原创内容为 `cleared`，私有教材为 `private_authorized`。
3. `source.review.status=approved`、`protocol_version=chinese-content-review.v1`。
4. 项目 Owner 的具名审核记录，以及权利凭证或审核单的 SHA-256 摘要。摘要仅记录在受控内容台账，不写入儿童学习记录、日志或 Provider 请求。
5. 每个版本的年级范围、技能、题型、确定性答案规则、干扰项、无障碍检查和 golden scorer 结果。

没有完整证据的条目必须保持 `pending_owner_review`。它们仅可作为项目原创演示与自动化夹具，不得宣传为正式教材、版权已审核内容或教研定稿。

## 当前原创演示包

| 内容 ID | 技能 | 来源 | 审核状态 | 说明 |
| --- | --- | --- | --- | --- |
| `...0001` | 拼音 | 项目原创 | `pending_owner_review` | 声调辨析 |
| `...0002` | 句子 | 项目原创 | `pending_owner_review` | 词语排序 |
| `...0003` | 阅读 | 项目原创 | `pending_owner_review` | 依据定位 |
| `...0004` | 生字 | 项目原创 | `pending_owner_review` | 偏旁与语境 |
| `...0005` | 词语 | 项目原创 | `pending_owner_review` | 词义辨析 |
| `...0006` | 古诗文积累 | 项目原创短句 | `pending_owner_review` | 不引用受版权限制的教材正文或古诗版本注释 |

当前条目已由确定性 scorer 和边界测试覆盖，但尚未收到具名教研/版权签核。项目 Owner 签核后，应以新的内容 revision 写入审核摘要和时间；既有 Attempt 始终引用旧 revision，不得回写或重判。
