# 验收目标

## 必须满足

- 模拟必须复现 Host 的 half-away-from-zero S24 打包。
- S24 Q8.16 / S32 Q16.16 Hadamard 必须复现五级整数蝶形、`11585` 系数和 `2^-16` LSB half-away 舍入。
- MinMax A8、zero point、ScaleCode code/shift 必须与仓库 bit-exact model 一致。
- 对所有未饱和测试组验证理论 L2 上界，违例数必须为 0。
- 真实激活必须报告输入范围、S24/S27 饱和、Hadamard 前后误差、A8 后误差。
- 模型 A/B 必须保持 folded weight、量化位宽、数据、token 数和随机性设置不变。
- 必须提供超范围和极小幅值反例，不允许把有条件结论写成无条件保证。

## 当前结果

- 7 个单元测试全部通过，包括 S24/S32 两条路径与仓库 bit-exact model 的逐元素一致性。
- 合成与真实激活的适用组理论界违例均为 0。
- 真实激活 32,768 组无入口和 Hadamard 饱和。
- 完整模型 A/B 为 64 blocks、65,472 scoring tokens、`records_complete=true`。
- 完整模型审计发现 S24 入口饱和 `260 / 8,447,459,328` elements；S32 入口、Hadamard 和 ScaleCode format error 均为 0。
