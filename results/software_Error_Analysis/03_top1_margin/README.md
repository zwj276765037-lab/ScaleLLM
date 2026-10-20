# 参考Logit Margin分层：全1024篇

完整1024篇、103700位置、1053个Top1翻转。Margin=参考最高logit减第二高logit，温度1、softmax前的原始logit单位；不是概率差或百分比。

查看 [报告](report.md)、[最终Python图](reference_logit_margin_top1_flips.png)、[分桶表](buckets.csv)。`positions.csv`保留103700行，`top1_flips.csv`保留1053行。空的高Margin≥1翻转清单也保留表头；另有最大Margin20条。固定protocol、所有源SHA与独立CSV/全量独审记录均保留，未隐藏零翻转桶。

分桶为[0,.01)、[.01,.05)、[.05,.1)、[.1,.2)、[.2,.5)、[.5,1)、[1,2)、[2,∞)。并列零Margin单独校验但不重复计总数；空桶翻转率为NA。统计只描述此固定数据。来源/SHA见 [清单](../package_sources.json)。
