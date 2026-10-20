# E012 R009：第32层真实出口提高精度

M005/SM021，A019唯一工程owner，按用户“最后一层输出也提高精度”的澄清执行。只在index31 o_proj/down_proj使用实验格式overlay：b2/b4，中间F24+b、guard/acc+b、出口F16+b、signed24+b/32+b、int64存储、drop8，HostFP32除2^(16+b)。其余节点与前31层保持原路径，生产format05/ABI文件不改。

六臂baseline/c2/c4/ref0/ref2/ref4；同R007的全部36开发文档/4494位置，每臂独立动态编码，单模型装配。主比较统一ref4；另给同格式配对和reference drift，避免移动参考。前31层逐层SHA、原attrs/functions/buffers恢复和baseline/ref0旧结果完全一致均为硬检查。

[合同](../experiment_results/runs/R009/lastlayer_precision_contract.json) · [协议](../experiment_results/runs/R009/attempts/AT003_true_exit_precision_dev36/protocol.md) · [冻结来源/输入](../experiment_results/runs/R009/attempts/AT003_true_exit_precision_dev36/manifest.json)


---
Published: 2026-10-20T01:35:40.356168+00:00
Publication: Pa898215e2117410c98c10230a618ea91
