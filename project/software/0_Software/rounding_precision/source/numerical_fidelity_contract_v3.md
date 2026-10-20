# ScaleCode多次位宽舍入：数值保真合同 v3

A014，2026-10-19；当前为执行接口与验收语义冻结，尚无v3新实现/数据通过结论。用户最新范围：只证明多次位宽舍入的数值精度；ACC/PPL已有结果，本轮不重跑、不设置任务非劣效门。本文取代此前设计中将任务指标作为本次前置条件的部分；旧证据保持原样。

## 1. 对象、来源与两类误差

生产来源：[V5](../../FPtoQ/experiment/v5_fullchain.py)，SHA256 `58a6bb7c769209925bd3bcd9d1a06414b0a25415a46591f70d8efd62db0b9898`。权重量化制品、A8/KV12规则、RoPE系数、SiLU/exp量化LUT、设计clip、共有输出接口及Host转换固定。不能把真实exp/silu或BF16原权重代入参考后将函数近似/基础量化差归因多次舍入。代码事实与exact商余范围见[工程方案](paper_precision_implementation.md)，局部证明及条件边界见[理论方案](paper_precision_theory.md)。本轮不采用其中任务评测要求作为数值验收门。

每个节点始终返回三项：

- `exact`：同一基础量化输入与共同函数定义下、最终出口舍入前的精确值。
- `reference_code`：exact按共同规定的出口舍入/限幅，代表高精度算术参考的可交接输出。
- `current_code`：当前位宽与生产次序计算的输出。

必须并列两组误差：`extra_rounding = current − reference_code`隔离额外中间舍入；`node_fidelity = current − exact`展示节点总算术损失。不得因SwiGLU/Host主两路共有一次出口而extra=0就称不存在数值误差。用户图例使用“当前位宽”“高精度参考（共同出口）”“精确节点值”，不用R编号。

局部实验固定相同输入码/metadata/组顺序。连续路径保留相同基础量化算法，但每一路根据自身激活重新算code/scale/zp、KV12和LUT索引；这些改变属于数值传播，不能强锁码后称完整连续路径。BF16轨迹局部回放、V5当前轨迹局部回放和真正两条连续路径分别标记，不互相代替。CPU节点模型一致不等于GPU/RTL逐bit已验证。

## 2. 稳定公共入口、数组与精确输出

公共入口：`numerical_reference.policy.evaluate_node(node: str, arrays: dict, config: dict) -> dict`。独立内部入口为`exact_reductions.evaluate_reference`与`current_nodes.evaluate_current`；exact不得调用current的舍入/累加函数充当独立期望。无torch输入或GPU初始化要求；生产CPU/有界AST调用必须记录依赖身份及来源。

数组用NPZ保存，无pickle/object dtype；整数至少在运算前转signed int64，bool仅用于mask。metadata可按NumPy广播到表内目标形状，广播后的范围/shape必须检查；不能静默截短G、K或lane。输出坐标与原tensor关系由manifest保存。CPU初始每chunk最多4096个输出坐标，G≤448、K≤128；超过时由runner分块而非改数值语义，沿用CPU1线程/RSS8GiB/300秒有界准备验证。

| node | arrays | 输出形状 / F |
|---|---|---|
| `linear` | `dot[N,G]`，`act_code,act_shift,weight_code,weight_shift`广播至[N,G]；可选`q_a,q_w[N,G,32],zero_point[N,G]` | [N]，F16；config.profile=attention/mlp_gate_up/mlp_down |
| `rope` | `raw_pair[N,2]`按原逻辑低/高半维配对；`cos_q16,sin_q16`广播至[N] | [N,2]，F16 |
| `qk` | `dot[N,4]`，`kv_code,kv_shift`广播至[N,4]；可选`query_s24,key_s12[N,4,32]`独立核dot | [N]，F14 |
| `softmax` | `score_q14[R,K]`、`valid_mask[R,K]` bool、`lut_u17[257]` | [R,K]，F16（概率） |
| `pv` | `probability_u16,value_s12,kv_code,kv_shift`广播至[N,K]，每行代表一个选中输出lane | [N]，F16 |
| `swiglu` | `gate_s24,up_s24`同shape，`lut_s24[8193]` | 同shape，F16；S32出口 |
| `host` | `raw_s32`同shape；可选config.input_width=24/32，默认32 | 同shape，F16物理单位 |

最低返回：node、profile/config身份、current_code、reference_code、exact、masks、audit、bounds。实现字段`bound_numerator/bound_denominator`及`reference_bound_numerator/reference_bound_denominator`统一采用输出码单位，metadata写`bound_units=output_code_LSB`；转本节后文的实值界须再乘2^-fractional_bits，禁止混单位。code均int64数组；Host code为`int64(float32(raw))`，可能为+2^31，故不能强行装回int32。精确表示不存可能溢出的共同大分子，采用

`exact={quotient_floor:int64[], remainder:int64[], denominator:int64[]或可广播, fractional_bits:int}`，满足`0<=remainder<denominator`、`denominator>0`；实值=`(quotient_floor+remainder/denominator)*2^-F`。大整数/Fraction用于独立spot核对。分数不要求约分，但重构必须精确。无效输出用accepted mask区分，不能用0假装可计算；统计端只在明确mask下取值。

可另返回`selected_code`用于单注入策略，但主current/reference两端定义不随selected策略改变。Softmax允许两个开关的四组合；不添加会改变基础量化、LUT、系数或Host精度的隐式开关。

## 3. 节点共同函数、合法域与参考

**Linear。** attention：shift26..47/rawS37/guardS42/accS42/outS24；Gate/Up：20..44/S33/S37/S44/S24；Down05：12..44/S33/S45/S54/S32。共同F24内部格距是2^-24，出口F16。active仅两个code均非0。dot保守绝对界W8为1036320、W4为65280；code0..255、metadata shift0..63。当前guard仅audit、acc逐组wrap；参考精确累加后half-away一次，再共同sat。逐步异常不能只看末尾。可选lane存在时独立重算dot。

**RoPE。** raw为S24，系数绝对值≤65536且来源hash固定。当前四乘积各half-away /2^16后加减；参考精确乘加后half-away一次，共同S24 sat。exact使用相同量化系数，不使用真实sin/cos；输出pair与原head坐标保留。

**QK。** query S24、key在[−2047,2047]，4组32lane；dot的物理绝对界`32*2^23*2047`。code0..255，active shift8..32；零code贡献0。当前各组`floor(dot*code*5793/2^(shift+18))`后求和；参考先精确和再floor一次。**±16 score clip是冻结的节点函数**：exact主值为精确和裁至[−16,16]，reference为共同floor+clip，另存unclipped诊断/clip率。这样不把设计clip损失混成舍入损失。

**Softmax。** score在±(16<<14)，K=1..128，固定257项非负单调下降量化exp表且首项65536（数组合法性及来源hash都核对）。共同函数是有效key的row max、delta clip[-16,0]、同LUT连续线性插值，再精确归一化。当前插值严格为`high - floor(((high-low)*fraction+512)/1024)`；不能换成对精确exponent做half-up，两者恰半时不同。当前reciprocal及最终half-up照源；参考精确概率经共同U16 half-up和上限65535。full-mask row为软件padding输出0，不计真实token误差分母；masked key输出0并用metric_mask排除结构零。single-key的65536→65535是共同出口cap，不当算法异常。

**PV。** probability0..65535、value在±2047、code0..255、active shift8..32、K≤128。当前每key算术右移到F24后sum，half-away到F16再S24 sat；参考在出口码域精确求和`Σ prob*value*code/2^shift`后同出口。活动V5的PV用int64求和，没有S43逐步wrap操作，不能替它造wrap后声称对应V5；硬件有限宽一致性另需证据。

**SwiGLU。** gate/up按S24有符号解释；生产接受的零扩展24-bit负payload须先同样规范化，超payload范围拒绝。同一8193项S24 SiLU表、地址规则及±16外分支完全保留；exact为该共同SiLU值乘up的精确乘积，当前与reference均在S32/F16共同出口half-away一次。输出超S32拒绝，不用饱和替代。此节点extra应为0，其出口node_fidelity仍须报告。

**Host。** exact为输入整数码乘2^-16；共同转换为FP32(raw)*2^-16，当前与reference相同。S24码可精确转FP32，S32大于2^24的绝对码可能丢位；报告实际被丢位、绝对/相对损失及跨边界。禁止把主参考Host改FP64再把混合误差叫额外中间舍入。后续连续路径必须保留生产Host转换。

## 4. masks、数值资格与理论界

所有mask与输出shape一致：`domain_valid_mask`（输入类型/范围/配置）、`accepted_mask`（生产规则产生输出）、`overflow_mask`（任一步raw/guard/acc等异常）、`saturation_mask`（Linear/RoPE/PV格式限幅）、`clip_mask`（QK/Softmax有意clip）、`software_padding_mask`、`metric_mask`、`valid_mask`、`bound_applicable_mask`、`bound_violation_mask`、`reference_bound_violation_mask`。`metric_mask`排除padding和Softmax masked key；普通输出全true。`valid_mask=domain_valid & accepted & ~overflow & ~saturation & metric_mask`。有意clip本身不取消数值资格。

报告必须同时给全部接受输出和严格有效域的计数/误差，保留异常原始样本；禁止静默过滤失败文档后声称整体保持精度。有效数量0时ratio/bias为null。bounds缺实现可标`not_implemented`，不能把False的applicable当“已证明且无违例”。`bound_violation`对应current−exact，`reference_bound_violation`对应current−reference_code；名称以此固定，摘要必须写全比较对象。

合法无异常域的界（实值单位）：

- Linear：余数损失D精确求出，`|current−exact|<=D+2^-17`；`|current−reference|<=D+2^-16`，D≤G_right*2^-24。详细符号/负数规则见理论文件。
- RoPE：每输出两个乘积舍入，`|current−exact|<=2^-16`，与共同出口参考≤1个F16码（整数格距可收紧）；输出饱和另列。
- QK：clip前四组floor总损失D_q∈[0,4*2^-14)，current−reference码差为`−floor(四组余数分数之和)`，最多3个F14码；共同clip不扩大界。current−exact≤D_q，方向非正；保留clip前D以解释。
- PV：同Linear余数恒等式，D≤K_right*2^-24；对exact≤D+2^-17，对共同出口≤D+2^-16。K≤128时最多1个F16码的主对照差。
- SwiGLU：有效S32域extra=0；current−exact的共同出口误差≤2^-17。
- Host：extra=0；S24入口node_fidelity=0；全S32入口可用64*2^-16作保守绝对界（−2^31恰可表示），可按实际binade半ULP收紧。不能把Linear整数出口的1/2码界未经处理延续到Host返回张量。

Softmax可冻结可复算的保守界：有效row的精确插值为E_i，生产整数插值为E'_i；S=ΣE，S'=ΣE'，ε_i=E'_i−E_i，有|ε_i|≤1/2且S,S'>0。输出码域

`Bnorm_i=65536*(|ε_i|*S+E_i*|Σ ε|)/(S*S')`，
`Brecip_i=E'_i/131072`（可用`E'_i*|R−2^32/S'|/65536`收紧，R为生产reciprocal）。

则对共同出口参考的界为`(Bnorm_i+Brecip_i+1)*2^-16`；对exact为`(Bnorm_i+Brecip_i+1/2+dist(65536E_i/S,[0,65535]))*2^-16`。由归一化差的通分三角界、reciprocal至整数的半格误差、共同出口舍入及clip投影得到，不假设独立噪声。最后的dist不能漏，否则single-key共同cap会构成假违例。full-mask不适用。首版可采用更保守的row-length界：由S,S'≥65536、E_i,E'_i≤65536及|Σ ε|≤K/2，得到Bnorm≤(K+1)/2、Brecip≤1/2；故对exact≤(K+5)/2个输出间隔，对共同出口≤(K+4)/2个输出间隔。K用valid key数可收紧，用总列数也保守。必须标`bound_kind=conservative_row_length`，不能称实际D收紧界。实现来不及可暂列未实现，实际数值结果仍可报告，不冒称所有节点理论闭合。

## 5. manifest、来源与可复算统计

每个NPZ记录的manifest最少含：schema_version=3、record_id、doc_id、source_id、domain、split、text_sha256、duplicate_cluster、token_ids/positions或可追溯token文件、layer、node、trajectory、output_shape、selection（token/head/channel/group坐标和抽样规则）、target_format、production_source_hash、artifact/input SHA、LUT/coeff/weight制品hash、config与输出对齐映射。记录是否完整输出或预定抽样，不能将抽样tensor冒称全层全输出。真实来源不得由用户填verified:true自证；runner实际核文件和shape/positions。内部节点由不同轨迹产生的数组不得拼成无来源的“真实连续路径”。

统计单位为document×layer×node（必要时profile/通道组细分），先在一个文档的对应输出集合计算两组误差，再跨独立document汇总；两个长度、同文档窗口/层/通道不是独立文档。每组参照r、误差e：

`signal_rms=sqrt(mean(r^2))`；`absolute_rmse=sqrt(mean(e^2))`；
`relative_l2_percent=100*sqrt(sum(e^2)/sum(r^2))`；
`normalized_signed_bias_percent=100*mean(e)/signal_rms`。

同报signed mean（实值）、maximum_absolute_error、理论界值/占界比例、资格计数与异常率。relative L2和normalized bias分别标参照是共同出口还是exact，不能混分母。跨文档报告P50/P95/P99、最大值及有效文档数；分位方法固定nearest-rank或在manifest明示其他方法，不混scalar池当文档分位。偏差为有符号分布，不能把其P99当绝对尾部，另报绝对偏差分位或负尾P01。

zero-signal文档/张量的相对量为null，保留绝对误差。小信号不默加epsilon：正式阈值尚未冻结时按signal_rms与输出格距u的比例分层并完整报告原值；若采用阈值，必须是预定网格尺度或独立校准依据，不能看正式误差后调。图主轴为相对L2百分比/信号尺度、分层与尾部，LSB仅辅助解释为相邻固定点值间距。不存在未经依据的通用“<1%即通过”规则。

数值可支持的论文结论依赖正式数据：给出分布、模型、32层/节点覆盖和误差预算依据后，陈述观察到/证实的范围。理论局部界可普适于合同合法域，但小pilot或同码率不能证明所有输入相对精度良好。正式数据来源/去重与运行预算由主控和A016冻结；旧first64/128仅工程smoke，不能冒充新增独立文档。

## 6. 实施与独审

A015负责独立商余exact、生产current、边界和差分；A016负责实际来源/NPZ/runner及原始结果；A014在[numerical_fidelity_review_v3.md](numerical_fidelity_review_v3.md)独审。普通修复连续，不新增逐项批准门。当前仅CPU1线程、无本角色GPU/后代；新GPU资源由主控原合同处理。核验重点：生产参照0 mismatch；exact独立Fraction核对；输入资格与全部异常；负floor/ties/抵消/clip/LUT边界；真实数组来源；统计分母/分位可复算。无实现或无数据的节点明确未覆盖，绝不填PASS。整个任务不包含ACC/PPL重跑或任务非劣效判断。

## 7. 正式结果前冻结的文档内最大误差统计（R004补充）

本节冻结主图局部统计对象，未改变任何模型输入、算术、输出或通过阈值。以current与共同出口reference之差为主系列。对文档d、节点类别c、该类别的完整测量位置集合J_c，位置j的误差能量E_j=Σ(current−reference)^2、参考能量S_j=Σreference^2。每位置仍按既定accepted真实坐标计算，不改为只保留strict好样本；对应mask/异常计数继续单列。

每篇每类统计M_{d,c}为**满足所有j∈J_c的√E_j≤(M/100)√S_j的最小非负M**，允许+∞。S_j>0时等于该文档内所有位置相对L2百分比的最大值。完整32层的位置数固定：Linear224（7算子×32层）、RoPE64（query/key）、QK32、Softmax32、PV32。主图先产生每文档每类一个M，再跨文档报告P50/P95/P99和最大值；不能先对层求分位再平均，也不能把224/64等位置数当N。另报M_{d,all}=max_c M_{d,c}，标签为“全部五类已测局部位置最大误差”，涵盖384位置；不含SwiGLU/Host独立出口损失，不称所有软件算子的全覆盖。

保留取得最大值的(layer,node,op)、该位置signal_rms、最大绝对误差及signed bias；并列极值以layer/node/op固定字典序选展示位置，另保存全部tie数量。该bias只叫“最大误差位置的bias”，不能冒称整类所有位置的总体signed bias。连续两轨迹仍独立报告逐层hidden和final norm，不能将同码局部M与传播误差混成一组分位。

**零信号、非法和缺失：**

- S=E=0：原位置relative L2仍为null，标`exact_zero_match`并计数。它对上述乘性界不增加约束；若所有所需位置均如此，文档M=0且`all_zero_exact=true`，此0来自精确相等的界定义，不是给0/0或失败填0。
- S=0<E：文档最大值为+∞，JSON存`value=null,state=unbounded,reason=zero_reference_nonzero_error`；保留绝对误差，不加epsilon。该文档在扩展排序中大于全部有限值，必须保留在分位分母内，不能简单过滤null。
- 所需位置缺失、重复、空的实际输出域、非法/非有限能量或身份不一致：`state=unestimable,value=null`，报告完整性失败；不能从剩余位置给主max。若已观测到无界点但还有缺失，可另标`observed_unbounded=true`，不能冒称完整文档已验收。数值格式sat/有意clip等已接受输出仍留主统计并保留异常字段；不因误差大而排除。

每个统计cell报告planned/completed/estimable/finite/unbounded/unestimable文档数、exact-zero位置数及all-zero文档数。完整目标的分位N包含finite、unbounded和all_zero_exact文档；只要还有缺失/失败，不能以剩余文档替代完整1024目标，须标partial并抑制其总体CI。允许单独展示“已完成部分”描述统计，明确分母和未完成数，不声称随机无偏子样本。

**分位及区间：**主点估计沿现有实现固定为linear interpolation（h=(N−1)p、相邻次序值插值）。扩展值+∞若具有正插值权重则结果+∞；h恰为整数直接取该秩，避免0×∞。结果以value/state显式编码。区间端点用整数次序统计，不插值；`numerical_quantile_uncertainty.md`已冻结的二项秩算法可直接用于文档内M这个单一随机变量，**不再因为内部有32层而重复Bonferroni32**。数据本身的∞与有限样本上界秩N+1分别标`data_unbounded`和`sampling_upper_unbounded`，均不得用样本最大有限值替代。

单个域、单类别、单分位的pointwise区间取family_size=1；若宣称多个类别/域/分位同时覆盖，须预先明确完整family再Bonferroni。例如5类×3域×{P95,P99}为30，加入总max为36；若P50也声称联合区间则相应扩张。逐层传播的32层（含final则33个位置）是另一族，逐层95%不等于联合95%。仅画多个pointwise区间可不作校正，但必须显式只作逐项保证，不把它们解读为联合带。

若总体分位q_p(M)有有限上界，它控制的是一篇随机文档内全部该类已测位置：在相应抽样假设下至少p比例文档满足该文档内最坏误差不高于该界。它不是每token、任意长度、所有未来输入的确定界。1024固定2:1:1配额合池仍仅描述性；域内二项区间也以iid或明确可辩护的抽样模型为条件，cluster/token去重不认证该假设。基础区间依据及有限尾样本无界规则沿[NIST TN2119 §5.3（式30–31）的已核来源记录](numerical_quantile_uncertainty.md)，不因观察正式结果而更换分位法、零信号规则或family以缩窄区间。
