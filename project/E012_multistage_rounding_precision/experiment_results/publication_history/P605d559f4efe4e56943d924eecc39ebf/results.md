# E012 多级舍入：当前结果

execution_state: running（R003开发资格已完成，准备R004正式首批）
verdict: inconclusive（尚不能宣布总体精度保持）
applicability: 单模型、真实≤128token前缀；开发文档局部/32层数值传播；正式1024篇尚未测
review: A014已完成AT007/AT010限定范围独立核查

AT010真实completed：374.403秒/native0，RSS约2.067GB、ownGPU约15.678GB，worker231065回收，20源码不变、共享权重不变。只加载/量化一次，四篇开发文档真实长度如下；相对L2是当前实现与仅输出舍入之差相对参考信号的百分比。

| 开发序号 | 真实tokens | 最终Host RMSNorm相对L2% | 整对前向/统计秒 |
|---:|---:|---:|---:|
|0（预定raw审计）|128|2.22103278|约51.64|
|1|14|1.64295975|约6.43|
|2|128|1.75551075|约6.05|
|3|128|2.15268328|约6.03|

每篇32个hidden层、384个local site、每臂192动态准备坐标及最终norm统计覆盖齐全。四篇是开发/吞吐观察，formal=0；不据此估总体尾部或修改精度门槛。第一篇耗时含raw/节点见证与冷编译，另外三篇不能直接代表所有21..128长度的正式冷编译成本。

[AT010主结果](../experiment_results/runs/R003/attempts/AT010_four_document_numerical_development/paired_result.json) · [逐层hidden](../experiment_results/runs/R003/attempts/AT010_four_document_numerical_development/document_summary.json) · [局部指标](../experiment_results/runs/R003/attempts/AT010_four_document_numerical_development/local_document_summary.json) · [最终norm](../experiment_results/runs/R003/attempts/AT010_four_document_numerical_development/final_norm_document_summary.json) · [终态收据](../experiment_results/runs/R003/attempts/AT010_four_document_numerical_development/gpu_receipt.json)。原执行证据188.64MiB，后附源码/独审文件后仍低于256MiB。

384/384见证无skip。A014独立整数/Fraction current/reference全部一致：Linear3584、RoPE2048、QK512、Softmax65280、PV512个展开标量；Linear622592组qa/zp/qw点积全部重算并对dynamic源切片。Softmax中32297为valid、32983为causal-masked，不能65280作有效分母。见证适用界0违例；见证pair最大输出码差依次1/1/3/7/1，均只是审计子集描述，不是总体最大值。audit doc0的完整hidden/final/meta和预定values已独立复算；其余三篇只有聚合统计，未声称全raw逐元素独审。[独审附件](../experiment_results/runs/R003/attempts/AT010_four_document_numerical_development/independent_audit/A014_audit_AT010_result.json)

AT007单dev文档32token完整资格315.132秒，末层hidden相对L2=2.17886771%，最终RMSNorm=2.39008556%；局部384 cell中最大relativeL2约0.08533%。较小局部差不代表传播不累积。[独立分开的局部/传播图](../experiment_results/runs/R003/attempts/AT007_complete_paired_numerical_qualification/plots_v2/continuous/plot_current_vs_reference_manifest.json)明确1开发文档，不作正式精度通过图。

AT001/AT009已冻结1024文档及其真实token输入，模型数值正式measured仍0。AT004旧BF16数组工程资格21tensor/168输出与先前已独审scalar结果逐码/精确Fraction一致；不混入新V5正式分母。R001/R002历史仅合成/单BF16文本局部恢复，不支持总体数值保持。

独立metric_uncertainty通过12项工程test及A014495组整数二项核验；域内条件P95/P99与32/64 family、零信号/失败处理、n256 P99无界均落实。没有验证iid假设，也不把固定配额合池1024写成iid精确CI。下一R004首批最多16篇，具体完成数只看新真实收据。
