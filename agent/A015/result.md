# A015 最新交付：completed；全目标判断：inconclusive

本节覆盖下方历史阶段的running状态。A015已完成独立参考、局部观测/见证及正式后处理实现；当前收尾交付为B001真实16/1024篇的聚合、overview_v2和report_v2。完整1024目标尚未闭合，完成角色交付不表示“精度保持通过”。

- [B001实际聚合](../../project/E012_multistage_rounding_precision/experiment_results/runs/R004/attempts/AT002_formal_batch_b001_numerical/aggregate_v1/formal_aggregate.json)：partial16/1024、missing1008，网页8/新闻4/影评4。15项CPU聚合测试通过，实际覆盖与身份检查通过。
- [易读概览overview_v2](../../project/E012_multistage_rounding_precision/experiment_results/runs/R004/attempts/AT002_formal_batch_b001_numerical/overview_v2/formal_numerical_overview.png)：中位数/95%描述分位带，非置信区间；保留v1，v2统计值未改变。
- [用户报告report_v2](../../project/E012_multistage_rounding_precision/experiment_results/runs/R004/attempts/AT002_formal_batch_b001_numerical/report_v2/numerical_report.md)：实际使用A014最终generic_v2资格；展开72064、理论界适用38376、排除33688分别计数，原始结构掩码与accepted异常输出分母规则已纠正。

最终冻结源码身份：
- aggregate_formal_numerical.py：b544f3ae5160cd3d4d7fce670f5d9196cfe4043a66109e9b1e12edcc6b2becbd
- plot_formal_numerical.py：ca4cd7c5d55c2b6aaeb5496564d7b8f64945fddb5e74dda1b2ba11f1829f609a
- write_formal_numerical_report.py：6ec5b56228c2db0aa70684d00dceffb79010c3af9bb46917f782446526a0fcd1

report_v2使用实际source/numerical_fidelity_contract_v3.md理论合同及其SHA；完整报告要求全部1024/512:256:256、显式25份generic独审与对应attempt/doc集合、15个预定raw审计匹配。报告不把执行成功、0码错或0适用域违例改写为精度验收；条件域内CI、固定配额合池仅描述及SwiGLU/Host覆盖缺口均保留。

最终B001 overview_v2 PNG SHA：dbea939fc1e758784ee07a781d883a4e7b2434997a77945e36c9bf1e02d0f9e8。
最终report_v2正文SHA：16ca86cb7a6d7caeb5e26ea87d13b0e800fa46c39ef7d5c7248a11f1d0a72da9；summary SHA：b92aa0f9a2ddf2a65443563da1c55e08c8a534c491719b2393a879e8116e4fb1。原始资格日志：/tmp/A015_formal_aggregate_cpu_v3.log、/tmp/A015_B001_formal_v2_checks.log、/tmp/A015_B001_report_v2_qualification.log；持久产物含source/output身份manifest。

按Root交接，Q001后台队列负责其余1008篇和自动后处理/最终报告。A015无持续监控声明、无GPU或后台实验进程。当前仅更新自有agent记录及标准控制台状态，不修改冻结源码、计划或共享正文。

以下为历史交付记录，适用其各自版本和当时阶段，不覆盖以上最新状态。

---

# A015 阶段结果：首版数值实现

execution_state: running
verdict: supported_with_scope
applicability: M005/SM021，固定整数码Linear恢复级CPU；生产GPU/RTL未运行，真实模型精度未覆盖。

已实现 `project/software/0_Software/rounding_precision/experiment/{exact_oracle,production_replay,metrics,linear_recovery}.py` 及三个数值测试文件。独立oracle为任意精度整数共同二进制分母；生产回放有界提取活动V5 kernel AST，guard只审计，acc每组回绕，末端half-away及S24/S32饱和。整数分数以十进制字符串保存，signed误差、LSB、G_right及异常分母分别返回。

实际CPU测试命令：
```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 -m unittest discover -s /home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/software/0_Software/rounding_precision/tests -p 'test_*.py' -v
```
结果：2026-10-19，29 tests PASS，0.444s；含本A015 21项及A016 8项。运行日志 `/tmp/A015_tests_20261019.log` 已交A016保存到AT001。初次测试产生Python3.14 bool~弃用告警，已经将tensor bool补码在AST标量化阶段按逻辑not适配；新测试无告警，源码生产未改。

测试内实际覆盖：300任意精度Fraction差分；320 MLP多组对活动mlp_fixed helper；180 attention逐lane对fixbit_v2 helper；600合法合成样本通用及收紧界无违例。以上是测试内确定性迭代，不冒充外部真实激活实验。

剩余：新落盘v1协议的4096组限制、lane_evidence可选核查、D精确tight界、来源证据资格细节待补；A016已获稳定首版接口并开始AT001，补丁将在其冻结消费完成后写入新版本，不覆盖首AT。A014独立审核待完成。

## v2 协议补强与修复

完整命令同上；实际新一轮35 tests PASS，0.515s，日志`/tmp/A015_tests_v2_final_20261019.log`已交A016保存在新AT。首轮白名单缺少guard依赖导致18 errors，保留`/tmp/A015_tests_v2_20261019.log`并修复；未改数值容差、删样本或生产源。

已完成4096组上限、可选lane证据独立dot/范围检查、D精确截断损失及tight界、截断恒等式检查、明确AST白名单和约分oracle；共同分母证据保留common_numerator/common_denominator_bits。来源静态判定永不自行授予当前生产轨迹证据资格，需runner真实哈希核查。

A014独审纠正：V5对inactive零code不检查其total shift，非零shift只移入metadata_hints；v1异常资格与v2不同，须用新AT重取最终分母。A016已获稳定v2接口，AT001原证据不覆盖。

源码身份（本次记录时）：
- `project/software/0_Software/rounding_precision/experiment/exact_oracle.py`：`a98128643201475725b80193facb7bdc0318b0b692e4cf732e54a7d788ead557`
- `project/software/0_Software/rounding_precision/experiment/production_replay.py`：`c68930e6e3ec1c34c991dfc7fdd8d05a5a5995626c9281265961b5cb75df7999`
- `project/software/0_Software/rounding_precision/experiment/metrics.py`：`dc7a3c68255ebb711dd346ae0a72fb3751e09fa5b4f2436b9aa1a194c015d2e8`
- `project/software/0_Software/rounding_precision/experiment/linear_recovery.py`：`bfb7460d2c5b742bc90bee611001808dc6d145b5beb6e5901bc71b8bea1bb11a`

## 显式定向补测完成

完整整合37 tests PASS，0.542s，日志`/tmp/A015_tests_v2_complete_20261019.log`交A016。新增三profile当前末端±half及相邻F24码；130个最大合法正项后130负项最终输出0但逐步overflow计数2，交替顺序同项集最终0且overflow0，防止仅检查最终值漏掉异常。数值四模块未改，AT002冻结后保持稳定。

## 真实采集生产函数与环境只读核查

Root授权只读协助A016 capture，未修改其文件、生产代码或旧工程；未载入8B模型。

配置解释器 `/home/user/anaconda3/envs/zhouwenjun/bin/python`：Python3.10.19、numpy2.2.6、torch2.10.0、triton3.6.0、safetensors0.7.0、transformers5.3.0。以CUDA_VISIBLE_DEVICES为空、BLAS/OMP1线程执行实际生产模块import和tiny CPU探针；exit0、实际工具墙钟1.6343s、torch.cuda.is_initialized=false。未调用GPU查询或GPU算子。

生产导入与参数：
- `model.export_scalellm_llama31_artifacts.quantize_folded_rows(source_out_in,weight_bits)`：Attention=8，MLP=4。float32 H32折叠、以decoded ScaleCode作除数、weight half-away，W8范围[-127,127]，W4[-8,7]。不得换旧rawscale/nearest-even QDQ。
- 同文件`encode_scales`保持positive half-away；实际200.5×2^-20→code201/shift20（nearest-even会产生200）。signed round_away实际[-2.5,-1.5,-0.5,0.5,1.5,2.5]→[-3,-2,-1,1,2,3]。
- 活动`v5_fullchain.fp_to_fixed_raw`从host FP32执行half-away到F16整数；`prepare_fixed_activation`需传真实raw，非Downinput_width24/hadamard_width27，Down32/35。H32乘11585/65536后half-away；activation ScaleCode/zp/U8使用nearest-even。
- format05显式flags：strict_total_shift=True、software_extended=False、down_shift12_candidate=True、down_output_width=32。末二者必须同时给出；格式ID本身不足。

探针权重为deterministic float32 4×64（linspace[-0.31,0.27]），4/8bit分别比较完整量化后选rows[1,3]与先选rows再量化，q/code/shift全部逐项相同。支持按目标output rows有界量化；仅证明该实际样本和源码按row/group独立的接口，不声称所有硬件/环境边界均已证明。activation同一32lane S24/F16输入重复调用完全相同，code184/shift18。

必要来源边界：BF16轨迹上套生产局部前端仍只能标bf16_trajectory_local_replay；当前格式真实生产轨迹须从V5的PreparedActivation和真实weight buffers采集，并保存同一权重制品及prompt/tokenizer/Host dtype身份。

采集接口源 `project/software/model/export_scalellm_llama31_artifacts.py` sha256=`689ddf269ff951e437cc3232c5b544b461e4a0b2ff737e21f69e2f93b8f2a300`。

采集接口源 `project/software/0_Software/FPtoQ/experiment/v5_fullchain.py` sha256=`58a6bb7c769209925bd3bcd9d1a06414b0a25415a46591f70d8efd62db0b9898`。

## 真实回放图表预案（仅设计，尚未绘图）

Root授权等待真实结果落盘后再执行。首图按七op分面，横轴离散层0/15/31，不连成32层曲线；纵轴固定“当前实现 − 仅输出舍入 (F16 LSB = 2^-16)”，使用output_code整数差。每点为一个真实输入输出标量（n=1），保留sample_id/token/row/channel及G、G_right、理论资格；每组标n_valid/n_captured和异常数。strict拒绝没有出口码，不能补0；out_of_contract放独立面板/计数，避免混入有效域统计。

有多样本时可补同layer×op ECDF，n是有效输出标量数，说明同prompt相关；单样本不画箱线或置信区间。来源写“真实BF16轨迹输入的生产局部恢复回放”，不冒充05全模型/生产全链轨迹。合成样本不进真实分布。微型探针证据与生产函数/flags已通过原生collaboration发A016和Root，无新增审批门。

## 本轮交付状态

execution_state: completed
stage: 授权的数值实现、CPU测试、采集接口只读核查与图表预案已交付
review: A014独立审核及Root最终整合仍待；本完成只指A015本轮交付
next_step: 待Root或A014新消息后联合修复；真实图表未执行，GPU/RTL/全模型评测未运行

未留运行中的实验进程，未更改正在消费的冻结数值源。

## 接续：资源失败后的逐张量加载独立核查

Root限定授权：只读库和A016 capture，/tmp独立小CPU验证；无GPU初始化，不改capture。原HF5.3 from_pretrained整批路径RSS超8GiB属于资源失败，未取真实样本，不反驳数值方法。

本地Accelerate1.13支持init_empty_weights(include_buffers=False)及set_module_tensor_to_device(value=...,dtype=...,non_blocking=False,clear_cache=False)；AutoModel.from_config(dtype=bfloat16,attn_implementation=eager)只初始化meta参数。每parameter单独safe_open CPU句柄，阻塞放置后删除全部value/view再关闭；不得长期保留整个shard state_dict或mmap句柄。LlamaModel基础权重名去checkpoint首个model.，只允许跳过lm_head.weight并校验完整base keys。两个RoPE非持久buffer inv_freq/original_inv_freq不在checkpoint，构造时保留真实CPU FP32，随后移动并保持dtype。基础AutoModel没有LM head alias，无需为此改用ForCausalLM；不能用meta data_ptr=0推断tied关系。

实际独立调用A016加载函数：
```bash
CUDA_VISIBLE_DEVICES='' OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/user/anaconda3/envs/zhouwenjun/bin/python /tmp/A015_verify_stream_loader.py
```

最终原始log：`/tmp/A015_stream_loader_verify_final.log`；脚本sha256 `b7ecf970b7eee0f7f3a0ecb9ee5d276e6abed1c8d3bfbc5675f694884d0598fe`。三种2层tiny sharded Llama checkpoint（untied+head、tied+head、tied且省略head）各20个base参数全部逐元素/形状/BF16一致；两个FP32 RoPE buffers完全一致；选定q_proj行原始字节相同；5token forward torch.equal完全相同；CUDA始终false。最终exit0、过程约4.77秒、测试计算0.3362秒、maxRSS794200KiB。

实际被测capture SHA256 `069040ad1a8904d03fa1150e9db160bd17331275c07b549e017297a1e87e1023`，测试前后unchanged；同hash源码的全tensor消费hash使用memoryview(...).cast(B)而非tobytes大复制。首次独立脚本传torch.device与函数str接口不符致JSON记录失败，改脚本传cpu字符串后通过，原失败log保留`/tmp/A015_stream_loader_verify.log`；中间2case通过log亦保留。

脚本及全部log已发送A016，并由其入新AT preflight（先前2case版本与最新3case分名保留）。以上只证明tinyCPU加载/数值语义，不保证8B GPU RSS或速度；A016按原预算启动新AT真实测量，A015不干预其进程。

execution_state: completed
next_step: 待联合复核消息；未修改冻结代码或新增采集/评测范围。

## 论文级工程方案交付

execution_state: completed
artifact: project/software/0_Software/rounding_precision/source/paper_precision_implementation.md

交付：完整V5减位宽节点/已测与缺失表；HF5.3兼容缺口；同权重同基础量化/近似函数的六开关接口；Linear/QK/PV int64精确商余、RoPE精确乘加和Softmax同LUT有理归一化；FP64适用域与Host特殊边界；全32层单点/族/全注入两轨迹方案；分级成本与流式GPU统计+分层任意精度审计。

本轮仅CPU1线程内的只读源码审核及新文档，无数值实现、测试实验或GPU运行。已通过原生消息给Root与A014回传关键缺口及文件路径，不把设计稿当验收或新实验。

## v3：纯数值参考实际实现

最新用户范围移除ACC/PPL/任务非劣效；历史设计中的任务计划不再作为本轮执行范围。实际新增四模块：policy.py统一NumPy evaluate_node(node,arrays,config)；exact_reductions.py向量int64商余/有理归一化；current_nodes.py活动V5 CPU/AST路径；model_compat.py HF5几何/mask/cache/tuple和attach上下文。六开关有selected_code，固定current_code/reference_code两臂不混同；SwiGLU/Host共同出口主差0但对exact误差仍保留。

精确值编码：(quotient_floor+remainder/denominator)×2^-fractional_bits。current路径不调用exact舍入helper。理论界分数在output LSB单位，metric_mask只表示真实坐标，valid另扣domain/overflow/formatSat；QK函数clip和Softmax endpoint cap不作格式故障。Softmax粗界由A014确认：current/exact≤(K+5)/2 LSB，current/reference≤(K+4)/2，bound_kind=conservative_row_length。

已修独审反例：inactive code0 shift63+63使二进制分母溢出（现k0）；SwiGLU零扩展S24负payload规范化；Linear可选lanes范围/dot复算；Softmax实际pre-cap predicate；metric/valid分母独立；Host24/32显式输入与0/64LSB界。

CPU命令（全新pilot）：
```bash
CUDA_VISIBLE_DEVICES='' OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/user/anaconda3/envs/zhouwenjun/bin/python -m unittest discover -s /home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/software/0_Software/rounding_precision/tests -p 'test_numerical_*.py' -v
```
最终29 tests PASS/0.543s（A01514+A01615），log /tmp/A015_numerical_v3_freeze.log已交A016；含独立Fraction、native CPU QK24records、Softmax48×128直接差分、tiny两层HF5 decoder位置/mask/cache/restore。Root接续GPU资格实际6tests通过属于Root证据，A015未执行GPU。

### 真实paired接入的只读审查与小修

查到HF5 AutoConfig.to_dict只有rope_parameters，生产_rope_tables旧接口实际KeyError rope_theta；原checkpoint config字典可生成128×64表，CPU实测CUDAfalse。AT005尚未启动，Root授权仅改本model_compat。新attach上下文以原config dict桥接未改变的生产_rope_tables，退出恢复，HFconfig不动；metadata追加原config路径/SHA。4compat tests PASS/0.264s，cos/sin所有128×64字节相同、正常/异常restore；log /tmp/A015_numerical_rope_bridge.log已交Root/A016。source重新冻结，不触碰生产或A016。

paired runner核查：base为AutoModel+Identity head；动态layer prehook和arm分离ordinal正确；audit清global/linear/min/max；新GPU kernel仅写output/counter，未见权重改写；buffer ptr/version guard是身份/版本检查，未冒充完整内容hash。原checkpoint reader只缓存header，BF16转换逐tensor返回独立float32，不是缓存整shard map。后续可加activation values_u8/values_s12翻转计数，现动态统计仅ScaleCode/shift/zp，此建议不阻断首costpilot。

当前四模块冻结身份：
- `policy.py`：`43bcf51ec86deb10a5d7e27a6bc3052ed63b9c6fbc9fd8cf2f13f8e4f4c6f921`
- `exact_reductions.py`：`f8990e5e82db13d8d41d536e4c350eac53c5a2099786957832d2208477e12551`
- `current_nodes.py`：`a5e6c719dc61df325e3bc8b5c3364c7bf911b673523cfdb4889830567c702404`
- `model_compat.py`：`53ef45e269b997bad32d09003bac53a7ccfa9ae006d9e1eecd95e13cb0f23dc0`

execution_state: running
stage: 四模块已冻结给Root/A016真实回放，待首paired costpilot联调
review: A014独立审核持续；正式全层/多文档数值目标尚未完成

## current轨迹局部GPU观测器扩展

新增独占 `experiment/numerical_reference/local_observer.py` 与 `tests/test_local_observer.py`；不在运行中的AT005消费清单，未改其四模块或A016/Root源码。SHA256 `a6f6c88c6cc69139e165028cf8123ff610d18c1476c9cf2c75d28065fc46756b`。

包装活动V5五个函数（Linear/RoPE/QK/Softmax/PV），每次original current后以相同输入运行gpu_reference输出一次共同出口，独立shadow audit与Linear counter，唯一返回原current tensor继续传播。支持doc/layer回调和operation标签；默认临时patch project_prepared读取op_name。禁止嵌套arithmetic_context，结束/异常恢复所有符号与类方法。

GPU设备内累计count、signal²、diff²、signed diff、max_abs及current/reference/delta审计。文档边界flush才同步sink。metric坐标只剔Softmax结构mask/padding，不用聚合异常推断逐output严格域；scope明示all_accepted_real_coordinates。reference为共同出口码，不冒充exact舍入前参考；零signal/空分母相对指标null。

CPU命令：
```bash
CUDA_VISIBLE_DEVICES='' OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/user/anaconda3/envs/zhouwenjun/bin/python -m unittest discover -s /home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/software/0_Software/rounding_precision/tests -p 'test_local_observer.py' -v
```
最终6tests PASS/0.111s，CUDAfalse；fake-source验证counter隔离、signed统计、回调分doc、真实current对象identity、context恢复；另只读导入真实native/backend做keyword签名兼容核查，未调用GPU。最终log `/tmp/A015_local_observer_cpu_final.log` 已发送Root；首轮5fake tests日志保留。GPU实际observer资格与大型采样尚未运行，由Root按后续新AT执行。

execution_state: running
stage: 局部observer代码交付稳定，AT005冻结中仅待联调消息

### observer 原生 CPU 非干扰资格与最终冻结

后续版本保留前述6项测试边界，新增原生CPU与RoPE分站位测试；本次版本不得和初版SHA混用。最终 `local_observer.py` SHA256为 `b3b2340da40a6ec5c71a50f2e2b218827ebe7e66fa50f2afa517a9f1cfa4a0a8`，`test_local_observer.py` 为 `311dad3cfe645ac014d8e4454cd6c5c2875be67a8be1802078761f059f83482b`。

沿用上方单线程、禁CUDA命令，实际8项测试PASS / 0.124秒；日志 `/tmp/A015_local_observer_native_cpu.log`（SHA256 `cb453730d66ade442cddf9d81468b515eb902d29443c0aadc7015e3b97df2ac7`）。实际V5 CPU RoPE/QK/Softmax/PV分别验证observer开/关输出逐位相同、完整current audit相同、输入tensor未改变；使用真实gpu_reference的CPU张量路径，`track_linear_modules=False`，CUDA未初始化。Linear GPU内核非本测试范围，仍以Root真实GPU资格为准。

默认RoPE按冻结生产query→key次序拆为query_rope/key_rope，flush记录站位推定方式和偶数配对完整性；显式operation标签可覆盖。reference guard/acc属于更宽算术的不适用审计，其reference值和差计数为null，保留current原始计数，避免将零误当可比结果。

已向Root、A014、A016发送原始日志与版本身份；新observer源码停止编辑供AT007冻结。原AT005消费四模块未修改。此CPU资格不等于真实GPU吞吐或32层局部数值采样完成。

## 五节点同输入见证文件扩展

Root授权新增且独占 `experiment/numerical_reference/node_witnesses.py` 和 `tests/test_node_witnesses.py`，不修改运行中AT007的18个消费源。实际新增 `NodeWitnesses(directory,audit_doc_ids,samples_per_coordinate=16,seed=...)`，其context只临时包装observer实例的 `_record`，保留原回调返回、输入、结果tensor和计数器，正常与异常退出均恢复。`load_witness`校验NPZ和逐数组身份后返回现有CPU evaluate_node输入、config和两路保存码。

预指定audit docs，逐doc/layer/node/op首call确定性取点；16指scalar输出点（首尾边界加SHA256 seed内部点），不依赖误差。RoPE展开成完整pair，Softmax展开成完整row，分别保存计划点/去重unit/实际scalar数量与原flatten坐标。Linear保存所选row/channel的全部G×32 qa/qw/zp及scale codes/shifts并独立重建dot；QK保存全部4×32 query/key和KV元数据；PV保存完整K的prob/value/scale；Softmax完整LUT，RoPE完整所选pair及coeff。

manifest保留source文件SHA、NPZ/每数组SHA、原shape/坐标、共同出口定义、planned/saved/skipped、byte_budget和预算；默认单doc64MiB、AT256MiB，写artifact前含manifest原子暂存的保守容量检查。触顶后层仍显式记录skip，元数据本身不足则显式失败，不冒充已保存。样本含定向边界，明确非IID；不使用误差极值；覆盖仅Linear/RoPE/QK/Softmax/PV，不宣称SwiGLU/Host或全链所有误差源。

CPU单线程命令：
```bash
CUDA_VISIBLE_DEVICES='' OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 /home/user/anaconda3/envs/zhouwenjun/bin/python -m unittest discover -s /home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/software/0_Software/rounding_precision/tests -p 'test_node_witnesses.py' -v
```
最终5 tests PASS / 0.373秒，CUDA未初始化。实际CPU四节点+同输入gpu_reference CPU张量路径所存见证由evaluate_node逐码复现；五类均有独立Fraction spot；另覆盖选择稳定性、GQA/layout、完整lanes、doc白名单、layer0和31预算skip、回调异常恢复及篡改拒绝。首轮native测试因独立import先后失败，v1日志保留；修测试导入顺序后v2通过，scalar语义/容量检查最终v3通过。

最终身份：
- `node_witnesses.py` SHA256 `d5c5dccfefe7a7cb30dab1322570b17be325033ddd743b4210f7b7af2f6fe049`
- `test_node_witnesses.py` SHA256 `31cdc6bd4e502516c705a46e49aad723b3947970725feeb39d826bd5079771cd`
- 原始日志 `/tmp/A015_node_witnesses_cpu_v3.log` SHA256 `ac61d2770d5a142c73e9977886cc23b4ee6619209c534beafd40d62eb4721e10`

现有observer SHA仍为b3b2340d…fa4a0a8，未热改。已给Root/A014/A016发接口、测试与范围；新文件冻结供后续AT。GPU真实见证采集/成本和正式独审仍待实际执行，本agent未运行GPU。

## 正式数值聚合与B001部分预览

授权独占新增 `experiment/aggregate_formal_numerical.py`、`tests/test_formal_aggregate.py`、`experiment/plot_formal_numerical.py`。不改22个运行消费源或metric_uncertainty。A014已确认extended max、linear描述分位数、域内pointwise秩区间与固定配额池边界，并提出的reaped/全22源码/固定tie规则与上下文均已实现。

接纳边界：显式completed GPU attempt列表；核supervisor/native0/reaped/source unchanged、worker与launch源身份、全部22源与base-model消费SHA跨attempt一致、冻结plan/stream/NPZ及actual输入IDs、逐doc32 hidden/384 local/384 dynamic/finalnorm身份与几何。失败/缺坐标/重复doc-cluster-batch/错误身份直接拒整个列表；partial只允许冻结目标尚未提供的文档，不把失败筛掉后称成功。

每篇文档输出五类局部跨全部层/site最大与五类总最大（仅这五类，非全部软件算子）、32层传播、末端norm。0/0局部ratio保持null exact_zero_match；全zero精确匹配的最小非负约束M为0另计；S0E>0为显式unbounded/null且进入扩展排序；任一非法所需位置使max unestimable，已有无穷另记录。最大位置按(layer,node,op)固定字典序处理tie，附tie_count与该位置RMS/absmax/signedmean bias。分位数不筛无穷/非法文档；非法阻止主分位估计，partial无CI，完整后域内条件iid rank CI M1，固定配额池永远仅描述。

最终15项CPU tests PASS / 1.392秒：`/tmp/A015_formal_aggregate_cpu_v3.log`，单线程/CUDA隐藏/无GPU导入。涵盖合成1024名单+正式schema、来源与输入拒绝、坐标/分母/dynamic几何、partial、zero/infinity/invalid、tie确定性、扩展插值、条件秩CI。前13项与14项通过日志分别保留，不合并版本身份。

Root回执B001完成后实际运行，输出R004/AT002_formal_batch_b001_numerical/aggregate_v1/formal_aggregate.json及overview_v1/PNG、PDF、source_data；保留partial16/1024、missing1008、web8/news4/reviews4。局部五类总最大P50=0.0848623%、P95=0.0881024%；末端P50=1.44054%、P95=1.75554%。均finite，未观察unbounded/unestimable。图中P50/P95为描述分位带，P99单列小N限制，不输出CI。新增总2,030,349B，未改原件。

实际复算检查`/tmp/A015_B001_formal_checks.log`核覆盖、全部input/result/code/plot SHA、argmax、32层selectors、图与aggregate一致、全部partial CI为空；目视PNG无缺字/裁切/遮挡；渲染日志无warning。此复核不替代A014对原数组/见证的独立数值审核，也不宣称正式1024完成。

身份：aggregate源码b544f3ae5160cd3d4d7fce670f5d9196cfe4043a66109e9b1e12edcc6b2becbd；plot源码5da337b33d924ae3d122dbc76d5de6b2544a9cadff90c985fa146a73fd107f79；test源码a5c48819209545abb06b0974a7eab18dc581ff75c2225d0ff74ee35e296428a5。
实际aggregate SHA70fad720e753a869d7587f3cc90f7306436c25b73d8d9302c41cbabfdba91775；PNG4856f3437c5e5f2157d1d18e90e477aa68ab9d0b1250f66dca7d705ad28dba96；PDF0487ad40762eff677bb98d646520add69afa6baafc390b5259a3bd42122b335e；source_data31c56c9cec9bebc00b03d24e3f028e2770c0b518215acbe2ba1af8c4b8e15fc3。

CLI：`aggregate_formal_numerical.py --plan PLAN --stream STREAM --attempt COMPLETED_AT [--attempt ...] --allow-partial --output-dir NEW_DIR`；完整1024可去allow-partial。`plot_formal_numerical.py --aggregate formal_aggregate.json --output-dir NEW_DIR`。跨版本消费源不自动混合，需另做明确等价资格。
