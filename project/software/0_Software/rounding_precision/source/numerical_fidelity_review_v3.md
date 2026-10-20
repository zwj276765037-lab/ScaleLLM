# ScaleCode数值保真 v3 独立审核

A014；2026-10-19。execution：实现资格、旧输入管线及AT007单开发文档完整32层连续路径已独审。verdict：limited_support_for_measured_numerical_evidence；formal_1024_document_fidelity_unassessed。

本轮仅数值精度，不重跑ACC/PPL，不设任务非劣效门。依据[numerical_fidelity_contract_v3.md](numerical_fidelity_contract_v3.md)逐节点审核exact/current、来源、理论界和文档级统计。此前pilot保留原结论，不能充作v3多节点正式通过。

已通过实际协作消息向A015/A016交付稳定evaluate_node数组接口、共同出口、exact商余表示、资格mask及主/诊断两类误差。已提醒Softmax插值恰半方向、QK有意clip与格式sat区别、Host S32转FP32误差，待实现验证。

## 首轮CPU实现审查：发现与待修

读取numerical_reference/{policy,current_nodes,exact_reductions}.py后，独立单线程微例复现：policy SHA `07196073f6fc622641bd33f8c625d5f20b5820dbc5dcde5ac4f21ffd2e3bd064`、exact SHA `265231fbc49d7ad579a0e15f47eb677bc93c5dae87f170c627ebe3dd6f77d3a9`。合法inactive zero-code组的两个shift=63使exact共同分母变0并产生除零警告；SwiGLU输入0xffffff按生产应规范化为−1却被domain拒绝；Linear提供qa=qw=1/zp=0但dot=0时错误通过，实际dot应32。三个问题已通过消息交A015，普通修复进行中，不将该版本作为数值通过。

另指出Softmax code==65535不等于发生clamp，需实际pre-clamp判据；metric_mask只应标真实输出坐标，不能复制strict-valid而隐藏格式sat；Host input_width配置不可默默忽略。Softmax保守row-length界经代数复核可用，含共同cap距离，实际实现仍待测试。

## R003/AT001文档清单有限审核

原始[manifest](../../../../E012_multistage_rounding_precision/experiment_results/runs/R003/attempts/AT001_clean_document_manifest/document_manifest.json)及prepare_receipt已读：exit0、9.143秒、worker回收、source unchanged。A014核3份train/dev/eval文件SHA和实际记录数，1152个已选cluster ID跨split全唯一；eval1024=web512/news256/reviews256，train/dev各64且均Wikipedia。该事实只是操作性exact-text/URL聚类互斥，不证明iid、语义近重复已排除或全部历史曝光已排除；manifest的限制保留。

1024文档nearest-rank P99为第1014个次序统计量，尾部仅11个；256文档域仅末3个。因此1024不是精确P99的充分性保证，bootstrap的最少20doc显示规则也不是统计充分性门。train/dev记录中的selection_probability=128/624表示两角色union，单独角色为64/624；已通知A016用追加说明修正含义，原冻结文件不动。本轮未核完整43,229来源记录的所有聚类成员，也不称完成全语料独立性认证。

## Root GPU参考模块的CPU张量独审

源`experiment/numerical_reference/gpu_reference.py` SHA `75c9e6c2ad18a8e568b6579f5b0a8333749988a2f3d031cf21d16a4c8085dd75`。静态核Linear固定共同K商余及int64上界、负数half-away、Softmax四种组合与输出mask；参考移除guard/acc限宽后相应production计数应not_applicable，不可报0当作无溢出证明。建议QK/PV把inactive code0的shift规范为0，避免极端零码metadata引发负对齐移位；context若不支持嵌套应显式限制；Softmax中间运算要固定int64，不能让int32 LUT使左移分子溢出。

A014仅CPU1、CUDA_VISIBLE_DEVICES为空、torch.cuda.is_initialized=False，使用独立Fraction复算15个正负ties/邻点、Softmax四组合2108个输出、QK24个输出及PV768个输出，0 mismatch；包括all-mask、single-key、inactive code0 shift63。源在此次核查前后未变。**只覆盖GPU模块可在CPU执行的整数函数，不含Triton Linear执行、不含GPU执行或完整连续模型**；上述静态资格建议仍需工程落实并在新版本复核。

## 冻结版修复闭环与GPU资格证据（2026-10-19追加）

A014独立单CPU线程复算原反例，CUDA未初始化，源码前后SHA不变：inactive code0且shift63+63得到合法0、精确分母1、0 warning；SwiGLU packed 0xffffff与signed −1一致；Linear不符lane的dot拒绝；Host24超域拒绝且界0，Host32共同出口允许int64记录2^31且界64个输出码；结构metric_mask保留饱和坐标，strict valid排除；Softmax真实cap与all-mask区分正确。上述6类原问题在本版闭合，旧失败记录保留。

冻结SHA：policy `43bcf51ec86deb10a5d7e27a6bc3052ed63b9c6fbc9fd8cf2f13f8e4f4c6f921`；exact `f8990e5e82db13d8d41d536e4c350eac53c5a2099786957832d2208477e12551`；current `a5e6c719dc61df325e3bc8b5c3364c7bf911b673523cfdb4889830567c702404`；compat `f459dbd093d40ba39c8183720a26fab01bd4f3e4c42a903a358893ce660b5138`。工程29项CPU测试日志已读，PASS/0.543秒；这是原日志核查，非A014重复执行29项。

澄清上一节时序：GPU模块 `75c9e6c2ad18a8e568b6579f5b0a8333749988a2f3d031cf21d16a4c8085dd75` 已含inactive exponent=0、Softmax int64及拒绝嵌套/恢复marker修正；上一节建议来自更早静态阅读，不能解读为该SHA仍未修复。A014重新静态核差异及finally恢复；此前CPU Fraction独审即该修正版。

[AT003原始回执](../../../../E012_multistage_rounding_precision/experiment_results/runs/R003/attempts/AT003_gpu_reference_qualification/gpu_receipt.json)与stderr核实：native0，6项真实GPU测试全通过，监督墙钟5.248秒，PID210358已回收，source unchanged；覆盖Triton Linear三profile/不整齐tile、RoPE、QK、Softmax四组合、PV及patch恢复。GPU是Root执行，A014未启动GPU。此证据支持所列实现资格，不能替代真实数据上的误差分布或完整连续路径结论。

## 统计及连续路径审阅待闭合项

`run_numerical_fidelity.py::node_metrics`当前使用结构metric_mask，但尚未与accepted/domain相交，也未单列strict-valid统计。未来无效输入可能以被清零后的值进入分母，已发A016普通修复请求；AT004的168输出均valid，故该缺口不改变本次已报数字。主全集须用metric_mask & accepted_mask，strict valid子集及排除数另外保存，不能只保留好样本。

`run_paired_numerical_model.py`已保存每层两臂hidden NPZ，可独立复算；初读版本动态metadata只有hash/shape及程序计数，尚不能独立复算翻转数。已要求未起跑时补保存实际code/shift/zp数组，若已消费则保留该AT限制后续补齐。参考路径取消有限guard/acc后，未填的相关计数须显示not_applicable；值0不可作无溢出证据。连续两臂各自重算metadata，单个开发文档不能当正式1024文档结果。

## AT004旧输入数组管线独立复算

[原始目录](../../../../E012_multistage_rounding_precision/experiment_results/runs/R003/attempts/AT004_array_replay_serialization_fix/)：native0/0.507秒/source unchanged；前序AT002序列化失败保留，不作为数值方法反例。A014校验66个唯一输入/来源/输出artifact的SHA，从原始qa/zp/qw重构全部29,184个有序组dot并核四类metadata重排；随后不调用被审oracle，用Python Fraction独立重算168个current、共同出口reference、exact及逐组guard/acc域和两界，0不符。21张量两类误差能量、信号能量、signed sum、相对L2%、归一化bias%、RMSE、max与原JSON一致，最大浮点显示差3.55e−15。

current/reference相对L2范围0至0.4019672177%；current/exact范围0.0001440268至0.2713609564%。两项最大均为layer0 o_proj的8个选中输出。两误差系列的参考分母与末端舍入不同，因此前者大于后者不是矛盾。范围严格限定为旧BF16轨迹、单个工程文档、0/15/31层各7个Linear及每算子2token×4channel；formal_eval_documents=0，未测其他节点真实分布、未代表完整V5轨迹或1024文档。

[selection_probability_addendum.json](../../../../E012_multistage_rounding_precision/experiment_results/runs/R003/attempts/AT001_clean_document_manifest/selection_probability_addendum.json)已核，正确区分train+dev union128/624与每角色64/624，并明确当前统计不使用该字段加权，旧文件未改。

兼容层另于AT005启动前修复HF5迁移RoPE配置字段问题：`model_compat.py`新SHA `53ef45e269b997bad32d09003bac53a7ccfa9ae006d9e1eecd95e13cb0f23dc0`，以原checkpoint config字典调用未改的生产_rope_tables，metadata留config路径/hash，finally恢复函数，不修改模型config或生产文件。A014已静态核修复；128×64系数一致与4项CPU测试为A015报告，待原始日志随AT核查。该兼容层新版本不覆写上一节冻结身份。

## AT005连续32层开发试跑：仅成本证据

[原始回执](../../../../E012_multistage_rounding_precision/experiment_results/runs/R003/attempts/AT005_paired_32layer_numerical_pilot/gpu_receipt.json)：2026-10-19 03:47:41Z终态，cost_stop、exit124/native−15、295.2269秒，stop_reason=assigned wall budget reached，RSS峰值3,281,264,640字节、自有GPU峰值15,678,308,352字节，PID212013已回收、source unchanged。stage记录只有loading_model、37.960秒model_loaded、attaching_v5，未进入任一forward，未产生配对hidden。因此没有32层精度或动态码翻转结论；这是预算内成本试探，不能反驳/证实舍入精度。

在起跑前，工程已补每事件两臂实际codes/shifts/zp/values_u8或values_s12的NPZ及hash。此代码层补充解决未来独立计数所需接口，但本AT未执行到采集点，不把接口存在写成已有数据。

exact主系列语义再次明确：QK exact含算法有意±16 clip；Linear/RoPE/PV exact在格式饱和之前；Softmax exact在共同U16 round/cap之前、包含endpoint cap误差；SwiGLU exact为同LUT/分支后未round乘积；Host exact为原raw实值。不得笼统称“所有节点均为饱和后的精确值”；QK exact_unclipped若展示，仅作独立诊断。

## 下一装配试跑前：分块与观测器有限审阅

AT006原始`chunked_quantization_result.json`/receipt已核：层0实际q/gate/down三完整矩阵、chunk64/128/256共9组，q/code/shift三个SHA逐项与未分块生产量化一致；native0/25.7403秒、CUDA未初始化、source unchanged。生产`export_scalellm_llama31_artifacts.py:253`的FWHT只沿最后32lane，`:296`权重量化max也仅沿该组，ScaleCode逐元素编码。`chunked_quantization.py` SHA `281c7a5b82f7531b43569d265d76c6779e698f9df790c9427d616a95d60d183e`只切独立输出行，函数调用、每组顺序和输出位置均保留；该机制与9组实测共同支持chunk128不改变每行量化语义，不意味着已比较所有模型权重的实测hash。

LocalObserver静态检查：先执行原current，再用独立shadow audit/count执行同输入reference，统计后原样返回current对象，finally恢复模块函数；不直接调用前端重新量化，故shadow不应增加动态码事件。需要原生开/关输出、输入及current audit一致测试闭合（此前已有fake隔离测试）；RoPE query/key两次调用应按site分开。CURRENT arithmetic_context也会设置活动marker，集成已改为current臂只用observer、reference臂只用arithmetic_context，避免嵌套冲突。

本observer只提供局部current/common-exit reference统计，未提供exact-pre-output或逐输出strict理论界。有限guard/acc的reference计数不适用；不可用未填的0产生“参考无溢出”结论。局部目前仅保存设备端聚合，因此不能声称A014逐元素重算全部local统计；连续hidden和动态码另有原始NPZ可独审。正式采集应增加预定坐标/极值见证及必要输入，用于独立精确spot。

统计双分母修复已独立微例闭合：runner SHA `5e7d949ddc7994254d90aa66b4aee779a87ac498905b4844770968170de6f501`，三坐标中accepted2、strict1、rejected1；有异常但defined的accepted输出保留，主relative L2=98.0580675691%，strict子集=0，invalid清零坐标未稀释分母。源码另写strict_valid_document_summary并保留主全集，两系列仍分开。

### 观测器修复与原生非干扰闭合

冻结observer SHA `b3b2340da40a6ec5c71a50f2e2b218827ebe7e66fa50f2afa517a9f1cfa4a0a8`。A014已核最新源码和`/tmp/A015_local_observer_native_cpu.log`原始日志：8 tests PASS/0.124秒；新增测试对实际生产RoPE/QK/Softmax/PV逐位比较observer开/关输出、完整V5Audit.collect及所有输入张量，全部一致，CUDA未初始化。Linear包含fake原样返回/独立计数指针测试与已有GPU算术资格，但本日志不包含原生GPU Linear observer开/关执行；不扩大其测试范围。

RoPE现按冻结生产query→key次序分query_rope/key_rope，输出site_assignment与pair_complete；reference有限guard/acc以及对应current−reference差值置null并列not_comparable字段，current原计数保留。paired runner亦将reference对应全局/模块计数置null。此前静态待修点已闭合，保留局部聚合不可逐元素独立重算、无exact-pre-output/strict理论界等既定范围。AT007登记本身不代表已有32层结果，仍待原始终态证据。

## AT007完整32层开发文档：独立原始结果审核

[原始目录](../../../../E012_multistage_rounding_precision/experiment_results/runs/R003/attempts/AT007_complete_paired_numerical_qualification/)终态native0、315.1316秒，RSS1,991,843,840字节、自有GPU峰值15,678,308,352字节、PID218508回收、source unchanged。A014核18项消费源码及dev文档文件共19项SHA；文档wikitext2_train:28168、32个prefix token、attention03/mlp05、32层/4096通道、LM head未测、formal_eval_documents=0。两臂第一层第一次前端的code/shift/zp/A8值SHA完全相同；之后各自重算动态metadata，非冻结同码传播。

A014用独立NumPy/数学公式（不调用工程统计函数）从32层hidden NPZ重算4,194,304个标量配对的E/S/signed sum/RMSE/max/relative L2/bias并与tensor JSON和document summary对账；再核384个dynamic NPZ、192配对全部字段的元素变化计数与原SHA。共416个节点/动态artifact hash吻合，所有指标在显示精度内一致；能量求和最大绝对显示差4.66e−10，非数值不符。这些标量不是4,194,304个独立统计样本，N仍为1个文档。

| 位置 | 相对L2误差(%) | 归一化signed bias(%) | 最大绝对误差 |
|---|---:|---:|---:|
|layer0输出|0.259635649|−0.044614739|0.0007171631|
|layer15输出|0.194094642|−0.004272225|0.035980225|
|layer31输出（全32层最大relative L2）|2.178867713|−0.023361628|0.455718994|
|末端norm后hidden|2.390085560|−0.034017476|0.743423462|

最后一行由A014直接从final_hidden_current/reference.npz独立计算，不是已有逐层JSON字段；文件SHA分别`424b7a4a9068595fc1554e3e28f56fe182cd254bc969f05b811c1d3030447aaf`和`b5bcd6ada884df401aad4d9c4f394ddd9d16912d9a71f214886d678e83b10d2c`。这些数字说明局部小舍入误差与完整路径漂移必须分别展示，不能以局部1个输出码界替代全路径精度；本轮未设置事后通过阈值，也不把2.39%解释成已通过或已失败全部目标。

动态实际变化：ScaleCode code646,476/917,504=70.4603%；shift10,047/917,504=1.0950%；zero_point485,861/851,968=57.0281%；A8值18,865,003/27,262,976=69.1964%；KV12值1,862,920/2,097,152=88.8309%。这是编码改变比例，不是相同百分比的实值误差，亦不能由此单独归因某个节点。当前输入及分组尺度随路径变化，与局部同码对照定义不同。

局部384cells=32层×12sites（7Linear、2RoPE、QK/Softmax/PV各1）；A014只由保存的E/S/signed sum重新核聚合公式及site完整性，未宣称逐元素重算这些局部输出。各node族最大relative L2分别Linear0.085330357%（layer0 o_proj）、RoPE0.000584922%（layer13 query）、QK0.004390722%（layer13）、Softmax0.003686279%（layer12）、PV0.029310093%（layer0）。局部是同输入共同出口对照，未含exact-pre-output、未给逐输出strict理论界，SwiGLU/Host独立局部损失尚未由本AT见证。

局部current审计累加与全局相符：列出的格式/guard/acc/sat/前端错误均0，QK有意clip709；reference有限guard/acc明确null/NA，其余列出错误0。QK每层统计32,768个已计算score（含causal mask将屏蔽的未来score），Softmax每层16,896个有效key坐标，不能混用分母，也不能把709直接称为709个有效概率异常。

限定判断：AT007支持上述单开发文档/32token的完整实现与所测数值，暴露末端约2.39%的连续差异；尚无1024文档、128token分布、P95/P99总体结论或全节点精确见证。未运行ACC/PPL，既有任务结果不被本AT重新认定。

## 下一4开发文档见证接口静态审阅

`node_witnesses.py` SHA `d5c5dccfefe7a7cb30dab1322570b17be325033ddd743b4210f7b7af2f6fe049`及工程5项CPU测试原始日志已读（0.373秒PASS，非A014重复执行）。抽样只依赖预定seed、doc/layer/node/site与shape，不读误差大小；16为scalar预选点，RoPE成对和Softmax整row展开后另记实际scalar数。完整Linear qa/qw/zp及G组metadata、QK4×32与GQA映射、PV全部key、RoPE原pair/coeff、Softmax整row/mask/LUT均可恢复CPU数组接口；读取NPZ同时核文件/每数组hash，保留两臂原输出码。

包装仅修改observer实例_record，先原记录再只读切片捕获，返回原结果并在异常恢复；未改模型张量、生产audit或算术。静态未见映射/采样阻断。工程测试包括原生四节点数组重现和Fraction spot、Linear完整lane核查、预算skip可见和异常恢复，但真实GPU4doc见证尚未产生，不能据测试宣布已逐元素独审未来数据。

预算检查在写artifact前执行，含manifest及原子临时文件；预算触顶记录planned/saved/skipped，后层未捕获不得隐去。collector的max_at仅约束witness子目录，不涵盖hidden/dynamic等全AT证据，已提醒Root统一新合同和全局磁盘配额。建议每条Linear另留实际guard/acc/output参数以核profile语义，当前仍以冻结全局attach/source身份为依据。

下一4doc为开发范围/吞吐与见证资格，不构成泛化样本；不据4doc给总体P95/P99置信结论，也不宣称数值保持已证完。SwiGLU/Host未在该见证模块coverage内，清单明确排除。

## AT010四开发文档运行器冻结前独审

已读固定合同`.research-agent/decision_inputs/M005_four_document_numerical_stage_contract.json`与[AT010 source_ready及launch_plan](../../../../E012_multistage_rounding_precision/experiment_results/runs/R003/attempts/AT010_four_document_numerical_development/)。A014单CPU只读重算20个消费源码及2份资格日志的SHA/字节数，全部吻合。`run_paired_numerical_model.py` SHA `94b5a91d0ce90e37ef54d3f56b845d7057f2fcb1a6345850485b4a667b53a08f`；`numerical_model_stream.py` SHA `cb62725a5980c2964532442d32e5f24bafa3e427711ffcd7166a34dd33f85c4d`。当前GPU参考SHA `a8f4309cb07ec84687903693888602c1fd09fa876d477dcd4c7f488ce4358837`与AT007冻结副本逐字相同，未将此前AT003的不同SHA混作本轮身份。

代码证据：stream:73–87一次加载、一次chunk128生产量化装配，核attention03/mlp05后四文档复用同一模型；:91–112按layer采两臂hidden，:113–137按(layer,function,ordinal)配动态数组；:153–186逐文档重置配对状态、同一真实token输入先current后reference，当前臂observer只读shadow，参考臂各自动态重算；每臂核共享buffer对象/存储/version未变。后者不是全部参数内容hash，但与一次装配复用及无优化器/只读前向代码一致，不能写成另做过两套全权重内容逐字比对。

最新保存范围已符合合同：audit doc0全部32层hidden两臂、全部32层dynamic code/shift/zp，values仅0/15/31；其余三篇只保留统计与身份/计数。每篇均单列final norm比较；doc0保存final两臂NPZ。见证预定16个scalar点，单doc64MiB、AT96MiB，完整AT由Root监督限制256MiB/900秒；触顶不得把skip当已覆盖。实际launch_plan固定index0/count4/tokens128/audit0/value-layers0,15,31。工程40项CPU测试PASS/0.582秒及静态token长度[128,14,128,128]日志已读，非A014重复执行；短文不padding、不拼接。

静态未发现本次固定配置的语义阻断。尚待真实终态：源码/输入未变、归属进程回收、实际资源、doc0原数组独立重算与五节点见证逐码复算。运行器虽检查配对字典清空，但没有硬编码每doc32层和每层12局部site的完整性断言；因此终态必须独立核每doc32 unique hidden、384 local cells及每臂192 dynamic坐标，不能仅凭completed标记认定全覆盖。代码允许的参数范围大于本次合同，以本次冻结启动命令为准。

范围仍是四篇开发文档，formal_eval_documents=0；局部聚合仍无全量exact-pre-output/strict理论界，见证也不含SwiGLU/Host。本次静态资格不等于已有四篇数值结果，不提供总体P95/P99置信结论，不运行ACC/PPL，也不宣称多级舍入精度目标已经完成。

## AT010四开发文档终态：整数见证与连续路径独立核查

[AT010原始目录](../../../../E012_multistage_rounding_precision/experiment_results/runs/R003/attempts/AT010_four_document_numerical_development/)的gpu_receipt为native0/374.4033秒、stop_reason=null，PID231065已回收，source unchanged；RSS峰值2,066,853,888字节、自有GPU峰值15,678,308,352字节。A014独立脚本仅用NumPy、Python整数/Fraction和数学公式，不导入生产、被审oracle或工程统计函数；单CPU运行9.502秒，脚本SHA `28c5dfa5a9669b9bec1ffa4b2159cc092af9e67f751a053ab27c49e76e55147e`，临时原件`/tmp/A014_audit_AT010.py`与`_result.json`已交工程追加归档。53,394项断言通过；断言数仅为核查工作量，不是独立实验样本数。

四篇各32个唯一hidden层、384个唯一local(layer,node,site)坐标和每臂192个dynamic事件完整；每层4次A8前端、2次KV12，配对无缺失。第一篇audit doc的32层hidden（16,777,216个标量配对）和final norm原数组独立重算E/S/signed sum/RMSE/max/relative L2/bias，与原记录一致；其余三篇没有全量原数组，限定为原聚合身份、坐标覆盖及公式核查。逐doc的local current计数合计与global current审计一致；此对账不把same-input shadow reference审计混同另一条连续reference路径。

|文档ID（均development）|实际token|末端相对L2误差(%)|归一化signed bias(%)|最大绝对误差|
|---|---:|---:|---:|---:|
|wikitext2_train:28168|128|2.221032779|−0.030294920|0.743423462|
|wikitext2_train:13401|14|1.642959747|−0.035152267|0.623108864|
|wikitext2_train:21735|128|1.755510748|−0.024845037|0.596143723|
|wikitext2_train:15542|128|2.152683280|−0.027531044|0.738361359|

audit doc的32层最大相对L2为layer31的2.036411402%，norm后为2.221032779%；final两臂NPZ SHA为`66ef57d44ddd065cac7617d5d4b6411c779383424e6354c20b5e29e93ed4e2ea`与`16392e2565ab85c93bf6e7eb9976d2ae6bb4dfecb0165365a211c3fd297188a7`。较短文档仍为14真实token，不padding。第一篇与AT007属于同一文档不同长度，不能作为两篇独立样本合并。

见证384/384文件全部保存，0 budget skip；预定scalar点经RoPE成对/Softmax整row扩展为71,936个输出，仍只来自audit doc0。A014独立重建预定SHA抽样坐标，核文件及每数组hash，重算Linear全部622,592组qa/zp/qw点积，并将A8/KV metadata切片与另一份dynamic原件交叉比对（0/15/31还比实际量化values）。所有节点的current按生产定义独立整数复算、reference按Fraction共同出口复算，**两臂逐码均0不符**。此处未复用工程reference函数进行自我验证。

|见证节点|展开输出数|适用理论界输出数|已见最大current/reference输出码差|
|---|---:|---:|---:|
|Linear|3,584|3,584|1|
|RoPE|2,048|2,048|1|
|QK|512|512|3|
|Softmax|65,280|32,297|7|
|PV|512|512|1|

38,953个适用坐标的保守current/exact与current/reference界均无违例。Softmax其余32,983个未来key由causal mask排除，单列而不稀释分母；QK见证仍包含实际计算后可能被causal mask屏蔽的score。QK一个输出码代表2^-14，其余四类为2^-16；Softmax7码约1.0681×10^-4，故不得笼统称“所有节点误差均不超过1 LSB”。这些界只适用于已核假设与对应局部同码算术，不解释全路径2%左右漂移，也不把共同LUT近似损失归给额外舍入。

audit doc全32层dynamic元数据独立变化数：code2,568,097/3,670,016、shift38,213/3,670,016、zp1,901,870/3,407,872。仅0/15/31原始values独审：A8为6,076,743/10,223,616，KV12为504,967/786,432；不能把这两个分母误写成全32层。其余层value变化只有生产记录/哈希，未宣称A014从未保存数组重算。

四篇当前路径列出的guard/acc/格式饱和/前端错误均0；QK有意clip分别17,684/142/17,074/17,542，参考连续路径为17,738/143/17,076/17,517。参考有限guard/acc计数保持null/NA；clip计数包括计算过的未来score，不能直接当有效概率异常。核查时见证54,445,927字节、全AT199,215,348字节，低于对应预算；后续附加图/审核记录另计，不回改运行期记录。

限定结论：实现、同码局部见证和本轮四文档连续数值具有上述可追溯支持；formal_eval_documents仍0，无总体P95/P99置信证明，无SwiGLU/Host独立见证覆盖，无事后万能通过阈值。局部理论界无违例与末端1.64%–2.22%的相对L2差异同时成立；不能据前者宣称全网络精度保持已完成。本轮未执行ACC/PPL。

## R004正式输入计划独审：未运行正式数值

[R004/AT001_frozen_formal_input_plan](../../../../E012_multistage_rounding_precision/experiment_results/runs/R004/attempts/AT001_frozen_formal_input_plan/)仅CPU计划准备，native0/0.806秒、进程回收、source unchanged；无模型推理。初版plan SHA `b70834bc4c18abf9c7b551d8579e6929178eb62f49a47aecfa4c0a0a646aebf5`，消费AT009 stream SHA `8acb1e6dbda89595af285f30b10a0c5a1c7dece98cac41cea0bc03c9531c0b97`。后续正式入口/保存策略扩展需单独记录新身份，不能覆写这次初版资格含义。

A014单CPU独立读取全部1024份NPZ，逐一核SHA/字节数、input_ids/attention_mask/position_ids三键、int64和实际一维长度、mask全1、position0..T−1及词表范围；逐文档核与AT001原文档的ID/源/域/角色/文本SHA/归一化文本SHA/cluster映射及实际文本hash一致。1024个source cluster和1024个token前缀各不重复，合计103700真实token、416短文；未重新分词，也未宣称token原件以外的长期上下文或全历史未曝光。审核脚本最初误用str.splitlines拆开文本内Unicode分隔符，改为JSONL文件真实行迭代后通过；此为审核读取修正，原输入未改，不是实验失败。

15个audit资格由seed2026101903、SHA256(seed:doc_id)模64独立重建，全部一致，分域web9/news2/reviews4。既定域内顺序与2web/1news/1reviews交织独立重建一致，64批×16覆盖1024恰好一次；每批最多一个audit，49批无audit。批内存在第二audit时提前截断的规则仅依赖预定资格，不依赖误差；本冻结清单实际均在16文档边界满足。无audit批可保留全部数值聚合，但不能冒称有原数组见证。

主控提出的raw分层保存可接受，须在正式误差出现前冻结具体ID和层集合：各域首audit为web `c4_official_validation_first10000:6896`（source4）、news `ag_news_test:4667`（source621）、reviews `imdb_test:10960`（source829），三篇全32层hidden；其余12篇audit只存0/15/31及final norm。所有15篇仍all32节点见证16个预选scalar点、all32 dynamic metadata、0/15/31 actual values。初版plan尚未写入这项raw策略，已向Root/A016发送修改要求；入口消费版本待独审。每doc32层hidden统计、384 local sites、final norm与两臂audit均不可因raw缩减而删去。

执行完整性边界：正式入口应直接消费并验证既定token NPZ，哈希失败拒绝，不回退重新分词；批失败保留已完成文档和失败位置，续跑去重且不得静默漏样/补0。每次实际批次和总1024目标完成分别计数，不以首批或审计子集替代正式全体。固定域配额合池仍是描述性总体；操作性cluster/token唯一不证明iid或语义独立，分位不确定性沿既定合同，不把token/层/见证展开数当独立文档数。

### R004/B001正式入口冻结闭合

AT002 source_ready的22个消费源码，以及输入计划、存储附录、阶段合同、测试源/日志、CPU回执共31项身份，A014独立重算SHA/字节数全部吻合。runner SHA `3f979d5f03d6d126e0efad3cf4fe8f5284be6eee7bcb179d7854d999172a27bf`，stream SHA `87d8763defbd215c377efd1a0caf81d289ae274ba6381aa10f096177aea20519`。存储附录SHA `43dd788f2bfd6679332660c5031a100400f96bbd9ad93e95cc522f3b0ce08559`按既定三域首audit ID冻结32层hidden，其余12篇三层；原AT001输入计划未改。

此前两项入口缺口闭合：`numerical_model_stream.py::audit_configuration`强制正式CLI与冻结0/15/31、64/96MiB一致并拒重复层；`validate_document_coverage`在每doc标完成前实际调用，核32唯一hidden、384个准确(layer,node,op)和每臂192个准确动态坐标，拒两臂共同遗漏及重复。无audit批使用nullcontext并显式记录collection disabled；正式分支只加载原NPZ，传入原position_ids，不重新分词/补齐/截短。

工程50项CPU测试PASS/1.088秒与正式入口CPU预检native0/3.124秒、CUDA未初始化、RSS711,680,000字节的原始日志已读，非A014重复执行。冻结CLI仅B001的16篇、1645实际token；代码虽支持最多80篇连续逻辑批合并，但本次启动没有使用该能力。静态无阻断已实际消息通知Root；这不是GPU执行或正式数值结论，须以之后完整回执/原始输出验收。

### 正式文档内max统计冻结补充

按Root明确授权，已在`numerical_fidelity_contract_v3.md`第7节冻结：每doc每类跨所有32层/site的最大relative L2，再跨doc报分位；另有五类384位置总max。统计量等价于全部所需位置的最小非负乘性误差界系数，因此0/0精确相等可单独标记且不施加约束，零参考但非零误差为扩展∞并纳入N，缺失/非法为不可估计而非过滤后取max。原tensor零信号ratio仍null；规则不改运行源或数值分母。

文档内max是一项随机变量，单项rank CI不另乘32；多域/类别/分位联合声明需单独预列family，传播逐层区间另算。固定配额合池及iid未获认证的限制保留。此补充在正式结果产生前完成，已经实际消息同步Root/A015/A016；没有按开发误差定通过阈值，亦不构成正式数值结论。


### R004/B001首16正式文档：限定独立验收（2026-10-19）

[B001终态及独审](../../../../E012_multistage_rounding_precision/experiment_results/runs/R004/attempts/AT002_formal_batch_b001_numerical/independent_audit/)保留原固定脚本、初版generic及最终`generic_v2.json`，不覆盖既有报告。GPU原生0、484.948567秒、worker245181已回收、输入/22消费源未变。最终独立CPU脚本10.086秒完成113632项核查、457项文件hash、16篇全32 hidden统计/384 local/384 dynamic及全部final norm公式；断言/标量数不是独立文档数。

实际逐值独审仅预定audit文档`c4_official_validation_first10000:6896`：32层hidden及final两臂原数组，all32动态元数据和0/15/31实际量化values，384个局部见证文件全部保存。Linear重算622592组qa/zp/qw点积；五类两臂Python整数/Fraction独立复算全部0不符，未导入工程生产/oracle/统计函数。展开72064输出，其中38376适用保守理论界且0违例；Softmax33688未来key坐标按causal mask单列排除。Linear/RoPE/QK/Softmax/PV的见证最大输出码差分别1/1/3/6/1，QK码间距2^-14，其余2^-16，不能统一写成“都小于1刻度”。

该audit文档末端相对L2独立复算1.5015658007872%，归一化signed bias −0.0308099571713%，最大绝对差0.423406124115；全部16篇末端记录范围1.1739466238324%–1.7805607257696%。其余15篇限定为原输入/源身份、完整坐标及原聚合量的公式核查，未冒称从不存在的原数组逐值复算。当前只有16/1024篇正式结果；上述数值是描述性部分结果，无总体尾分位置信结论或万能精度通过阈值。

### 可重复单attempt审计器与有限队列复核

新增本人独占`experiment/audit_formal_numerical.py`，SHA `1b0eae5f16b2b6b7957d319b570c95c5ab918a2bec94b288a3a240ca8773e421`；接口为`python -B audit_formal_numerical.py --attempt <已完成AT> --output <不存在的JSON>`。源仅NumPy、Python整数/Fraction及标准库，CPU1，无GPU初始化，不改实验原件。逐attempt按冻结输入计划与存储策略识别全部audit文档；非audit仅核身份/覆盖/聚合公式。无见证时mismatch/bound-violation字段为null且适用数0，不伪造“0违例通过”。

临时证据结构fixture明确标记`fixture_only=true`，不是新测数据：无audit且无目录、无audit且显式空manifest分别0.475/0.479秒通过；薄3层hidden分支7.487秒通过，同时保留all32见证复算；故意修改非audit文档final norm相对L2被明确拒绝。资格代码和JSON追加于B001独审目录；不把fixture的16行重复算成新正式样本。实际B001最终同SHA重核通过。建议Root每次45秒/CPU1/RSS8GiB有界运行，输出到R004统一analysis目录；未来运行耗时仍由实际回执确认。

队列最终`run_formal_numerical_queue.py` SHA `da6c8046ca4ead82907a86e7895e885d363af8c243fbb9ab2d0dcde3e7d3592f`只读复核无本计划阻断。发现并已闭合partial日志游标、SIGTERM收尾和finalize exec瞬间空argv导致超时跳过kill/无界wait的问题；最终采用精确argv身份重试、可核自身worker发现及Popen自有子进程有界回收，未按GPU占用选择外部进程。工程12项CPU资格PASS/3.626秒日志`/tmp/A016_queue_cpu_review_fix.log`已报告，非A014重复执行。队列仅既定24组1008篇、23400秒及原资源；本静审不声称剩余GPU已跑完。

聚合器修订点已只读核实：要求completed/native0/reaped和全部22消费源+模型身份跨attempt一致；缺失/非法值不丢样；文档内max固定lex argmax与tie_count、对应信号/绝对误差/bias上下文；32层单独selector；partial与固定配额pool不报总体CI。A015已提供B001实际聚合和图，A014未声称另作目视验图。

适用域严格为本模型/版本、最长128个真实token、32层prefill。不能外推长上下文或decode；局部界保留G/K依赖，尤其PV在K≤128的结果不能扩为任意K。五类见证不等于SwiGLU/Host转换独立原始见证全覆盖。无ACC/PPL复跑、无任务非劣效门；局部零违例与连续路径实际百分比误差分别报告。
