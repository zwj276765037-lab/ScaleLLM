# R005 — 完整数值误差、MLP 与全词表补测

2026-10-19 用户明确要求：用 Python 画图，完成数据补测后重新画图。最终交付一张整合所有实测面板的 PNG；不得以待测占位图作为完成交付。执行状态：completed（1024采集、独审、汇总及PNG绘图）；数值判断：inconclusive。

本轮复用 R004 冻结的 1024 篇文档、103700 个真实 token、同一 32 层模型、同一基础量化/权重/LUT/Host 与 v3 纯中间舍入对照。1024 篇均重新采集扩展字段，R004 成功 112 篇不充作新增指标完成。R004/Q001 失败及全部已冻结源保留，不热改旧运行。

Root 负责 logit_numerical_extension.py、范围与资源决定及最终整合；A015 负责 mlp_numerical_extension.py 与CPU验证；A016 负责新 extended_numerical_stream.py / run_extended_numerical.py、成本测试/实际采集/三份摘要；A014 独立审核协议和 audit_extended_numerical.py。所有人只写各自新模块，生产算法不改。

新增 MLP 统计遵循 mission/M005_multistage_rounding_precision/mlp_and_logit_measurement_extension.md：Gate/Up/Down 分开、实际查表 SiLU、门控乘法共同出口舍入损失、同入口完整 MLP、相同残差干预及自由传播残差分解；32 层完整。只读观察器不得污染原局部/动态计数或改变两条轨迹。

输出头从同一 checkpoint lm_head.weight 加载，BF16 源精确提升到 FP32，默认全词表 4096 行块、全部真实 T 个预测位置（含末 token 的下一词分数），两臂相同运算形状与规则，禁 TF32/autocast。FP32 GEMM 输出在 FP64 相减，稳定 FP64 logsumexp。保存逐 token 最大绝对 logit 差、Top1 ID/并列计数、参考 margin、对数概率最大绝对差及整数一致数。输出头的共同浮点舍入另由预定原始点独算；有限 pilot 复核 2048/4096 chunk 敏感性。不得声称整条路径是精确有理数参考。

主覆盖曲线是文档最坏分数差 E_d 的经验 CDF；可同时描述全部 token×词表分数阈值覆盖，但不把标量数当独立文档。预列描述阈值 0.001/0.002/0.005/0.01/0.02/0.05/0.1/0.2/0.5/1/2/5，不设事后通过线。Top1 同前缀文档宏平均、所有 token micro、整篇完全一致分别给出；不是任务 ACC 或自由生成一致性。非有限/缺失/重复坐标触发完整性失败，不丢弃失败样本。

原每小组 bootstrap 在 GPU 作业末尾重复执行导致约 254 秒开销。新入口仅写逐文档原始指标和轻量覆盖，最终统一离线计算相同点估计/分域条件区间；移除重复统计不改数值或统计定义。

资源：最多 4 活跃代理含 Root、无后代；GPU0 UUID GPU-78b42905-e40c-4ab9-30cf-b8e6f7e8c0f6；每 worker CPU1/RSS8GiB/自有GPU24GiB，启动空闲>=30GiB、运行空闲>=8GiB、系统可用RAM>=32GiB、每 attempt<=256MiB。首次扩展 GPU pilot<=900秒；完整队列的分组/有限总成本仅依据本轮实际 pilot 冻结，未完成资格不启动全量。GPU1、其他进程、M003/M004、Vivado、驱动、旧历史目录均不触碰。

AT001 为旧 G001 48 篇 CPU 汇总成本与数值等价资格；原始执行在 /tmp，复制证据须保留原时间/目录，不伪称新跑。后续实际每次执行另登记 AT 和源/输入身份、原生退出及完整覆盖。

## 实际有限预跑

AT002_extended_mlp_logits_pilot 于2026-10-19 06:30:21 UTC实际启动，supervisor313802/worker313807，CPU affinity0。新26源SHA与CPUinputscheck身份一致，4篇开发文本长度128/14/128/128；A014静审无启动阻断。GPU进程正在加载和装配模型，当前未完成forward，不能计入1024正式文档。真实进程与保护记录见该AT的root_launch/gpu_launch_manifest/gpu_worker/gpu_resources。

后续正式方案拟常驻同一模型按固定逻辑组执行，只保留一份真实global GPU进程回执，每组单独真实执行记录；新源码与总成本待本轮pilot测量后冻结。最终审计将明确共享进程，不伪装每组独立GPU启动。

## 预跑终态与正式阶段决定

AT002于06:37:59 UTC自然完成，native0/supervisor0、worker回收、源码不变，457.664秒，开发4篇398真实位置，正式0/1024。旧轨迹66个原数组及全部四篇旧指标/动态身份逐项相同。A014新独审6.720秒完成，无测量资格阻断；head全词表分块敏感性max约1.5e-5、两臂Top1变化0，仅限开发资格。不得将394/398开发Top1写成正式结果。

Root依据实测冻结新正式合同 `.research-agent/decision_inputs/M005_R005_formal_persistent_contract.json`：64个原逻辑16篇组、同一模型装配一次；唯一session_S001，组AT003..AT066。总14400秒含后处理，全部session与组输出总6144MiB，每组900秒/256MiB，CPU1/RSS8GiB/GPU24GiB及原准入保持。正式入口正在CPU双组/故障/资源回收测试与独立代码复核，尚未启动。新stage预算独立明示，不延长旧失败或预跑。

## 正式运行已实际启动（最新）

Root于2026-10-19 06:51:49 UTC启动唯一session_S001 supervisor330188。完成冻结plan自检后，06:52:30 UTC启动shared GPU worker330520（PGID330520/starttime8235802），64组AT003..066及67条后处理命令均按planSHA `4c2bebb5cc74679759447f358a5c9070dbdc3fd0eafd97394e766f8f11126db4` 消费。源码/计划/后处理保持冻结。当前首次装配阶段，尚未声明任何完整正式文档。动态进度以session_S001/group_progress.json与组document_result为准；最终必须global原生0、1024完整及全部独审后才能交付PNG。

正式命令、来源、准入与实际进程见session_S001/root_launch.json、session_launch_manifest.json、session_worker.json。全数据采集后自动执行64份核心+扩展独审，以及make_inputs/aggregate/render三步。Root继续监督至最终PNG实际产生并目视核对，不以后台启动当完成。


### 2026-10-19T08:04:37.180053+00:00 — 用户要求后台继续、先汇报中间结果

用户最新要求：不用持续盯进度，让补测在后台自行运行，先报告中间结果。既有 session_S001 继续执行冻结的 1024 文档采集、64 组独立核查、聚合和 Python PNG 渲染；未暂停、重启或修改冻结程序。主控结束逐分钟轮询。

已单独保存前 G001–G029 完整 29 组的描述性快照：464 文档，47,481 个真实位置，6,089,723,136 对词表分数；来源为 `analysis/interim_464/interim_summary.json`，带输入文件哈希。此为固定前缀中间统计，全量独立核查待完成，不代表 1024 文档目标完成或普遍精度结论。

中间结果：全词表绝对差≤0.1 的分数覆盖率 98.024699%，≤0.2 为 99.830909%，≤0.5 为 99.992799%；逐位置 Top1 一致 47,013/47,481=99.014343%。末端隐藏向量相对 L2 中位数 1.579803%、P95 3.010414%；词表分数相对 L2 中位数 1.231032%、P95 2.312856%。最大单个分数绝对差 7.070253，长尾保留。不得将这些数字写成最终结果或任务 ACC。

冻结流程预定最终输出：`analysis/final_precision_png/png_v1/final_precision.png`；只有实际生成并通过全量核查后才能标为完成。


## 全量采集、核查与PNG交付终态

execution_state: completed（R005 S001采集、64组独审、聚合与Python PNG绘图完成）
verdict: inconclusive（不作所有输出误差可忽略或普遍精度保持的结论）

2026-10-19 17:38:17（Asia/Shanghai）完整流水线结束，实际墙钟9946.915秒；GPU采集17:30:26结束，native0、worker已回收、冻结源未改变。1024/1024文档、64/64组、103700真实位置、13300147200对全词表分数；web512/news256/reviews256，无缺失文档。64核心与64扩展审查均已完成，15篇预选原始见证与其余文档统计/来源检查的范围分开陈述；不是所有完整张量独立重算。

全量结果：逐位置Top1一致102647/103700=98.984571%；文档等权98.994439%；整篇全部位置一致397/1024=38.769531%。全词表绝对差≤0.1的分数覆盖率98.130653%，≤0.2为99.844413%，≤0.5为99.991921%。末端隐藏向量相对L2中位数1.570580%、P95 2.847756%；最终词表分数相对L2中位数1.228031%、P95 2.207453%。这些不是任务ACC或自由生成一致性。

MLP每篇跨32层最大局部误差的P95（%）：Gate0.00709539、Up0.00918906、Down0.07167732、门控共同出口损失0.04570844、整个MLP分支0.16322653、同残差相加后0.09299327。门控项对同LUT精确乘积，其他局部项对共同出口的高精度中间参考。SiLU同表语义核验不表示解析函数近似误差为零。

PNG v2只修正底部说明重叠与两个分区标题；13×1024个点、分位值、整数计数和全部来源与v1一致。最终图已目视检查，原v1与冻结renderer保留。刚讨论的Softmax后完整概率分布TV尚未测得，不能标为本轮已完成指标。范围仅单模型、最多128个真实token、32层prefill；固定配额合池描述，分域区间依赖未验证iid假设。

[全局终态](session_S001/session_receipt.json) · [最终PNG](analysis/final_precision_png/png_v2/final_precision.png) · [汇总与源链](analysis/final_precision_png/aggregate_v1/final_aggregate.json) · [数据表](analysis/final_precision_png/aggregate_v1/quantiles.csv) · [版式一致性核查](analysis/final_precision_png/png_v2/layout_validation.json)
