# A016 数据与局部实验运行器

关联：[M005](../../mission/M005_multistage_rounding_precision/contract.md)、SM021/SM022、[E012](../../project/E012_multistage_rounding_precision/README.md)。

负责人：实际工具代理 `/root/rounding_data_runner`，父代理 `/root`。不创建后代。

写入：`rounding_precision/experiment/data_inventory.py`、`prepare_replay_data.py`、`run_local_experiment.py`、真实结果绘图及对应测试；E012三摘要、独立AT原始证据；本A记录。A014拥有协议/JSONL，A015拥有独立参考/生产回放/数值指标，Root唯一共享登记与索引owner。其他执行者在同一工作区，不撤销他人改动。

资源：CPU总4线程，本worker最多2线程/8GiB RSS；pilot<5分钟，单次CPU<=20分钟；可用内存<32GiB不启新run；无GPU/EDA，无外部进程控制。旧工程只读，M003/M004不触碰。

阶段回传：真实数据是否具备同整数码/同ScaleCode回放资格；接口/数值反例；pilot及正式CPU结果；缺口与有界采集建议。局部结果不扩成全链结论。
