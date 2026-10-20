# E012 多级舍入：当前状态

execution_state: running
verdict: inconclusive
applicability: R003输入冻结与有界数值开发资格已完成，R004正式首批准备中
review: AT007/AT010限定范围独审通过；不等于整体精度命题通过

AT010已于374.403秒native0结束，worker231065回收，无自有GPU实验仍运行。四开发文档真实tokens128/14/128/128；每篇32hidden/384local/384dynamic事件覆盖齐，最终norm误差约1.643%..2.221%。前序AT007单dev32token最终norm2.3901%。这些结果说明必须单列传播误差，不能凭局部<0.086%宣称精度保持。

AT00718、AT01020消费源码已hash匹配完整保存证据，当前实现已获Root解冻进入正式入口改造；独审已完成，不新增源码批准门。三摘要现在以本状态为主，Root集中登记/publish/索引，A016不手改共享索引。

正式数据：1024个目标文档及token前缀已冻结（web512/news256/reviews256、无相同token前缀），prepared1024而numerical formal measured0。现准备R004第一批最多16篇，以冻结身份和token NPZ直接驱动，预定2:1:1域顺序，到第二raw审计候选前断批；不能重新选样。允许无raw审计批，按计划保留必要raw/witness，其余逐文档全量统计。GPU尚未启动，须Root新AT/来源/资源冻结。

资源保持CPU1/RSS8GiB/GPU24GiB、单次900秒、整AT256MiB；GPU0固定UUID、launch free30GiB/runtime free8GiB，外部进程不干预。第一审计开发文档整对51.64秒、非审计约6秒，但未知真实长度冷编译不套用T128平均成本，首批保守控制。若触限保全失败/缺失，不补0或静默缩小预定集合。

没有accepted/strict待修阻塞；CPU主accepted全集和strict-valid子集已分开。GPUobserver当前只给common-exit局部/聚合audit，Host/SwiGLU共同出口损失、全量exact/strict逐输出界尚未由该observer覆盖。分位统计模块已独审，正式总体固定配额仍只描述性，域内条件CI不冒称假设已验证。

历史失败保持：AT005300秒合同wall stop（17/32 attach，无forward）；AT008输入payload命名冲突失败，AT009独立修复；这些工程失败不反驳方法。M003/暂停M004、GPU1、EDA及ACC/PPL任务均未触碰。M005总体未完成。
