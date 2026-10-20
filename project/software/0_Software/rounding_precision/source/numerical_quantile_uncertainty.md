# 文档级P95/P99不确定性合同

A014；M005/E012/R003；2026-10-19。新增统计设计，不改AT007消费源码，不增加ACC/PPL或通过阈值。A016可在独立metric_uncertainty.py实现；本文件不声称1024文档已经测量。

## 统计单位与适用假设

一个数据点是合并全部tensor分片后的document×layer×node×op/site×trajectory×series指标。token/channel/scalar不是独立样本；同doc的32层为一个相关向量。唯一duplicate_cluster/doc_id须核验，不能靠重复token增加n。

下述二项区间在“文档指标独立同分布”条件下不依赖分布形状：连续分布给精确覆盖，离散/ties给保守覆盖。去重、固定SHAseed和域标签不能证明该假设。当前固定web512/news256/reviews256配额不构成同分布的1024个混合抽样；从有限语料无放回选取也不是二项独立试验。论文应称“在域内iid文档模型下的条件区间”，并保留操作性抽样/潜在近重复/历史曝光限制；若目标改为有限语料总体，应另按实际无放回设计反演超几何分布，不能给二项区间贴上设计精确标签。

相对L2未定义的零信号文档、运行失败、缺失输出分别计数，禁止补0。区间用实际有定义的n，目标须注明条件于指标有定义；失败不是可随意剔除的正常样本，不能由剩余成功样本代表完整预定集合。

## 可执行二项次序统计索引

定义q_p=inf{x:F(x)>=p}；排序x_(1)<=...<=x_(n)，1-based。令x_(0)=−∞、x_(n+1)=+∞；仅预先已知的指标support可替换无穷（例如非负相对L2的下界0，不能用样本max替代上界）。给总体alpha=.05、预先冻结family_size=M，a=alpha/M，B~Bin(n,p)：

- L=max{k=0,...,n : P(B<=k−1)<=a/2}。
- U=min{k=1,...,n+1 : P(B>=k)<=a/2}。
- CI=[x_(L),x_(U)]；coverage_under_iid=1−cdf(L−1;n,p)−sf(U−1;n,p)>=1−a。

实现直接用cdf/sf枚举或二分，不以1−cdf计算极小上尾，不做正态近似、不插值CI端点，也不事后选择“最短且漂亮”的区间。原有点估计可保留np.quantile(method=linear)，明确它与不插值的区间端点是不同对象。ties不打随机抖动。

这些索引由A014同时用SciPy cdf/sf和独立大整数二项权重核对；表中n1024仅为iid参考，不能直接套本轮固定配额合池。

| 有定义文档n | pointwise P95秩 | pointwise P99秩 | 32层joint P95秩 | 32层joint P99秩 |
|---:|---:|---:|---:|---:|
|256|[236,251]|[250,257=+∞]|[231,254]|[247,257=+∞]|
|512|[476,497]|[502,512]|[470,502]|[498,513=+∞]|
|1024|[959,987]|[1007,1020]|[949,994]|[1002,1023]|

pointwise P95实际覆盖依次0.9704313681/0.9676392523/0.9557995291，P99为0.9845903632/0.9786672172/0.9583818993；离散秩导致不恰好等于.95，这是保守性而非计算错误。双侧等尾P99有限上端要求.99^n<=.025，即n>=368；n256时样本max覆盖q99仅1−.99^256=92.36850161%，连单侧95%上界都不足。任意非等尾有限区间的存在条件另为p^n+(1−p)^n<=alpha；P99该最低n为299，不能与等尾368混淆，也不能看完数据后切换尾预算。

JSON不用Infinity/NaN：端点value=null并给upper_unbounded/lower_unbounded，秩仍保留n+1/0；空集合返回not_estimable。接口建议rank_interval(n,p,alpha=.05,family_size=1)及order_statistic_interval(values,...,sampling_model)，包含n_selected/n_defined、排除原因、p、M、family_scope、两尾概率、实际覆盖下界、support来源与假设状态；调用层验证文档唯一性。

## pointwise与joint的区别

每层分别95%不等于整条32层曲线95%。单一预定node/op/domain/series与单一p的32层联合覆盖，用上述M=32（Bonferroni）；层间相关不影响此保证，不要求把各层当独立。若同时声称P95与P99，则M=64；若同一结论还涵盖多个节点/域/误差系列，应在正式测量前把它们计入family，不可事后挑最大层后沿用M=1。

也可对每个文档先构造max_layer(error)再估其P95/P99，但那是“文档内最坏层误差”的分位，与各层分位的最大值或整曲线band均不同，须独立命名。bootstrap按完整文档向量重采样可作补充敏感性；逐层percentile bootstrap或样本max不自动具有本合同的有限样本joint覆盖保证。

## 当前固定域配额的总体结果

默认总体1024只报预定权重(.5,.25,.25)混合经验分布的描述性分位，每域另报条件二项区间；拒绝把pooled n1024结果标成iid精确CI。若必须给保守总体区间：定义F_mix=sum_s w_s F_s，先以总alpha除以域数3（再除预定layer/quantile family）分别求域内q_p区间[L_s,U_s]，再用[min_s L_s,max_s U_s]。这是由min_s q_(s,p)<=q_(mix,p)<=max_s q_(s,p)及union bound得到的保守包络，不是加权平均分位；可能上端无穷，应如实显示。不得把此宽包络称高精度P99估计。更紧分层CDF带反演可另实现，但本次不靠未经验证的pooled二项近似换取有限区间。

## 来源与核查范围

来源事实：[Zhan-Qian John Lu, NIST TN 2119 (September 2020)](https://nvlpubs.nist.gov/nistpubs/TechnicalNotes/NIST.TN.2119.pdf)，§5.3，印刷页32–33（PDF页40–41），式(30)–(31)：iid条件、二项覆盖概率及离散分布保守性。已通过公开PDF读取该节；本文等尾索引代码化、32层family及分层包络为本项目推导。

来源事实：[R. Zieliński & W. Zieliński, Best Exact Nonparametric Confidence Intervals for Quantiles，作者公开draft](https://wojtek.zielinski.statystyka.info/Inne_informacje/prace_pedefy/P36_Stat_2005_draft.pdf)，§1，PDF页1–2，条件(C)：有限两端区间存在条件及P01的299例；公开文件名标2005_draft，未把该draft冒称排版终版。已读相关全文页。本项目采用确定性等尾保守区间，不采用该文随机化最短区间方法。

最小工程验收：核上述表、n=1及n=0、全ties、非负support、缺失/重复doc拒绝、M=32/64覆盖、n256 P99上端无穷；再用独立整数二项枚举核小n和已列n。CPU1、小数组、无需GPU。当前结论是统计方法/索引已核，不是实际误差满足任何万能精度阈值。

反例校验：256个观测均为0时，经验bootstrap可能给P99区间[0,0]，但存在“绝大多数0、略超过1%为任意大值”的总体仍以非忽略概率产生该样本。二项区间保留+∞上端，正是避免把未看见尾部误写成尾部已受限；不能根据全0样本改用样本max作support。

## 独立实现审核（2026-10-19追加）

`metric_uncertainty.py` SHA `1d8c7613d550215706409e8c930703ec9f38818e9f6af3a50e4b097a8d04fec5`。A014不调用其二项递推作为oracle，另以math.comb构造整数概率，核n=1..30及256/512/1024、p=.1/.5/.9/.95/.99、M=1/32/64共495组，索引/覆盖0不符；单CPU0.458秒。微例核全0的n256 P99仍无有限上端、固定配额不发布iid区间、failed但保留partial值时抑制完整集合CI、empty_valid_domain非null数值拒绝。

审阅发现并已修：iid假设声明不再命名为已验证；单cell实际coverage不再用于推断异n多cell的joint coverage，family保证使用1−alpha；failed状态检查不局限于null值分支。实现保留assumptions_verified=False。该审核只确认数学/输入分流，不认证实际文档iid，也不声称任何正式P95/P99实测结果。
