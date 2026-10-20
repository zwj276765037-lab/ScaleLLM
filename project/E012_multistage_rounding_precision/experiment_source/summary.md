# E012 R011：第32层误差来源定向诊断

用户要求快速定位具体算子，限诊断、不优化。只加载decoder index31的原7套量化线性、两层RMSNorm、最终norm与原LUT，使用R006预声明的3篇保存paired hidden30（299位置）。前31层、完整8B模型及LM head均未加载/执行。

四轨迹：A=CURRENT(Hc)、B=OUTPUT_ONLY(Hr)、C=OUTPUT_ONLY(Hc)、D=CURRENT(Hr)。原动态quantization每轨迹重算。OUTPUT_ONLY仅移除所声明的中间舍入；原Hadamard/动态ScaleCode/SiLU LUT/SwiGLU公共规则保留。A/C“同输入”指相同层入口，不指每个后续stage输入仍相同。

记录36stage的误差/信号能量、RMSE/RMS、相对L2、动态code/shift/LUT地址变化、残差能量交叉项和FP32加法roundoff；保存A/B15stage、C/D7stage raw。仅两个预声明MLP条件参考输出切点：gated_product、down_proj，并重算后缀。统计与交互分开，不以relative百分数相减作归因。

[合同](../experiment_results/runs/R011/causal_diagnostic_contract.json) · [固定输入/源SHA](../experiment_results/runs/R011/attempts/AT002_singleblock_fourway_v2/manifest.json) · [协议](../experiment_results/runs/R011/attempts/AT002_singleblock_fourway_v2/protocol.md)


---
Published: 2026-10-20T02:37:42.761565+00:00
Publication: P6e53624bbe884f24ae54fb7e565f3a4d
