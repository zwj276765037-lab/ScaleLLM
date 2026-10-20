# R011：已有1024篇证据的第32层跳升检查

31→32层确为实测曲线最大的P95层间增量：1.6215193%→2.4397643%，增加0.8182449个百分点，1023/1024篇的相对误差增加。这不是把最终RMSNorm或“32层累计输出”误当作单层误差。

已有两轨迹同坐标stage显示：进入第32层时P95为1.6215193%；Attention残差后为1.6182517%；MLP残差合并后为2.4397643%。对应绝对RMSE中位0.0113945→0.0116184→0.0164408；参考RMS中位1.10039→1.15081→1.14591。最后一跳含真实绝对误差增长，不是近零分母。最终RMSNorm再到P95=2.8477555%，逐文相对误差比值中位1.0907055，不单独认定其为根因。

## 残差合并的能量解释

Attention后主支、MLP branch与实际合并输出都是同一批424,755,200个实值坐标，可比较能量。不同维度的QK/Gate等不进入此排序。

|量|主支 a|MLP m|实际合并 f|
|---|---:|---:|---:|
|两轨迹误差能量|68,905.1934669|71,889.8150750|138,623.317568|
|参考信号能量|585,293,967.912|664,677,519.723|567,028,569.457|

合池参考signal cross约−341,471,459.089，cos≈−0.547472；主支与MLP参考信号相消了分量信号能量和的54.636679711%。直接保存的误差cross≈−1,085.845881，cos≈−0.015428，只抵消分量误差能量和的1.542449398%。1024/1024篇signal cross为负，且信号抵消比例均大于误差抵消比例；每文signal cos中位−0.534354，error cos中位+0.005991，后者接近不相关，而不是处处负相关。

合并后相对Attention残差后的pooled relative L2倍率为sqrt((Ef/Sf)/(Ea/Sa))=1.44104226781，即增加44.104226781%。这是误差生成与参考向量几何合并的描述，不能当作算子本地舍入的因果份额。

误差能量代数项占Ef分别：主支49.7068%、MLP分支51.8598%、直接cross项−1.56661%；它们是可为负的代数项，不是独立来源贡献。直接保存cross使FP32相加导致的能量恒等式余项可算：全池0.000787917649，约Ef的5.68e−9。余项等于2〈ea+em,δadd〉+||δadd||²，不是δadd自身误差能量。参考信号cross由能量反推，含FP32相加的小偏差；已给基于u=2^-24及subnormal绝对项的保守偏差界，全池约148.76，对3.41e8量级负cross结论无影响。完整每doc cos、误差centered Pearson、signal/error交叉项和余项均在JSON。没有保存reference分支向量均值，故不能恢复signal centered Pearson，未把uncentered cosine称为Pearson。

## 本地舍入与传播仍须区分

同输入whole_mlp_local的P50/P95为0.0297064%/0.0325303%；自由两轨迹MLP branch为0.917282%/1.517390%。前者来自`mlp_metrics.jsonl`的`whole_mlp_local/current/same_mlp_input_current_vs_reference_branch/same_input_local_shadow`，由`mlp_numerical_extension._reference_branch`用原量化整数权重、同ScaleCode/prepare/SwiGLU LUT和独立exact Linear重放，同F16/S32出口及FP32 Host；不是`v5.record_mlp`中的checkpoint浮点/BF16近似参照。两数不能相减当因果百分比。

现有数据能叫“MLP输出与主支残差合并是观察到的跳升点；信号相消但两路误差几乎不相消”。不能叫“Adder本地舍入错误”或据此唯一定位Gate/Up/SwiGLU/Down哪一个是源头。缺自由两轨迹Attention各节点、两个RMSNorm出口、MLP内部各节点。A/C同层入口也会在层内逐步分叉，某stage A−C增大未必是该stage本地注入。四轨迹A=current(Hc)、B=ref(Hr)、C=ref(Hc)、D=current(Hr)应与同一实际节点入口的local shadow并列判读。R008此前在GPU前取消，无实测定位证据；R009重复36篇的o/down出口扩精度没有全面改善，不能当作1024篇唯一来源证明。

所有上述统计为固定配额合池描述；没有GPU或新模型前向，没有把不同stage的relative百分比相减作贡献。源路径/哈希：`existing_stage_review.json`、`residual_cross_review.json`；工程单层重放尚须独立收口。
