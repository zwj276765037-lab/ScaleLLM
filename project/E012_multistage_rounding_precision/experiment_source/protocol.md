> 2026-10-19范围更正：用户确认本补测仅证明数值精度，ScaleCode方法ACC已有结果。本文任务NLL/PPL/ACC及非劣效设计为历史，已由M005 numerical_fidelity_protocol_v3.md取代；旧局部实验定义和证据保留。

# E012 / R001：Linear 多级减位宽首阶段协议

状态：执行合同已冻结，结果待工程及独立审核。所属M005/SM021–SM022；不是恢复M004。数值及JSONL唯一细则见[design](../../software/0_Software/rounding_precision/source/design.md)，同名字段以该v1合同为准。A014只设计/独审；A015独立oracle、生产CPU参照及边界测试；A016数据/runner与原始记录；Root维护共享索引和GPU资格。

## 本阶段假设、步骤与验收

假设：对同一整数码、ScaleCode与group次序，当前Linear的额外减位宽误差满足确定性界；影响是否足够小仍需真实回放和后续任务预算。本阶段不预设整模型精度结论。

1. 冻结活动V5源hash、独立oracle和生产回放身份，检查JSONL v1。生产CPU回放来自当前V5语义，oracle用独立有理数路线；不以两个共享舍入helper的模型互相比对作为独立证据。
2. 定向集覆盖三个profile；每项提供明确输入标签、预期合法/异常分类。必测零/正负对称、half-away正负ties及两侧、右移余数0/最大/1、负数floor、左移/不移/右移、inactive code、total_shift合法两端/越界、group次序、长累加与抵消、逐步wrap后抵消、guard越界、输出sat上下界、相同码及不同码、malformed行和零有效分母。正常合成样本满足dot/raw物理范围；故意越界必须标负向样本。
3. 固定seed=20261019生成有界合成样本，先5分钟内CPU pilot。随机集补充定向集，不替代边界。单行G至少覆盖1/2/128/448；真实模型维度资格另记。A015测试提供预期证据；A016 runner在独立AT运行并保存逐行结果与聚合。普通实现错误直接修复，保留失败AT，不降低容差或删用例。
4. 验收：生产参照一致性mismatch=0；精确界适用样本违例=0；全部预设负向样本准确分流；必要边界类别无缺失；源/输入身份和退出状态完整。缺项标NOT_RUN/INCOMPLETE，不能写总体PASS。异常样本不进入有效域mean/RMSE/P99；保留异常率及分母。CPU验证不能替代GPU/RTL一致性。

主报告只命名“仅输出舍入”“当前实现”，另列oracle；按profile和输入来源出表。至少记录signed mean、RMSE、max、P99、LSB误差直方图、输出码相同比例、理论界/违例、异常计数和有效分母。A014审核源代码分离、至少一例正负tie/负floor/逐步wrap的手算或独立复算、原始逐行证据和汇总。

## 真实数据现状及最小采集

A016初查历史archive只含groups.float32[32768,32]与labels，缺layer/token/group定位及q/dot/code/shift。该材料可研究前端分布，不能构造有真实身份的同码Linear输入。不得从聚合cosine或这些float组反推整数码；完整inventory由A016落盘并供审核。

下一阶段优先对冻结prompt进行一次**生产数值轨迹**的有界采集：pilot层0/15/31，各层Q/K/V/O/Gate/Up/Down七算子。采集点放在 `PreparedActivation` 与相应weight codes/shifts已经生成之后，记录选定row/token、选定输出channel的全部128/448组A8整数码、zero-point、W整数码、code、shift、group顺序、生产输出及每步/末级异常。真实post-RMSNorm前端输入可一并保存，以核前端来源；Down需真实SwiGLU输入，不能以任意激活替代。保存模型/tokenizer/prompt/权重制品/代码hash及Host dtype。每模块至少固定一个row/channel作最小链路样本，不以此代表充分统计覆盖；数量与选择策略在正式采集前冻结。

选取row/channel后，重放数据仅按groups增长，CPU可用任意精度标量逐组完成，无需拷贝整个checkpoint。若只保存dot，则采集时须独立由保存的lane码复算并保留可追溯证据；优先保存少量lane数组避免来源盲点。

CPU逐层前向虽可降低显存占用，仍需加载/计算8B及此前所有层，可能远超20分钟；本合同不把它视为已可行。先测单模块回放CPU时间/RSS，估算全32层采集与回放，超预算缩小采集而不是无界运行。GPU可通过一次有界前向采集，但只有Root确认设备身份/占用、显存上限、pilot成本和停止条件后才启动；当前不占GPU。GPU1不使用，不干预M003/M004或外部进程。若真实采集暂不可行，合成结论与缺口单独交付，不伪造SM022完成。

pilot后正式覆盖全32层及预先冻结的不同token/幅度/shift区间，保留每层七类算子覆盖分母；layer0/15/31每层一次的旧42行trace不能担保全层或全输入域。

### 独立允许分支：BF16轨迹的真实输入局部回放

若完整V5轨迹采集成本较高，允许先从原生BF16前向捕获上述七类Linear的真实输入；用同一活动生产frontend与exporter对选定row/channel生成A8/W码及ScaleCode，再接本阶段精确oracle/当前实现。必须标记 `provenance.trajectory="bf16"`、`source_format_id=null`（或保留可核实的实际源标签），结果名为“BF16轨迹的真实输入局部回放”。它说明这些真实输入上的条件局部恢复误差，不说明输入来自V5轨迹，不证明全链误差或模型精度；不得设置eligible_current_format_evidence=true。Down输入是BF16轨迹的真实SiLU×Up输入，与生产整数SwiGLU轨迹分开。禁止重新使用归档raw-scale权重量化替代V5 decoded-scale量化。

Root已采用独立GPU0 pilot预算：先单prompt/batch=1/32tokens，eval、BF16、no_grad、use_cache=False；采层0/15/31七算子，每模块至多2个固定token位置×4个输出channel，并保存这些输出所需全部128/448组lane码与metadata。后续128tokens是单独记录的下一次尝试。使用低CPU内存/流式加载，CPU≤2线程/8GiB RSS，GPU任务峰值reserved≤24GiB，墙钟≤300秒；启动前free≥30GiB且给外部进程保留≥8GiB余量。实际设备UUID、外部占用只读快照、加载策略、checkpoint/config/tokenizer/prompt及源码身份随AT保存；只管理本任务进程，不触碰既有约10GiB外部进程，GPU1不使用。Root冻结代码与资源后按已授予范围直接执行，普通修复不新增逐项放行门；触资源保护保留失败证据并缩小采集，不能无限加预算重试。若8B加载仍超CPU上限，先报告所需主存与更小拷贝方案，不伪称可行。


## 资源、证据和后续边界

资源沿[M005主合同](../../../mission/M005_multistage_rounding_precision/contract.md)：本聊天最多4活跃含Root，无后代；CPU合计≤4线程，每worker≤2线程/8GiB RSS；先≤5分钟pilot，每次CPU实验≤20分钟；系统可用内存<32GiB不启动。资源触限保留证据并缩小范围；只有本任务进程可由runner管理。禁止Vivado/板卡/驱动操作。

每个AT新目录，保留命令、cwd、主机/Python/依赖版本、源码与数据SHA-256、seed、开始/结束时间、退出码、实际线程/RSS/时间、stdout/stderr、逐行JSONL、汇总JSON、边界覆盖及失败反例。manifest记录schema与目标/来源format，JSON大整数及有理数按design规则序列化。源码/输入实质变化新AT，范围/协议实质变化新R；原证据不覆盖。运行器实际CLI由A016填写到AT记录，本协议不捏造未实现命令。

全链阶段统一Host dtype、基础量化制品、LUT和评测协议；额外舍入名单、节点误差预算、δ_NLL/δ_ACC及独立统计单位必须在正式结果前基于应用要求/统计能力冻结，当前不编造数值。只使用hardware_128兼容任务集合，可先匹配五项likelihood；GSM8K不是本次前置条件，不能借用M004或2048上下文结果。旧04 PPL不改称05实测。RoPE/PV/QK后续独立合同见design，数值规则未逐项冻结前不套用Linear界。
