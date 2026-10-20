# E012 多级舍入：状态

execution_state: completed
verdict: supported（仅当前限定局部范围）
applicability: v2 synthetic及单文本BF16真实输入的32/128token局部Linear恢复；真实各168输出；全链未测
review: synthetic与32/128真实有限局部均已独立复算接受

本轮A016工程阶段completed：inventory、精确运行器、41项CPU回归、预算内真实32/128采集与CPU同码回放、两套真实PNG/PDF/SVG/CSV全部交付。没有A016自有GPU或CPU实验仍运行；GPU0最后只见原外部PID23186，未控制任何外部进程。Root负责集中登记与下一阶段，不把本阶段交付当整个M005完成。

R001 AT001/AT002原始synthetic版本均保留。R002 AT001 HF加载成本停止，AT002逐tensor32采集成功，AT003为32CPU回放，AT004为128采集，AT005为128CPU回放；各有独立manifest/receipt。AT003–AT005曾因Root模型容量错误暂存raw evidence+registration_pending；Root已集中补齐AT002–AT005登记并在pending历史追加解决；A016没有删除原标志或改共享索引。

资源：单GPU0固定UUID；采集2线程/RSS8GiB/ownGPU24GiB/sharedfree8GiB/300秒，实测峰CPU约2GiB、GPU14.44GiB。两个采集45秒左右，两个CPU回放约1.2秒。GPU1、EDA、M003与暂停M004未触碰。source/输入运行期间冻结，失败与旧版本不覆盖。

下一步：Root统一publish、阶段审阅与导航；另按当前授权确定是否继续全32层/非线性/全V5传播或正式模型指标。当前没有自动扩张scope或排队GPU任务。

本轮E012有界实验已执行完成；SM023为planned后续工作，M005整体未完成。没有后台实验正在继续。
