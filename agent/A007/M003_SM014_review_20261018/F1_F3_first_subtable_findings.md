# 首个F1子表的独立发现与F3依赖

2026-10-18；A007。[机器审核](F1_first_subtable_review.json)已经完成：审读工程提取算法，并独立关联工程导出小表，不重复原115/269MB扫描。工程实际执行48084 exit0；本次不能冒称第二次原生导出或原始全表复算。

13137个精确FF包括head6560、tail6560、meta17；位范围及全部Q读者与生产字段映射一致。6560个tail Q均只有一个已导负载，逐位匹配同bit head D driver helper。head真实Q6560和helper6949分开，meta真实Q17和helper18分开。head总Q负载8294pin是实际pin计数，不等于6560位或原冲突网数。

head Q/D/CE均完整；tail Q/CE完整而D未在固定选集中；meta Q/CLR完整而D/CE未导；全部C未导。缺失是查询范围限制，不是无连接或零成本。head D helper上游也只导出命中选集的一跳输入，不能称完整上游fanout。

元数据17位各自驱动全部12个直接地址URAM，共204地址pin，另47个非URAM负载pin。12个直接URAM全SLR1、跨物理X1/X2/X3列，不能直接等同全部80或按名称索引推logical lane。它支持比较真实跨列消费者的局部化机会，但没有证明收益、确定片数或提供新图映射。

进一步检查现有CE小表：head的6560 FF由同一个CE canonical网驱动，真实driver为SLR2的`parent_head_r[6559]_i_1/O`；tail的6560 FF同样由SLR2的`parent_tail_r[6559]_i_1/O`驱动。这些CE网canonical名称含`parent_head_r[0]`/`parent_tail_r[0]`，**不能据名字把它们当成payload bit0的Q**。真实driver和REF_PIN_NAME才是归属依据。

因此，若选完整双分支、两entry字段银行，payload从13120增至16576 FF（+3456）的算术之外，每个entry的存储由6560增至8288，公共CE名义负载各增加1728，clock负载总增3456；payload依原合同不增加宽reset。这是选项成本，尚未选入。若分别生成局部CE组合锥，必须计其窄控制输入、LUT、控制集合/兼容打包及防合并成本，不能增加clear/握手周期。

private字段在Q端已是单分支读者；将其head/tail/选择逻辑重定位，可能把原Q跨区线转移到source→D或tail→head。shared字段复制也可能把原共享Q跨区改成输入D跨区。F3必须同时列原/新完整连接图的边界，不用Q端局部化单独承诺净布线收益。实际缺失物理D/clock只约束依赖那些事实的方案；可由已核RTL给出结构预算的部分明确标估算，不能把估算冒充已测距离。
