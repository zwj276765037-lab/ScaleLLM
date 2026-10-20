# R004 — 冻结1024文档的正式数值测量

状态：采集未完成，Q001已停止；verdict: inconclusive。2026-10-19 13:45（UTC+8），G003/AT005在汇总收尾阶段触及既定900秒墙钟预算，cost_stop/exit124；源码未变、worker已回收。完整成功attempt覆盖112篇（B001 16篇及G001/G002各48篇），其中仅B001的16篇已完成独审。队列记录160篇durable输出另含失败AT005的48篇，不能当作160篇完整验收；其余864篇未启动。全1024采集和原全量后处理均未完成，六列完整图依赖任务随原队列失败停止，最终图未生成。后继新采集计划尚未启动。开发批R003/AT010不并入正式文档统计。

以下13:00启动段及自动出图描述均为历史记录，当前状态以上述停止回执为准。

以上数量是2026-10-19 13:00（UTC+8）的启动快照。剩余有限队列Q001已在后台启动，固定24组、总墙钟23400秒；[启动证据](queues/Q001/root_launch_receipt.json)记录自有进程身份。进度写入`queues/Q001/queue_events.jsonl`，终态才生成`queue_receipt.json`。25份独审、全1024聚合、主图及可读报告只在完整采集后自动执行，预定输出为`analysis/Q001/`。后台启动不表示这些未来产物已经存在，也不表示精度保持通过。

本批严格延续M005 v3数值协议：同基础量化、整数权重、LUT及共同出口，比较当前中间位宽与保留中间精度的参考；逐文档记录同输入局部误差和两条自由传播轨迹的32层及末端误差，不运行ACC/PPL。

输入唯一来自R003/AT009冻结token流，与AT001同一1024源文档（web512/news256/reviews256），103700实际token、最大128，不重新取样、不padding。输入计划固定2:1:1域交织且保持各域内既定顺序，预定15审计候选不按数值结果更换；重复来源簇和token前缀分别核查。

AT001准备输入顺序、身份与64个逻辑批次边界，不做模型推理，已经完成。AT002测量B001的16文档，484.95秒完成且源码未变、工作进程已回收。余下B002–B064按成本合为24个预先冻结的运行组，共1008文档；每组至多48文档、1个预定审计文档，保留全部32层原始hidden的组至多32文档。分组仅依据已测时间、存储与冻结审计名单，不依据误差。每一实际启动另记AT，CPU1/RSS8GiB/GPU24GiB、最多900秒、全attempt256MiB及当前GPU资源准入保持不变。队列遇失败、触限、源码变化或覆盖不足即停，不重试、不删样、不补0。

AT002每篇32层hidden、384个局部位置及两臂各192处动态编码完整。独审核验16篇输入token/mask/position逐值一致，并对预定网页审计文档独立重算384份原始算术见证（72064个展开输出），当前及参考结果均与独算一致，38376个适用误差界零违例；33688个Softmax结构掩码输出单列。首批最终归一化hidden相对L2误差为1.17395%–1.78056%，表示数值偏差而非ACC变化。此为16篇观察范围，不构成全1024或任意输入的精度保持证明。

每篇均需32层hidden统计、每层12个局部位置（五类节点，累计384）、最终归一化和两臂审计。预定审计文档保留原始数组与完整输入依赖见证。SwiGLU/Host共同出口损失与五类额外中间舍入的范围分开，不把后者说成前者的全量独立见证。

全1024目标完成与单批完成分别登记。图主轴使用相对数值误差百分比；逐文档P50/P95/P99与绝对误差并列，零信号单列。固定域配额合池只作描述性统计，域内分位置信区间保留其假设与可能无界的尾部；不观察结果后选择精度通过阈值。

2026-10-19 六列图修订：按用户要求新增[局部算子与整体输出误差图](analysis/figure_six_columns_v1/numerical_six_columns.png)及[矢量PDF](analysis/figure_six_columns_v1/numerical_six_columns.pdf)，数据身份和全部96个点保存在[source_data](analysis/figure_six_columns_v1/source_data.json)。同一百分比对数轴上，前五列为每篇文本该算子全部32层及调用位置的张量相对误差最大值，第六列为同篇文本最终归一化后隐藏向量的相对L2误差。灰点为文档，蓝点为中位数，橙菱形为95%分位数；后两者为固定配额合池描述值。当前仅使用AT002已审核16篇：局部观测最大0.0891436%，末端中位1.44054%、95%分位1.75554%。整体输出范围是最终归一化隐藏表示，不包含LM-head。图明确标识16/1024部分结果，既有图/源/队列计划保持原样；这次改图不改变数值定义、样本或精度判断。

六列完整样本图的有限CPU依赖任务已启动：[启动身份](analysis/six_columns_after_queue/root_launch_receipt.json)、[冻结计划](analysis/six_columns_after_queue/plan.json)及[资格与启动核验](analysis/six_columns_after_queue/validation.json)。仅在原Q001全部1024篇及28项后处理成功、覆盖与原报告身份链均核齐后生成`analysis/figure_six_columns_final/`；不重跑模型、不使用GPU、不修改Q001。依赖任务截止2026-10-19 11:32:09.660291 UTC，失败即停止，不重试。当前图仍是16篇审核数据。

2026-10-19 末端误差质疑只读诊断：[当前判断与后续区分实验](analysis/final_error_diagnosis_v1/interpretation.md)。公式和输入配对核验一致，末端非零小分母；最后解码层的绝对误差上升已确认，具体主因尚无干预证据。原Q001继续，整体数值保持仍inconclusive；未新增模型运行或改动冻结源。

2026-10-19 MLP补充：已从AT002同一16篇独审核验数据拆分[Gate/Up/Down三投影图](analysis/mlp_precision_v1/mlp_projection_precision.png)、[PDF](analysis/mlp_precision_v1/mlp_projection_precision.pdf)及[覆盖报告](analysis/mlp_precision_v1/coverage_and_summary.md)。三投影的P95分别0.00707148%、0.00920143%、0.07192479%，不能把Down局部误差视为整个MLP分支误差。SiLU/门控乘法/完整MLP输出以及词表分数尚需新增测量；[扩展合同](/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/mission/M005_multistage_rounding_precision/mlp_and_logit_measurement_extension.md)将最高分词一致率列为用户明确要求的必测项，当前没有该项实测值。

2026-10-19 综合图：按用户要求将Attention局部五类、MLP三投影与最终归一化hidden放入[同一张综合PNG](analysis/integrated_precision_v1/integrated_precision.png)及[矢量PDF](analysis/integrated_precision_v1/integrated_precision.pdf)，下方加入全词表分数误差覆盖率、最高分词一致率两个面板。Attention线性从q/k/v/o四投影的原始位置重新聚合，与MLP分开；九列均为同一已审核16篇，共144文档点。词表两项尚无实测，面板明确待补测，没有示意线、假值或填0。SiLU/门控乘法/完整MLP及残差未独立记录仍明示；旧图与冻结源保留。
