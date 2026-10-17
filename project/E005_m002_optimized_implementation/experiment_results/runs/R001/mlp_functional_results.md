# MLP 输出row CE功能结果

execution completed / verdict PASS（生产repacker局部功能）/ applicability functional_delivery_v2及AT003实际输入；A007集中独立审核另记。

A006执行AT003，A009重新打开原xsim/launcher/status：native与监督exit0、stop_reason null、无owned survivors；唯一PASS marker。原证据：[xsim.log](../../../../hardware/vivado/reports/m002_E005_R001_AT003_mlp_output_ce_v2/xsim.log)、[输入hash](../../../../hardware/vivado/reports/m002_E005_R001_AT003_mlp_output_ce_v2/inputs.sha256)、[监督终态](attempts/AT003_mlp_output_ce_v2/status.json)、[事实/证据hash](mlp_functional_facts.json)。

| 真实覆盖 | Down S32 ROWS16/MATRICES1 | Gate S24 ROWS16/MATRICES2 |
| --- | ---: | ---: |
| checker周期/冻结原版逐周期比较 | 2477 | 4821 |
| 独立列FIFO oracle输出 | 49 | 98 |
| 同拍consume/refill | 2 | 5 |
| 背压稳定周期 | 1368 | 2754 |
| reset/clear与本会输出资格重叠 | 各1 | 各1 |
| 非法顺序/mask/残余错误场景 | 16 | 17 |
| 终尾4/终尾8场景 | 各6 | 各12 |
| 输入高符号位lane | 7168 | 14456 |

独立oracle按矩阵和row缓存accepted列，凑满16列时顺序弹出；不使用DUT的pass case拼接、SRL输出或内部状态。它独立预测ready容量、pass/matrix/block顺序、metadata、输出mask、输入/输出计数、sticky错误及非法终尾残余。冻结原版比较覆盖全部外部payload/metadata/valid/ready/count/error，包括无valid期payload保持。真实211拍长stall、随机短stall、matrix交替及所有生产16row均包含在通过范围。reset/clear当拍payload保持与SRL原独立CE行为通过差分与随后不同block重入检查。

AT002 v1只因Vivado变量声明在task首次使用之后而xvlog失败，未进入功能仿真。原失败日志和完整v1 TB保留；v2只前移声明，RTL/oracle/刺激/断言不改。Attention生产源及TB未改，复用其AT001 PASS；无gold改动或删断言。

这是局部12→16列重排及周期/控制等价证据，不是SwiGLU/Hadamard/完整MLP数学链或模型ACC/PPL验收；也不证明32物理driver落实、fanout/拥塞收益、合法route、时序或板卡通过。
