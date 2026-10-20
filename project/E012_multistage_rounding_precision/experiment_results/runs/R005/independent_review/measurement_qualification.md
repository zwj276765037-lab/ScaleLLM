# R005 扩展测量独立资格要求

2026-10-19，A014，执行前设计审核；没有新增GPU结果。依据是 M005/mlp_and_logit_measurement_extension.md 的“必须补齐的MLP覆盖”“词表输出证据”“最高分词一致率”三节与主控本轮明确的1024文档重新采集授权。旧R004保持原件。

## 必须满足的口径

- 同一篇的当前/参考final norm hidden采用相同位置、相同checkpoint输出头（真实tensor key、是否tied、bias、原dtype和shape均记录），原BF16权重精确提升FP32；head不是另一个重新量化算子。两臂相同4096词表chunk几何/顺序、FP32 GEMM，TF32关闭、autocast关闭，记录实际环境/实现身份。
- 所有T真实前缀位置、全部V词表恰好一次，包含末token对下一词预测，无标签、不构造任务ACC。头部计算不能擅自改成T−1或丢短文本。非有限、漏块、重复块是完整性失败，不筛除后重算通过。
- logits主比较保留共同Host FP32 head的算术。两份FP32 logits提升FP64再求差和能量；全词表稳定FP64 logsumexp给log-probability差。不能宣称该差无head舍入误差，也不拿两臂head误差自动相消作假设。
- 每位置Top1精确tie固定最小词ID、报告全词表tie计数；reference margin为第一与第二不同词ID的logit差，tie时为0。每位置保存最大绝对差、signed差上下极值及坐标、两臂Top1、margin、两臂LSE。每篇覆盖maxabs、Top1一致整数数/实际T及整篇全一致；文档等权均值与全token长度加权micro分别报告。margin>2×同位置最大差仅是共同已算logits上的充分条件，须与实测一致分列。
- 阈值若无独立概率变化预算，不编造达标线；可以报告预列阈值覆盖或经验CDF，文档仍为统计单位。相对L2保留零信号/缺失语义，不能将logit逐项除接近0值。无新ACC/PPL和任务门槛。

## Pilot中的head算术敏感性

仅在预定pilot再算一次同两臂输入的2048词表chunk，主版本仍4096。分别核两臂全T×V的maxabs/RMS、Top1变化和tie变化，并核(current−reference)差的变化；记录实际GEMM环境。切N维块不改数学点积，却可能切换kernel和归约顺序，不能先验宣称bit-exact。非零差不自动判模型算法错误；低margin预测若因chunk变动翻转，应独立披露为head算术敏感性。

## 最小原数组见证

沿冻结15个audit文档，固定token位置[0,T//2,T−1]去重。每位置保存两臂全vocab FP32 logits用于独立复算max/Top1/tie/margin/LSE（约2.94MiB/doc、总约44MiB，不CPU重算全词表head）。此外固定vocab[0,2048,4096,65536,V−1]有效去重，并加入两臂Top1和最大差坐标；后者明确为结果依赖诊断选点，非随机独立样本。保存完整D维两臂hidden及这些vocab对应原始head行，单CPU math.fsum高精度点积与少量精确二进制有理数交叉核对，分别报告当前/参考head计算误差及误差差值。文件、每数组、真实checkpoint切片和被消费全head身份均可追溯。

小head点积核查支持已选点的计算语义，三行全vocab支持三行指标原值核查；其余T位置仍是覆盖/聚合公式身份审核，不能冒称逐值独立复算。正式文档全量统计和15篇原始见证分母分开。

## MLP观察器要求

SiLU使用同一量化LUT/地址/共同出口；shared-path额外误差为零必须与总出口舍入损失分列。门控乘积以相同LUT结果的精确整数乘积为基准，规定S32/F16出口和饱和另计。整个MLP比较固定同一真实入口，两支分别动态重算；残差后比较使用同一second-residual base。shadow观察器必须不改变主current输出、审计计数及动态事件；连续两臂decoder出口不能冒充已隔离MLP误差。

## 当前判断与资源

以上是待验证资格，尚无R005新节点/logits实测结论。A014只用CPU1、无GPU/后代，负责新checker与本目录。原≤128真实token、32层prefill范围保持；不外推长上下文或自由生成。所有必要修复在本轮授权内继续，普通修复不增加逐项批准门。

## 实现静审与CPU checker资格（GPU pilot终态前）

已读冻结MLP `49cd112093c9ec105d8b9eb69645eb77ef39893b8decb68d30924f857068eb23`：observer先捕获未包装前端；同入口shadow直接调用精确Linear后端与原SwiGLU，不经过原module.forward/project_prepared；shadow audit独立。第二残差base由post_attention_layernorm prehook捕获，current局部对照使用同base，真实每臂layer出口核base+branch重建。SiLU当前self/self仅表达同一查表语义，字段已明确不是解析函数近似精度。SwiGLU生产行为是S32溢出拒绝、无饱和clamp；共同出口误差2^-17界仅在合法S24/S32域使用。新增Down整数/Host小raw和whole-branch配对输出小raw分别说明可复算范围。

已读输出头 `dd2e80c12270010347c3460a6526958fe9737265326911d4a2782af2db848e99`：升序chunk的最小ID tie与全局top2合并正确；FP64差和在线LSE、log-prob extrema公式正确，已补两臂LSE和完整final hidden身份。4096/2048 chunk资格只在pilot首文档额外计算，不预设浮点bit一致；原始BF16 tensor消费hash与两臂相同head保证明确，实际FP32 head舍入另由点积见证评估。

R005入口已确认先构造MLP observer再安装旧dynamic包装；current上下文local→witness→MLP，reference arithmetic→MLP，恢复顺序正确。416 MLP与全T×V测量、旧32/384/192覆盖均在document_completed之前完成。旧核心源码和R004原件未改。首pilot四篇development、实际token[128,14,128,128]，formal0；是否只读保持尚待实际旧AT010原数组/统计/动态identity比较结果，不以静审替代实测。

独立checker `audit_extended_numerical.py` 当前候选SHA `36b84d3e27f617e578e7202cfbf3d3f12c86a396f8534fa090f679aaf2e7609a`。本人CPU资格4项PASS/3.392秒，日志`checker_cpu_qualification_v2.log`：手工精确二进制dot、tie/共同平移指标、小BF16 safetensors原权重+块尾全vocab原行、32层小宽度CPU fixture的416 MLP位置。1024个乘积样本和1024个Host样本独立复算；故意改Top1/覆盖/乘积/Host值/缺失行均被拒绝。fixture不属于8B实测，不计入formal1024；无CUDA初始化。

新checker不导入被审数值函数，采用标准库/NumPy、直接读取safetensors BF16字节区域核完整消费hash，选定点用math.fsum及少量精确dyadic整数累加。CLI支持普通`--attempt --output`；后续常驻GPU组可加`--session`及`--core-output`，须真实global completed才作最终审核。薄适配仅/tmp只读引用真实global receipt/launch，不在managed目录创建symlink，不制造每组独立GPU运行事实。该常驻schema接线仍待A016最终接口和真实结果验证，未宣称已验证未来全量运行。

## AT002真实四开发文档终态独审

实际pilot `AT002_extended_mlp_logits_pilot`原生/监督均0，457.664秒、source unchanged、stop=null、自有worker已回收。本人候选checker SHA36b84d3e…2e7609a实际CPU6.720秒完成，证据`AT002_extended_audit_v1.json`与`.log`。4篇development分别128/14/128/128真实token，**formal_eval_documents=0**。

每篇旧32 hidden/384局部/两臂各192动态坐标和新416 MLP、全T×128256词表测量完整；audit doc0全32 hidden独立重算。旧384见证的每个数组身份与已经独审的R003/AT010原件一致，实际readonly基线也核66个hidden/final原数组及4篇全部旧metrics/dynamic身份一致。这支持该有限pilot的新增观察器未改变原轨迹，不泛化为未来任意上下文的无干扰证明。

MLP原值见证：audit doc0两臂32层合计1024个SiLU/门控乘积整数样本、1024个Down S32→Host FP32转换样本独立复算；3584个配对输出spot核所声明配对规则（含Host样本，不重复加成独立N）。乘积精确误差最大7.621943950653076e-6，2^-17条件界无违例；4篇128个current文档×层单元中乘积总出口max达到2^-17，共同出口额外对照为0，两者不混。Down Host实际有非零损失，current记录最大1.52587890625e-5；whole MLP同入口最大相对L2 0.1609121272%，固定残差后0.0904071910%。这些文档×层单元不是128个独立文档。

|开发文档|真实T|全词表相对L2(%)|全T×V最大logit绝对差|最大log-prob绝对差|同前缀Top1一致数|
|---|---:|---:|---:|---:|---:|
|wikitext2_train:28168|128|1.7748053113|0.4872927666|0.5784073923|127/128|
|wikitext2_train:13401|14|0.9880999939|0.2250679731|0.2310754584|14/14|
|wikitext2_train:21735|128|1.5331757803|0.3940014839|0.4606218760|127/128|
|wikitext2_train:15542|128|1.7394339762|0.6824817657|1.0831112431|126/128|

全398个预测位置中的394一致仅为这4篇开发观测；整篇全一致1/4，不是任务准确率，也不作为正式1024结果。它不证明任意输入或自由生成保持一致。

输出头原值核验：完整原checkpoint BF16 head tensor消费hash吻合；选中head原行、两臂final hidden SHA/原件切片及3个预定token的完整词表raw一致。3行的全vocab max/tie/Top1/margin/LSE/log-prob指标独立重算通过。66个完整D维head点积以math.fsum复算，选点单臂误差最大current2.4198174e-6/reference2.7092688e-6，两臂差值中的head舍入最大2.6354533e-6；4个exact dyadic spot核fsum残差最多4.44e-16。以上仅是预定与明确结果依赖诊断点，不能称全词表head舍入上界。

真实4096/2048 chunk敏感性资格覆盖pilot首文档128×128256全部score：当前臂max1.4662743e-5、参考臂max1.4305115e-5，两臂差的变动max2.0027161e-5；两臂Top1翻转和tie-count变化均0。说明本几何分块确实不是bit-exact，微小head算术差单列，不并入位宽舍入解释。此项是已冻结源所产的完整pilot记录与本次静审口径核对；A014没有再次GPU计算第二套全vocab输出。

限定资格结论：新增测量实现/来源/非干扰在上述pilot范围无阻断，可据实成本安排正式常驻采集。整体数值保持结论仍inconclusive；正式1024、分域尾统计、完整最终PNG均尚未完成。未调整数值阈值、未运行ACC/PPL、未改旧证据。
