# AT004 布局 warning 的合同影响

execution：只读核查完成；verdict：需纳入既有 POST/route 解释，未据此建立新增停点或合同违规；applicability：当前 floorplanning/PBP，place 与 POST 未完成；review：A007。

`Place 30-1229` 明确说明 partitioner 未能遵从部分 USER_SLL_REG。可见 100 个唯一对象均在 d0_mig_slice/ar15，均不属于 C01；工具随后抑制后续同类消息，总数和隐藏对象范围未知。原输入/约束字节保持与 placer 是否实际采用该属性是两件事：已审 9,525 对象策略快照覆盖候选及祖先，不包含这些 DDR 对象，也不记录 USER_SLL_REG 值；物理 XDC 和 175 约束来源文本未出现该字段，不等于嵌入网表无此属性。故不能把“策略保持通过”写成“DDR USER_SLL_REG 全部实际兑现”，也不能由该 warning 反推工程删除/软化了约束。

同阶段旧 E005 也显示 100 条后抑制，覆盖 ar15/aw15，可见对象交集 51；该轮 place 后来成功。它证明此类提示此前存在且曾非致命，不能证明本轮无影响，也不能比较被截断的受影响总量或归因于 C01。

`Place 30-356` 报整个设计的 SLR1→SLR2 需求 10,865/17,280（62.88%）。工具的 currently routable 是该阶段估计，并同时提示性能影响；不是候选专属开销、最终 SLL 用量、带宽或已合法布通。旧轮 10,594/17,280 指向 SLR0→SLR1，边界不同，不能相减作为改善/恶化或压力迁移证据。

C01 是否实际全部落入 SLR2，要等既有 POST 的实际 LOC/SLR、P 对应关系和有效 Pblock 核验；缺失、unknown、未放置或越界不能假通过。后续仍核当前阶段的 80 个保护边界、全局拥塞/跨区/时序/DRC/复位与 CDC，并以真实 route 状态验收合法布通。这些 warning 不增设独立属性硬门；正常流程按原合同继续，不改源码、约束或消费包。

[机器审核](place_warning_contract_impact_review.json) · [带原行号的冻结观察摘录](AT004_place_warning_observed_excerpt_20261017.json)
