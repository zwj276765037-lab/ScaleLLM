# R009 第32层出口扩精度：独立边界核查

范围仅decoder index31的真实分支出口`o_proj`和`down_proj`；前31层及该层其他节点不变，不是全层参考替换。生产源码只读，新文件仅属实验overlay。候选源尚未出现，本说明是方案核查，不是GPU或模型资格。

对b=2/4，Linear每组`A_b=floor(raw*2^(24+b-total_shift))`，左移部分必须精确；guard/acc各在原位宽上+b，每步acc仍按扩宽位宽wrap。末端half-away仍右移8，所得code为F16+b，o/down分别signed24+b/signed32+b。共同出口物理范围保持，正上限因格点细化更接近同一上界。o的guard/acc为42+b/42+b；Down05为45+b/54+b，最大b4使用S49/S58，合法物理域可用int64。

实际边界正确的必要条件：

- 最迟在grouped kernel返回存储时改用int64，不能先存int32再cast；Down的34/36bit出口否则已截断。传入同宽output_min/max。
- 仅两个目标模块临时`output_width=24+b/32+b`，避免生产project_prepared的S24 packed-negative修正误解合法正码；finally恢复原值。不得全局禁止该生产修正。
- 原Attention/MLP先按F16转FP32（V5:1441–1444、1592/1616）；在Attention tuple[0]或MLP结果进入对应残差加法前恰好乘一次2^-b，使有效decode为`RN32(code)*2^-(16+b)`。不能缩放概率tuple项、残差base或整层hidden；不能事后缩放已相加的hidden。
- 分支`output_dtype`须为FP32，不能先变BF16。仅给内部或出口增加整数位、仍在原位置丢低位，不构成精度提高。

FP32不是无限精度Host。它只有24个二进制有效位。o的S28大幅整数可能在cast时丢最低3bit，Down S36更不可能逐码精确；后续FP32残差加法、RMSNorm和logit前向仍会舍入。在原完整范围内，Host cast的统一最坏实值绝对误差可分别界为o不超过2^-18、Down不超过2^-10；b0的o整数则全部精确。附属stdlib探针保留各位宽正上端实值与实际binary32误差。新增2/4小数位不保证全部穿过FP32，也不代表硬件ABI已扩宽或RTL成本已验证。

主比较baseline/candidate2/candidate4统一对固定reference4，辅助报同格式candidateb/referenceb及reference0/2相对reference4漂移，这一口径合理。主比较同时改变两个真实出口精度，不能再称只改变中间舍入。各reference必须沿用独立exact商余内部，只改变这两个末端共同出口；不能用候选分组floor代替reference，不能把所有last-layer算子换reference伪装优化。

启动前窄审重点：b0 raw/counter逐bit复现原生产；原reference0复现旧reference；baseline/candidate各前31层hash相同、三reference前31层hash相同；CPU任意精度与GPU实际raw核b2/b4符号/shift/half/饱和/wrap；覆盖超过int32的Down及超过旧S24正上限的o码；inactive有效shift归0；检查两处残差前恰好一次缩放、所有属性/函数/hook异常也恢复；固定reference4身份，保留退化和尾部。此方案局部代数可定义，最终hidden/logits改善不能由方案推导，须看实测。
