# E012 R007：等位宽中间舍入候选

M005/SM021，A019工程负责。用户针对第32层累计误差授权快速数值纠正试验。新增独立软件候选，保持生产v5及R001–R006冻结源；R007不部署RTL、不重跑ACC/PPL。

仅将Linear组对齐和可选PV逐项右移改为有符号quotient/remainder nearest-even，inactive code先将effective shift置0；原有限guard/acc宽度、wrap、出口half-away/sat、QK、权重整数码、ScaleCode/Hadamard/format05、LUT和Host保持。候选固定为Linear-last1、Linear-all32、Linear+PV-all32。共同参考为原独立OUTPUT_ONLY实现，不以candidate替换。

单份模型驻留；每臂重新执行32层全部192动态activation/KV编码坐标。前4开发文档/398位置用于冻结联合规则初筛，Linear-last1进入后续32开发文档/4096位置验证。所有计划文档及真实位置纳入，原hidden、指标、尾部、审计与runtime保存。本批数据不称heldout正式1024。

CPU17059例Fraction oracle及GPU511向量/30Linear/256PV输出通过；源码AST边界核查及A015独立静态审核通过。前4 baseline/reference的hidden哈希、L2、Top1、TV与R006全等。

候选SHA256：`3a01f438bb6fb1c8fce899ab7acf3e43ee2e0af197a4d547ce45ef3f596fd2f9`。运行源结束SHA复核不变。Python3.10.19、torch2.10.0/CUDA12.8、transformers5.3.0、triton3.6.0；GPU0 RTX A6000、driver580.178.04（环境版本于同环境postrun读取，推理前已有安装源SHA冻结）。

[合同](../experiment_results/runs/R007/optimization_contract.json) · [冻结协议与命令](../experiment_results/runs/R007/attempts/AT001_rne_equalwidth_dev36/protocol.md) · [来源身份](../experiment_results/runs/R007/attempts/AT001_rne_equalwidth_dev36/manifest.json) · [环境](../experiment_results/runs/R007/attempts/AT002_cpu_postprocess/tool_versions.json)


---
Published: 2026-10-20T01:01:05.795069+00:00
Publication: P5374ac080ed74293b7c514b78f31d8af
