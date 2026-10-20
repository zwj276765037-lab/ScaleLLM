# E012 R007：等位宽舍入候选

M005/SM021，A019唯一工程owner。用户明确授权针对第32层累计误差快速纠正优化；仅隔离软件候选，不更改生产v5或R001–R006冻结源。

候选仅把Linear组对齐和可选PV逐项右移改为nearest-even，保持原guard/acc wrap/出口half-away/sat、QK、ScaleCode/Hadamard/format05与Host。固定比较baseline、Linear-last1、Linear-all32、Linear+PV-all32，以及原有独立OUTPUT_ONLY参考；每臂重算动态activation/KV代码，单份模型驻留。

先dev前4（398真实位置）按meanTV优先并约束finalhidden/logitL2中位及Top1错数不退筛选，再对next32dev独立验证选中候选。报告第32层pre-norm/finalhidden/fullvocablogitL2、温度1全词表TV、Top1、全部尾部及guard/sat/runtime。本批不作heldout1024、任务ACC/PPL或RTL时序结论。

CPU17059例独立Fraction oracle及GPU511向量/30Linear/256PV输出全部通过。原语通过后同一PID装载模型，实际load36.398s、attach347.182s。资源GPU0唯一UUID，CPU1/RSS8GiB/GPU24GiB/总GPU阶段2400s/证据512MiB。

[合同](../experiment_results/runs/R007/optimization_contract.json) · [冻结协议](../experiment_results/runs/R007/attempts/AT001_rne_equalwidth_dev36/protocol.md) · [来源身份](../experiment_results/runs/R007/attempts/AT001_rne_equalwidth_dev36/manifest.json)


---
Published: 2026-10-20T00:54:20.722145+00:00
Publication: P4d963b8e981e47eb8477e22492a3454a
