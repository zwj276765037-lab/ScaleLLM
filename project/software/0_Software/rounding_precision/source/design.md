# M005 / SM021：Linear 恢复数值合同与接口 v1

冻结时间：2026-10-19T02:27:59Z。负责人 A014（设计/独审）；A015 实现；A016 数据/运行器。状态：可实施，未代表测试通过。本阶段不改生产源码，不使用GPU。用户主对照名称固定为 **仅输出舍入**、**当前实现**，另外单列精确oracle；图表不用R1/R2/R3。

## 1. 来源和适用范围

权威生产参照：[活动 V5](../../FPtoQ/experiment/v5_fullchain.py)，SHA-256 `58a6bb7c769209925bd3bcd9d1a06414b0a25415a46591f70d8efd62db0b9898`。本文行号对应该文件2026-10-19核查版本。403–457为逐组缩放、累加、末端；642–652、733–794为严格shift检查及位宽。首轮为Llama-3.1-8B-Instruct（32层），只研究固定A8/W整数码与ScaleCode下的Linear恢复，不覆盖上游量化、非线性近似或全模型精度。

| profile | 目标格式 | active total_shift | raw有符号宽度 | guard / accumulator | 输出 |
|---|---|---|---|---|---|
| attention | 0x48384103 | 26..47 | 37 | S42/F24 / S42/F24 | S24/F16 |
| mlp_gate_up | 0x48384605 | 20..44 | 33 | S37/F24 / S44/F24 | S24/F16 |
| mlp_down | 0x48384605 | 12..44 | 33 | S45/F24 / S54/F24 | S32/F16 |

参数从profile派生，不能由样本默默覆盖。05须逐字段确认，不只看format ID；V5默认Down-S24/shift12关闭，不是本合同。旧04输入保留来源身份，可以在目标profile下重放，但不得改名为05实测；旧工程只读。

## 2. 输入 JSONL v1

每行一个输出标量及按生产次序排列的全部Group32贡献。文件UTF-8、无NaN/Infinity；JSON整数不能由float或bool冒充。sample_id在一个输入文件内唯一。唯一公共入口：`experiment/linear_recovery.py::evaluate_linear_sample(sample: dict) -> dict`；批次聚合用 `experiment/metrics.py::summarize_results(rows)`。

| 字段 | 类型 / 约束 |
|---|---|
| schema_version | 整数1 |
| sample_id | 非空字符串 |
| kernel | 固定 `linear_recovery` |
| profile | 上表三个值之一 |
| groups | 非空数组，顺序即累加顺序；pilot最多4096组/行，超限报告输入资格错误 |
| groups[].dot | Python整数，`Σ_{lane=0..31}(q_a−zp_a)q_w`；不得由反量化float推断 |
| groups[].act_code / weight_code | 整数0..255 |
| groups[].act_shift / weight_shift | 整数0..63；total_shift为二者之和 |
| provenance | 必需对象，字段如下 |
| provenance.kind | `synthetic` 或 `real_trace` |
| provenance.model | 字符串或null；真实首轮必须为 `Llama-3.1-8B-Instruct` |
| provenance.layer | 0..31整数或null；真实样本必填实际层 |
| provenance.op | q_proj/k_proj/v_proj/o_proj/gate_proj/up_proj/down_proj之一或null；真实样本须与profile匹配 |
| provenance.source_files | 数组，每项 `{path:非空字符串, sha256:64位hex}`；真实样本非空，由runner校验内容身份 |
| provenance.source_format_id | 实际来源format字符串或null，禁止改写04为05 |

允许附加provenance.row/column/token/group_selection等定位及样本标签。真实采集必须增加provenance.trajectory，明确 `v5_production`、`bf16` 或实际其他来源；BF16轨迹仅标bf16_trajectory_local_replay，不是05生产轨迹。组数：首轮真实Q/K/V/O/Gate/Up通常128，Down448；若实物维度不同，保留并分流为非当前模型范围，不静默裁组。合成短组不冒充真实模型覆盖。

可选 `groups[].lane_evidence={q_a:[32整数],q_w:[32整数],zero_point:整数}`：q_a/zp范围0..255；V5 W8为−127..127，W4为−8..7；提供时独立重算dot并要求相等。未提供时只承诺恢复级验证，不承诺上游点积已验证。dot可达保守界分别为±1,036,320和±65,280；raw最大绝对值分别67,386,708,000和4,244,832,000。越界测试可保留，但不进入生产合法域分母。零code组允许dot非零，贡献恒为0，不因该组total_shift越界触发active shift错误。

## 3. 三条计算路径

设第g组 `r_g=dot_g*act_code_g*weight_code_g`、`t_g=act_shift_g+weight_shift_g`。active当且仅当两个code均非0。

**精确oracle：** 使用任意精度整数/精确有理数计算 `y*=Σ r_g/2^t_g`，全程无按组截断、无有限宽累计。不得调用生产replay中的舍入/移位helper作为独立期望。把最终精确值表示为约分后的有理数，不将FP64当作S54精确参考。

**仅输出舍入：** `u=round_half_away(y*·2^16)`，然后仅在共同输出宽度sat。half-away定义：非负x取floor(x+1/2)，负x取−floor(−x+1/2)；例如+0.5→+1，−0.5→−1。无中间wrap。

**当前实现：** 严格生产入口遇active非法t时拒绝，`current.accepted=false,output_code=null`；可另返回`diagnostic_zero_guard_raw`展示非严格RTL-zero-guard错误路径，不能算主对照。对合法t，先计算 `a_g=(r_g >> max(t_g−24,0)) << max(24−t_g,0)`。这里有符号右移等于floor除以2^k，负数不是向零截断。逐组检查a_g是否超guard；**V5只audit guard，既不wrap也不sat guard**。然后按原次序 `s=acc+a_g`，检查s是否超S_W，再执行 `acc=((s+2^(W−1)) mod 2^W)−2^(W−1)`。任何一步溢出都计数，不只看末尾。最后 `v=round_half_away(acc/256)`，sat到共同输出S24/S32。pre-saturation值及饱和次数必须保留。

生产参照允许有界抽取上述V5 AST表达式做CPU标量回放，保存被抽取节点与源hash，严格限制节点/操作并校验结构；不得任意执行整个生产文件。可与现有独立标量helper交叉核对。CPU模型一致不等于GPU Triton或RTL已逐bit通过，后两项另记NOT_RUN。

## 4. 有效域和确定性界

逐行status为 `ok / out_of_contract / invalid_input`。缺字段、错类型、未知schema/profile、资源上限等为invalid_input；格式可解析但dot/raw/guard/accumulator越界、active非法shift、输出饱和等为out_of_contract。无界oracle可以对安全可解析的异常样本继续计算，但不能把异常误差纳入有效域平均。防止非法巨大shift导致资源耗尽，metadata不在0..63时不执行移位。原异常样本保留并列原因；预期负向样本正确被拒绝不是算法失败。

`bounds.applicable`要求上述范围检查均通过、严格路径接受、当前和仅输出路径都无饱和。Numerical status与来源资格独立：synthetic、legacy_input_replay、current_format_real_trace分别计数；旧04或来源缺失不能计入当前格式真实运行证据。保留 `provenance_status`、`eligible_current_format_evidence` 及具体原因。真实来源文件校验由runner记录，缺失不是数学界反例。evaluate入口始终返回eligible_current_format_evidence=false及source_identity_not_verified；runner另保存实际逐文件hash校验和捕获manifest、组位置/算子/目标参数核验回执，只有来源为v5_production且全部证据闭合才可授予该资格，不能信任输入自带verified=true。synthetic/旧04/BF16轨迹均不能授予当前生产轨迹资格。

令G_right为active且t>24组数；d=t−24，`rem=r−floor(r/2^d)·2^d`，即使r<0仍有0≤rem<2^d。G_nonzero_remainder只数rem≠0的右移组。定义精确截断损失 `D=Σ rem/2^(d+24)`。无溢出/饱和时，累计右移误差恰为−D；因此：

- `|y_current−y*| ≤ G_right·2^-24 + 2^-17`；可用G_nonzero_remainder替代G_right，或收紧为D+2^-17。
- `|y_current−y_output_only| ≤ G_right·2^-24 + 2^-16`；可收紧为D+2^-16。两个末端都舍入，不能沿用单个半LSB界。
- G=128/448时第一式保守界分别1.52587890625e−5、3.4332275390625e−5。G不是深层网络传播次数。

所有界比较使用精确有理数，违例判据不加浮点容差。统计signed error并检验截断项非正；不假设独立白噪声或√G累积。相同出口码比例和有符号LSB直方图仅为描述性统计，不替代误差界及异常检查。

## 5. 返回结构与聚合

`sample_id/profile/status`必返；`invalid_input`仍须返回可定位原因且不让单坏行终止整批。正常可计算行返回：

- `current={output_code,pre_saturation_code,accumulator_f24_code,accepted,error_counts}`。error_counts至少含invalid_active_shift、dot_range、raw_range、guard_overflow、accumulator_overflow、output_saturation；诊断拒绝输出另标。
- `output_only={output_code,pre_saturation_code,saturated}`；`exact={numerator,denominator,denominator_bits}`，大整数numerator/denominator均为十进制字符串，bits为整数。
- `metrics`含 signed_error_current_vs_exact、absolute_error_current_vs_exact、lsb_error_current_vs_exact，以及current_vs_output_only对应字段；展示为有限float，溢出展示null，禁止NaN/Infinity。精确值存于 `metrics.exact_fractions[同名key]={numerator:str,denominator:str}`。
- `metrics.g_right/g_nonzero_remainder`；`metrics.bounds={applicable,excluded_reasons,vs_exact,vs_output_only,tight_vs_exact,tight_vs_output_only,violation_vs_exact,violation_vs_output_only}`。各bound为有理数对象；tight优先用D的精确界，违例bool或不适用null。
- 来源判定独立返回，不把synthetic有效样本写成真实模型通过。

聚合按profile、status和来源分开；至少总行数、坏行数、理论适用数/违例数、每类异常计数、有效域signed mean/RMSE/max/P99、LSB直方图、与仅输出舍入相同的码数/比例。分母为0时null并解释，不能输出虚假0误差或100%一致。保留逐行结果使汇总可复算。

## 6. 后续局部合同接口边界（本轮不自动实现）

RoPE可独立固定同一S24/F16输入和S18/F16系数：当前每个乘积half-away后加减，输出一次路径先精确乘加再half-away，均S24饱和；系数误差另算。PV固定U16概率和KV12/code/shift：当前每key恢复F24后累加再F16，输出一次路径保留精确项至出口；须核S43每步语义后另冻结。QK固定query/key/code/shift/head系数：当前分组floor到F14再相加；输出一次时出口round模式必须显式定义，不把floor改nearest后宣称仅改变次数。score clip单列。各节点新schema/源码逐项核定后进入新批次，不泛化Linear界。
