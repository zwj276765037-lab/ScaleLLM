# 数值流式执行：四开发文档之后的正式批次准备

A016，2026-10-19。此文是非消费方案，未启动正式GPU运行；不改AT010二十份冻结源码或既定1024文档。只做数值精度，不做ACC/PPL/任务非劣效。

当前目标清单是AT001冻结的web512/news256/reviews256个操作性去重文档簇；AT009已冻结其真实≤128 token前缀，合计103700 token，416篇不足128而未padding。1024不是已测文档数。语义近重复/同事件相关及全历史曝光仍未证明不存在；域内iid只能明确作为条件模型。

## 等四文档实测后再确定批大小

本次AT010只用dev indices0..3，一次模型加载/量化，各自当前/参考轨迹，真实长度128/14/128/128。正式批大小仅由此开发成本、内存和落盘字节决定，不看正式误差后选择样本或阈值。

令Tprep为新worker实测加载+attach时间；tmax为三篇128token开发文档中最大的整对前向/统计时间；taudit为审计见证带来的额外成本（本样本不足以把它叫总体P95）。若继续900秒阶段，可先用工程保守式 `m <= floor((900-Tprep-60)/(1.5*tmax))` 作为候选上限，再取Root核定的更小整数。60秒与1.5是成本余量，不是统计精度门槛；触限仍保全，不宣称任何保证。更大批需要新的明确合同，不热延长旧AT。

每批只有一次streamed loader和生产row-chunk128量化，模块/码权重固定；逐文档完成两路、释放当前文档CPU hidden缓冲后再处理下一文档。不能为加快把多个文档当一条文本或跨文档组成attention序列。长于128的位置不属于此生产路径证据。

## 预先写定批次与审计身份

在正式数值曝光前，冻结document_plan.json：doc_id、duplicate_cluster、domain、原文SHA、AT009 token文件SHA、实际位置、batch_id、是否raw审计、node-witness位置seed。按原冻结次序或已声明SHA种子确定顺序，不按数值误差排序；批之间维护全局doc/cluster唯一ledger。

AT009 source-ID hash选择的15个候选审计文档尚不是完整的node/token/channel审计合同；必须在正式运行前明确各域覆盖与固定位置。可继续边界+确定性hash选择16点/node，保留完整Linear组、RoPE pair、Softmax行等依赖。该点集是有向覆盖而非独立随机文档样本。

为满足整AT256MiB，正式分批应预先保证每批至多一篇全raw审计文档；非审计文档只保留能量/偏差/max/异常统计、输入身份与动态码hash/翻转计数。当前AT010政策为audit doc0的全32 hidden/meta、dynamic values仅0/15/31、全32层node witnesses；见证64MiB/doc与96MiB/AT只是子预算，不能代替整AT预算。最终批次政策须以AT010实际字节验证；若有skipped/byte_budget，原样报告覆盖，不能称全部见证完成。

正式worker还需允许某批无raw审计doc，不能为满足collector构造约束偷偷给每批加新审计样本。该改动只能在AT010终态、源码留证后实现/冻结。

## 每文档完整性与统计

每篇必须有32个唯一hidden层、32×12个唯一local site（7 Linear、query/key RoPE、QK、Softmax、PV）、每臂192动态准备坐标和最终Host RMSNorm指标。实际长度保留，输出标量只是覆盖计数，独立统计单位仍是文档簇。

每文档先合并所有tensor分块得到E=sum(error²)、S=sum(signal²)、signed_sum、n、max，再得到relativeL2%=100sqrt(E/S)与normalized bias%=100*signed_sum/sqrt(nS)。局部同码与自由传播分开；当前vs共同出口与当前vs精确节点值分开。GPU observer当前仅给前者，精确子集审计另列。Host/SwiGLU共出口损失未由五节点observer覆盖，不凭主差0宣称无损。

QK统计包括未来masked scores，Softmax只统计valid keys，分母标签不得合并。零信号比值null、小信号保留signalRMS/绝对误差，不加epsilon；失败/缺失/越界各有doc状态，不能以成功子集替代完整预定集合。

## 图和条件区间

主图报告各节点文档相对L2分布和32层hidden/finalnorm传播；P95是主要尾部，P99同时给尾端有限文档支持。整体固定配额混合经验分布描述性汇总，不能套n1024二项iidCI。各域可按numerical_quantile_uncertainty合同给条件order-stat区间：n256 P99双侧95%上界无界，不能拿samplemax替代。

pointwise层区间不冒称整曲线joint；单预定node/site/domain/series的32层用M32，P95+P99联合M64。若跨节点/域/系列同时推断，必须预先扩大family，不能在看到峰值后选择有利口径。没有预定万能“精度保持”阈值，不从开发或正式曲线调门槛。

正式1024尚未启动，当前单开发文档已观察到末层2.1789%、最终RMSNorm2.3901%的相对L2；局部小误差不能代替传播结论。四文档吞吐/个体变化结果出来后才能填具体批数与预计总成本。
