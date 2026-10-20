# E012 多级舍入：当前来源与方法

M005依据[v3数值协议](../../../mission/M005_multistage_rounding_precision/numerical_fidelity_protocol_v3.md)继续，只补数值精度，不重跑ACC/PPL。当前实现与仅输出舍入共享整数权重、基础量化、ScaleCode、LUT和共同出口。局部固定同一输入码；连续两路各自重算动态码。参考不是BF16/QDQ轨迹。

活动代码唯一根为project/software/0_Software/rounding_precision。采用同一V5 module对象、HF5兼容桥、逐tensor BF16参数加载和经完整矩阵字节核验的row-chunk128量化；32层全部挂接Attention03/MLP05、Down S32/shift12/S45/S54。LMhead从未加载或调用，无任务评分。CPU1/RSS8GiB/GPU24GiB，GPU0由Root监督；新900秒合同单独登记，不热延长旧300秒尝试。

数据目标是[AT001冻结清单](../experiment_results/runs/R003/attempts/AT001_clean_document_manifest/document_manifest.json)：eval1024=web512/news256/reviews256，train/dev各64互斥Wikipedia文章。文本/URL去重不证明语义iid或全历史未曝光；dev为域外开发。旧first64/128只作工程smoke。[AT009 token流](../experiment_results/runs/R003/attempts/AT009_frozen_eval_token_stream_fix/frozen_document_stream.json)准备同一1024篇的真实≤128前缀：总103700 tokens、416篇不足128不padding，1024个token前缀无重复。**准备1024篇不等于已测1024篇，正式数值测量仍0。**

R003/AT007用单dev文档32tokens跑完整32层；AT010一次加载复用四篇dev，实际长度128/14/128/128。局部observer计算Linear、query/key RoPE、QK、Softmax、PV的同码common-exit影子结果，但只返回原current继续轨迹；另一forward单独运行仅输出舍入并记录hidden/final Host RMSNorm。局部与传播分开，Host/SwiGLU共同出口损失未由五节点observer全量测出。

统计先合并document×layer×node×site×trajectory的分块，再报relativeL2%、normalized signed bias%、实值RMSE/max与signalRMS。零信号比值null，不加epsilon；小信号无临时通过阈值。QK包含未来masked scores，Softmax只含validkeys，分母不同。CPU数组主全集使用metric_mask∩accepted，strict-valid子集另报；GPU局部只有accepted聚合/audit，不冒充全量逐输出strict或exact界。

AT010预定audit doc0保存全32 hidden和dynamic metadata、values只层0/15/31；其他文档只统计。16点/node的见证保留完整依赖：Linear全128/448组、RoPE pair、Softmax整行等，64MiB/doc/96MiB见证子预算，整AT256MiB。所有384见证坐标保存，无skip；边界+hash点不是iid文档样本。A014独立整数/Fraction复算，而非只比较两份软件输出。

AT007的18源码与AT010的20源码均逐一匹配运行hash后保存为frozen_code证据，[AT010源码清单](../experiment_results/runs/R003/attempts/AT010_four_document_numerical_development/frozen_code_manifest.json)不是第二实现入口。旧失败不覆盖：AT005在attach17/32时wall stop无forward；AT008 token payload命名冲突失败，由独立AT009修复。R001/R002合成/BF16局部历史仍只支持原范围，[旧结果](../experiment_results/runs/R002/attempts/AT005_cpu_replay_bf16_128token/summary.json)不替代新V5传播证据。

后续R004将直接消费冻结token NPZ和身份计划，保持1024选样不变；第一批预定最多16篇、2:1:1域顺序、第二raw审计文档前切批。尚未启动。P95/P99按[不确定性合同](../../software/0_Software/rounding_precision/source/numerical_quantile_uncertainty.md)处理：固定配额整体描述性，域内iid只作条件假设；n256 P99上界无界，pointwise不等于32层joint。
