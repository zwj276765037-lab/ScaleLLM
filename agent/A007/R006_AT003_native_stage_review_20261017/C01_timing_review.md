# AT003 C01 实际有界时序独立审核

原生query/stage均0；实际归档timing validator独立重放结果完全相同。四个方向max/min查询各cap16/nworst1，ingress20534、egress945个完整边界LOAD，64行实际路径、三份原始时序账本及四报告首路径关键段全部与已审R005相同。

| 方向 | setup最差 | hold最差 |
| --- | ---: | ---: |
| ingress | +1.416 ns | −0.128 ns |
| egress | +1.848 ns | +0.035 ns |

此前兄弟分支控制耦合、setup路径网络延时占比超94%、输入hold失败判断直接复用。LOGIC_DELAY/NET_DELAY属性仍UNKNOWN_UNSUPPORTED_PROPERTY，报告首路径提供的逻辑/网络延时不冒充属性实测。全部来自原physopt估计图，不能证明迁移后时序或正式签核；完整cut TNS未测。C02实际结果到达后集中候选取舍。

[真实身份与四组路径](C01_timing_review.json)
