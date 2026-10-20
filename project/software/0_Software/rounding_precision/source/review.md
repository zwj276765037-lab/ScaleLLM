# M005 数值设计与独立审核记录

A014；2026-10-19。当前状态：合成R001及BF16真实输入R002的32/128 token局部恢复独审完成；verdict：supported，仅限本文列明的输入和局部数值合同。全模型任务精度仍待对应证据。

以下先保留设计与首批审核经过；当前结论以文末AT002审核判断为准。

已核查活动V5 sha256 `58a6bb7c769209925bd3bcd9d1a06414b0a25415a46591f70d8efd62db0b9898` 的403–457、642–794、1688–1706；guard仅audit、acc逐组wrap、half-away和strict shift拒绝已写入[设计合同](design.md)。旧04/当前05来源不可混写；用户主对照已固定中文名称。

已向A015/A016实际发送JSONL、公共入口和数值/来源双分流接口；普通实现修复按合同连续进行，不新增逐项审批。待审核：独立oracle与生产回放不共享关键算术；边界覆盖/手算反例；精确有理数界；原始逐行和汇总；异常分母；来源身份与资源记录。CPU模型与生产公式一致不替代GPU/RTL逐bit，也不证明模型NLL/ACC。

A016报告历史float组缺q/dot/code/shift及组位置；真实同码重放暂不具备输入。后续inventory与合成结果见下文；历史float组不能称为真实Llama同码恢复数据。

## AT001 合成pilot独立审核

证据：[AT001](../../../../E012_multistage_rounding_precision/experiment_results/runs/R001/attempts/AT001_cpu_local_rounding_pilot/manifest.json)及同目录input.synthetic.jsonl、results.jsonl、summary.json、execution_receipt.json。输入hash `a25af129d9d2ea44925150dddab7404072dcc061ae90376c42fe90c43cabe87b`；逐行结果hash `2bd0235f9cce77923567c7958c4e2a5e6b79c41cb55eb730bb1ae3895b39e02c`。

A014直接读取291输入/291结果，用独立Fraction与整数公式复算，没有导入工程实现。285条可解析oracle与279条当前主输出均0 mismatch；252有效样本按精确D界复算0违例。250输出码相同，2个attention样本差−1LSB，均只有一组；其余36条异常/3条输入拒绝独立分流。exit0、源/输入不变；worker0.105秒、RSS28056KiB。结论：有限合成算术pilot支持合同，不能视为真实模型通过。

独审发现inactive code的非零shift曾被额外排除，V5不据此拒绝；已交A015改为metadata提示。v2另补4096组限制、lane点积核查、精确D恒等式、AST白名单及来源资格。A015报告37项测试通过并保留一次白名单漏依赖的失败日志；实际日志/下批结果需继续独审。AT001尚不包含所有新补字段，保留为首pilot，不改旧证据。

AT002已由A016实际运行完成；303条原始结果的独立复算与结论见下文。

## AT002 数值合同v1补强与多组累积见证独审

证据：[AT002 manifest](../../../../E012_multistage_rounding_precision/experiment_results/runs/R001/attempts/AT002_cpu_local_rounding_v2/manifest.json)及同目录input.synthetic.jsonl、results.jsonl、summary.json、execution_receipt.json和三份A015测试日志。输入hash `2013745767fba05cedc103172d63e64ce2dea5bf28725fb32f8270e4c7b145ea`；结果hash `44c4a58a1de2f8daa0ae2add6455cdddeb1ad3914e7be33efea0985697730af2`。

A014不导入实现模块，逐行独立Fraction/整数复算：303输入/结果；297条精确oracle、291条可输出当前实现、1728组附带lane证据的dot全部一致；288条适用的截断恒等式 `acc/2^24−y*=−D` 全部一致；264条有效域样本按精确D收紧界0违例。36条异常、3条坏输入分流保留，未进入有效误差均值。24个输出饱和、6个active非法shift、3个dot越界、3个metadata越界；本批guard/accumulator overflow为0，其负向分支在独立测试中覆盖，不能把本批0计数视为已观察到这些异常路径。

9个有效样本与仅输出舍入不同，包含：attention128组负见证当前−1/仅输出0；Down448组正见证0/1、负见证−2/−1、抵消见证−1/0；Down448 full_floor_bias为−2/0，最大差2个F16 LSB。后者说明相关的连续向下截断会累积，仍满足本合同确定性界；不可报告“全部≤1 LSB”、无损或白噪声模型成立。

已读取日志：首次AST白名单漏guard依赖造成35测试中18错误，失败日志保留；修复后35测试通过；补正负tie邻点与逐步overflow后抵消/顺序对照后37测试通过（0.542秒）。实现当前guard仅audit、acc逐步wrap、inactive metadata仅提示、精确D及来源资格分离与合同一致。AT002 exit0、source/input unchanged，监督墙钟0.329秒，正常回收worker。

审核判断：**接受AT002在上述合成输入与CPU生产公式回放范围的结果**。SM021局部工具/数值证据已形成；真实模型激活、GPU Triton一致性、RTL一致性及NLL/ACC仍未由该批覆盖。协议之后增加BF16采集分支，不回写AT002旧manifest。当前真实采集版本与资源启动由Root/A016负责，普通修复不增审批门。


## R002/AT001 BF16真实输入采集：资源停止与静态路径审核

证据：[capture receipt](../../../../E012_multistage_rounding_precision/experiment_results/runs/R002/attempts/AT001_bf16_real_input_32token_pilot/capture_receipt.json)及同目录capture_manifest.json、stages.jsonl、capture_stderr.log、input_identity.json、resource_preflight.json。采集源码sha256 `5b944bac2f517a8a1d3926977da1389df7a4f0041a3f3018705f14e981605ed4` 与manifest一致；本次审核只读源码和证据，未启动GPU。

实际终态：2026-10-19 02:44:26–02:44:34 UTC，exit124、worker_returncode −15，因自有worker RSS超过8GiB预算停止；最高观测10,590,232,576字节，GPU自有占用最高15,288,238,080字节，worker187558已回收、源码未变。stages仅到loading_model，没有forward完成、integer artifacts或真实数值行。该次不计为数值成功/失败样本；它反映加载资源路径未满足预算，不能据此否定局部数值方法。预检保留外部PID23186的10056MiB占用；终止代码只针对本次start_new_session创建的进程组。

静态源事实（上述固定hash）：capture_real_inputs.py:198–203以本地checkpoint、AutoModel、BF16、eager attention加载；:208–236注册0/15/31层全部7个Linear的pre-hook，取batch0的token0/31，eval/inference_mode/use_cache=False，无任务打分；:254–300用生产checkpoint的输出通道[0,1,63,last]、完整128/448组，经exporter.quantize_folded_rows与v5.fp_to_fixed_raw/prepare_fixed_activation生成码。Down输入S32/H35，其余S24/H27；权重W8/W4、真实切片与q/code/shift/lane证据均计划保存。provenance明确trajectory=bf16、source_format_id=null，另列局部adapter目标格式，未冒称05完整生产轨迹。

单个first64.jsonl第0行prompt只代表固定提示的首末位置和所选通道。input_identity冻结32个token及全1 mask；未全量哈希checkpoint，当前只有metadata、选中切片与源码身份，不提升为全checkpoint内容认证。代码尚未实际产生捕获值，不能从静态函数调用声称真实输入已验证。建议后续新AT记录hook原始dtype/device/shape与实际Llama实现hash，继续常规加载修复，不新增逐项审批。


## R002 32/128 token真实BF16输入与局部恢复独审

来源分别为[32 token采集AT002](../../../../E012_multistage_rounding_precision/experiment_results/runs/R002/attempts/AT002_bf16_streamed_32token_pilot/capture_manifest.json)、[32 token回放AT003](../../../../E012_multistage_rounding_precision/experiment_results/runs/R002/attempts/AT003_cpu_replay_bf16_32token/manifest.json)、[128 token采集AT004](../../../../E012_multistage_rounding_precision/experiment_results/runs/R002/attempts/AT004_bf16_streamed_128token/capture_manifest.json)、[128 token回放AT005](../../../../E012_multistage_rounding_precision/experiment_results/runs/R002/attempts/AT005_cpu_replay_bf16_128token/manifest.json)。审核时AT003/004/005为真实raw证据，A016报告共享管理登记待Root恢复后补；本文不替代登记或声称已登记。首次AT001的资源停止保留，不计入数值分母。

来源事实：capture_real_inputs.py:127–203的新流式加载逐tensor关闭CPU映射，实际LlamaModel全部290个base参数为BF16，RoPE buffer为FP32；:297–321在真实forward的Linear pre-hook记录原dtype/device/shape，保存首末token输入及已加载权重行；:346–370对checkpoint原始权重切片与GPU所用行逐值核对后保存NPZ。:383–395明确BF16轨迹/null source_format_id及独立adapter目标。加载日志记录15,009,849,344字节base参数的逐tensorSHA及聚合身份，两长度相同；A014独立核对290项key/shape/dtype/extent与safetensors头、聚合hash自洽性，并独立读取84个选中原始权重行。A014未重读全部15GB张量body或做全模型GPU前向复现，因此不称全checkpoint文件或全部GPU参数逐字节独立认证。

A014独立复算仅用Python整数/Fraction、NumPy与safetensors原始头/小切片读取；未导入生产oracle、replay或量化函数，设置BLAS/OMP/MKL/NumExpr各1线程、CUDA_VISIBLE_DEVICES为空。H32采用独立符号矩阵，激活nearest-even与最终half-away分别按商余数计算。每个长度分别核对21个NPZ、84个checkpoint权重行、7296个激活组、14592个权重量化组、29184个lane点积和168个精确恢复输出，全部一致；每批24个source_files的实际SHA均匹配。逐样本group自然顺序、token行/通道定位、qa/zp/qw、ScaleCode、精确oracle、−D恒等式、G_right/nonzero计数、四种误差界和summary的均值/max/P99/同码直方图均独立核对。

两个长度各168行数值合法，无舍入界违例；独立检查FP→fixed、Hadamard及scale异常、active shift、dot/raw/guard/逐步acc越界、两个对照输出饱和均为0。以下同码率只是两个数值路径的输出一致性，不是模型任务准确率。两次同一prompt首位置有重叠，不合并成336个独立抽样。

|序列长度|同码/168|当前−仅输出 = −1 LSB|attention / gate-up / down差异数|最大当前−exact绝对误差|
|---|---:|---:|---|---:|
|32|117|51|17/96；13/48；21/24|1.3655118942260742 LSB|
|128|115|53|25/96；9/48；19/24|1.3518400192260742 LSB|

两个主对照最大差均为1 LSB；这不能改写成对exact最大≤1 LSB。32 token相对exact的signed mean为`−28844472491/5910974510923776`、max absolute为`1431843/68719476736`；128 token对应`−1316938137/246290604621824`与`1417507/68719476736`（以上均为实值，1 LSB=2^-16）。持续向下截断与观察到的负偏置一致，不使用独立白噪声假设，也不以此单prompt估计全域偏置。

原始身份：32输入SHA `7c7f307ef6098fdec21f387684ed0ed2737dab37fec72137045359533ced2085`、results `5894a82a10efd4176a1240dec6df74f04fee4c9dcc6de767461ac2d28548dd65`；128输入 `a23b012ebf3c0185167436ade8802b96e7fa6c5bccb234c4abe646d7e808b548`、results `d5593f6ed527d66fa5d99f49513208e9e8f39847af3955bf2e3b8a4112c4c23c`。32采集使用runner helper SHA `6d128c03...`，随后CPU回放及128采集使用`00710ddb...`；A016说明变更限于实际source hash校验后更新资格状态，oracle/数学未改。各receipt均source_unchanged，属于尝试间版本边界，不误报为运行中漂移。

运行终态：32采集45.834秒、RSS2,101,694,464字节、GPU15,504,244,736字节；128采集45.343秒、RSS2,056,790,016字节、GPU15,504,244,736字节。均exit0、自有worker回收、无预算停止。CPU回放分别1.212/1.259秒，exit0/source与input unchanged。审核没有使用GPU。

判断：接受两批在所采真实BF16输入及固定生产局部量化码条件下的Linear恢复结果。只覆盖同一prompt、0/15/31层、每算子首末token×4输出通道；虽每行包含完整128/448组，仍不能代表所有输入、全32层或V5生产轨迹。source_identity_status verified仅证明所列文件身份，eligible_current_format_evidence仍false。此证据不证明GPU Triton/RTL逐bit一致，也未执行NLL/ACC。若进入传播/任务阶段，仍须正式数据前冻结有依据的δ及匹配协议，不能沿用整体BF16误差容忍度作为额外舍入限值。

管理状态后续更新（2026-10-19）：Root已补齐R002/AT002–AT005四次登记，状态均为completed，registration_pending.md追加已解决记录并保留原文。上文“待登记”描述仅指独审当时的历史状态，不代表当前状态。本项管理完成不扩大数值验收范围。
