# A015：R007定向舍入纠正独审说明

本轮仅读生产/冻结参考，做小型Python integer/Fraction核查；无GPU、模型前向、生产或冻结源码修改，无后代。依[冻结R007合同](../optimization_contract.json)，仅评估Root冻结的3个RNE策略；额外4位仅为后继备用，不加入本轮搜索。**可修复的局部单向截断已经确认；RNE整体是否改善必须由独立验证数据决定。**

## 1. 确定性方向与最小改法

- [Linear F24组对齐](/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/software/0_Software/FPtoQ/experiment/v5_fullchain.py:403)的`(raw >> right) << left`在右移时是floor；[PV逐key对齐](/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/software/0_Software/FPtoQ/experiment/v5_fullchain.py:1009)同样floor到F24。合法无wrap/溢出域，逐项误差均≤0，累加后仍≤0；同单调half-away出口及sat不会改变当前码≤精确共同出口参考码的方向。这里是固定输入下的确定性误差，不靠零均值或独立噪声假设。
- [QK四组floor](/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/software/0_Software/FPtoQ/experiment/v5_fullchain.py:932)也有相同单向损失；共同±16 score clip不会扩大固定输入差。但本轮工程约定不改QK，以便把Linear/PV干预分开辨认。
- 最小等位宽改法：仅把指定组/项的右移floor改为最近偶数（RNE），保留F24格距、guard宽度、acc逐组wrap、F16最终half-away和sat。对`s>0`：`q=x>>s; r=x-(q<<s); h=2^(s-1); RNE=q+[r>h or(r==h and q odd)]`。`s=0`返回x；负shift沿原精确左移。**不是**`(x+half)>>s`，后者half ties固定向上，不是最近偶数。
- 每项F24误差由`[-1,0]`格（左端不取）改为`[-1/2,+1/2]`格，故G项的最坏出口前绝对界减半，且取消必然负向；**不能无分布假设称统计无偏，也不能保证每个共同出口或整网结果更好**。

合法反例（其余实际组可设inactive）：Attention两组total_shift=26、codes=1、dot=507和3，对应F24项126.75与0.75。精确和127.5经共同F24→F16 half-away为码0；原逐组floor和126也为码0；逐组RNE和128输出码1。RNE在此比baseline差1码。CPU证据见[A015_arithmetic_probes.json](A015_arithmetic_probes.json)。

## 2. 负数、shift与溢出必须守住

1. 负数使用floor商和非负余数，`q&1`判断负奇数同样成立。对s=0，不能在TL where另一分支仍计算`1<<-1`；half用safe_s=max(s,1)，inc再显式mask s>0。
2. inactive code0的两个shift仍允许0..63，故伪right可达102。求half、mask或移位前必须把inactive有效shift置0或安全clamp；raw=0并不能令`1<<102`或负位移变合法。不能把inactive的非规范metadata误报为数值失败，也不能用clamp掩盖active非法shift。
3. active Linear右移：Attention2..23；Gate/Up与Down0..20。精确左移最大Gate/Up4位、Down12位。PV active右移0..24，inactive保持0。
4. [guard仅audit](/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/software/0_Software/FPtoQ/experiment/v5_fullchain.py:411)不能另加guard wrap/clamp；[acc逐组有符号wrap](/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/software/0_Software/FPtoQ/experiment/v5_fullchain.py:448)不能改成只在末尾wrap或默默无限精度；[最终出口](/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/software/0_Software/FPtoQ/experiment/v5_fullchain.py:452)仍half-away再sat。RNE组值可能比原floor大1，应原样检查guard和每步acc状态，不能看末端值正常就排除中间越界。

按物理dot bound和code≤255，正负同幅保守上界如下（G分别128/128/448）：

|profile|最大abs raw|最大abs F24组项|G×组项上界|guard/acc正上限|
|---|---:|---:|---:|---|
|Attention|67,386,708,000|16,846,677,000|2,156,374,656,000|2,199,023,255,551 / 同值|
|Gate/Up|4,244,832,000|67,917,312,000|8,693,415,936,000|68,719,476,735 / 8,796,093,022,207|
|Down05|4,244,832,000|17,386,831,872,000|7,789,300,678,656,000|17,592,186,044,415 / 9,007,199,254,740,991|

这些物理上界内，RNE组对齐仍可装入原S42/S37/S45 guard与S42/S44/S54 acc；实现还须核每步audit及数据来源。非物理合成边界仍须按out-of-contract单列。PV乘积abs≤34,208,286,975，K128累加abs≤4,378,660,732,800；QK缩放乘积abs≤811,710,997,730,426,880，均安全装int64。不要先转FP64再把S54累加当精确。

## 3. 4位备用方案及代价（本轮不执行）

在F24+b保留低位，逐项floor后求和，最后half-away右移8+b到同一F16出口。无wrap时：原floor和≤高精度floor和≤精确和，因此同输入、相同单调出口下对固定reference的绝对码误差确定不劣；b=4把截断界缩16倍。但**原acc位宽不变、仅把小数位上移4位会失去动态范围**，上表所有profile的保守acc界均不能保证安全。

保留原完整范围的简单方案需明确内部扩宽：统一保守guard/acc可用Attention46/46、Gate/Up41/48、Down49/58，全部可由软件int64承载（并不等于RTL成本已验证）；或保持原F24主累加器，增加低位侧带，b4/G448时侧带和至多448×15=6720，需13bit，再处理carry及overflow。后一方案保留外部format05/ScaleCode/Hadamard，但内部算法/资源仍有改变，必须单独版本和硬件代价，不能称原内部格式逐bit不变。不把这些备用方案加入当前3策略选择。

## 4. 防止“candidate替换oracle”的验证

- 冻结原[GPUreference exact商余Linear](/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/software/0_Software/rounding_precision/experiment/numerical_reference/gpu_reference.py:23)、[PV exact商余](/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/software/0_Software/rounding_precision/experiment/numerical_reference/gpu_reference.py:183)及其输出规则，分别记录SHA；candidate只来自生产kernel/PV函数复制后的明确RNE改动，不调用candidate作为reference，也不把oracle出口改成逐组RNE。
- CPU gold用任意精度Python integer/Fraction独立重算dot、每组RNE、profile wrap和原half-away/sat；exact节点值与共同出口参考另由Fraction精确和得到。优先核负数tie、s=0、左移、inactive shift63+63、抵消、出口±128 F24半刻度、guard/acc边界；保留上面的“RNE更差”反例，避免测试只奖励candidate。
- GPU小样本须保留同一raw qa/qw/zp/code/shift完整依赖，以及baseline/candidate/reference三种结果；比较candidate与**CPU RNE gold**证明实现正确，再比较candidate/baseline对固定exact与共同出口oracle的误差证明方法效果。这两种比较不能互相代替。
- GPUreference接口与生产grouped_linear_s24同签名，但它移除了有限guard/acc语义（72–102）；不能用直接调用它就得到零误差，声称等位宽纠正成功。其签名含output_min/max、shift范围和5计数器，candidate须保留原宽度与真实计数。
- 保留checkpoint/量化权重、所有LUT/系数、quantizer规则与Host不变，每条完整轨迹仍根据自身激活重算码。不得对最终输出做拟合reference的偏移校正。

CPU探针：106,509组有符号RNE/shift对与`round(Fraction)`一致；65,536个QK四组小整数例中，原floor对固定floor出口最大差3码、RNE最大差2码；240组合法profile数据核4位备用的单调夹逼，未调用candidate或GPU。它们只是算术资格，不是当前工程candidate或真实模型优化成绩。

## 5. last-layer-only与all-layer：回答不同问题

- “第32层”对应layer index31。last1策略要求0..30层输出与baseline逐bit相同，只有第31层预定Linear/PV调用换RNE；这可测最后层新增误差的修复价值，不能清除前31层已经形成的误差。应在pre-finalnorm、finalnorm、logits、TV和Top1全部报告；不能只看有利的最后一项。
- all32作用于误差注入源各层，可能降低累积的方向性偏差，也会改变后续动态码/LUT/clip路径，可能改善或恶化，不能由局部界推导整网单调性。
- 只做Root冻结的3策略：前4开发文档初筛，预定后32开发文档验证，二者IDs不重叠。selection与validation成绩分开，胜者不等于1024正式总体结论；退化/异常/时间全部保留。
- context必须用稳定layer prehook索引31，进入/退出及异常均恢复v5符号/hooks；用实际调用计数核last1仅7个Linear/1个PV（按候选所改项），all32仅224个Linear/32个PV，不得因scope未复位污染baseline或reference。

已知全1024 layer24 P95约0.8184%、layer32 pre-finalnorm约2.4398%、finalnorm约2.8478%、logits约2.20745%，finalnorm/pre每文比值中位约1.0907（Root提供）。它们说明后段与最终norm有数值放大现象，**不能证明最后norm为根因**。本轮应先验区分last1与all32，而不是把整个放大都归给norm。

## 版本边界

- R007合同：保留原3个RNE候选，无额外搜索。
- 当前生产V5 SHA `58a6bb7c769209925bd3bcd9d1a06414b0a25415a46591f70d8efd62db0b9898`。
- 原gpu_reference SHA `a8f4309cb07ec84687903693888602c1fd09fa876d477dcd4c7f488ce4358837`。
- 工程candidate尚未落盘时，本说明不对其代码正确性下结论；待出现后只核符号/shift/overflow/scope关键差异，不重新探索全链。


## candidate落盘后的关键独审（CPU，不构成模型效果结论）

实际核查candidate SHA `3a01f438bb6fb1c8fce899ab7acf3e43ee2e0af197a4d547ce45ef3f596fd2f9`，原始证据为同目录 `A015_candidate_key_review.json`。AST比较确认：Linear只替换对齐舍入段，guard audit、逐组acc wrap、最终half-away/sat均与生产相同；grouped wrapper的AST完全相同；PV只替换guard赋值。inactive有效shift归0，负数商余和ties-to-even、安全half分支符合定义。

实际Torch CPU helper对独立`round(Fraction)`共49,188例（负数、s≤0、最大活动右移、较大整数），0不符；前后均未初始化CUDA。last1静态按`state['layer']==31`选择，context在finally恢复两个符号和marker。此版本关键算术未发现阻断；尚未由本独审核验GPU kernel实际执行、完整overflow计数与runner层prehook调用计数。不能把上述资格当作RNE整网改善的实测结论。
