# Attention 固定slot功能结果

execution completed / verdict PASS（限定范围）/ applicability functional_delivery_v1及AT001实际冻结输入；独立审核由A007另记。

A006执行AT001，A009重新打开原日志和监督终态核验：native与监督exit0、stop_reason null、无owned survivors，唯一PASS marker。原证据：[xsim.log](../../../../hardware/vivado/reports/m002_E005_R001_AT001_attention_slot_ce_v1/xsim.log)、[监督终态](attempts/AT001_attention_slot_ce_v1/status.json)、[输入hash](../../../../hardware/vivado/reports/m002_E005_R001_AT001_attention_slot_ce_v1/inputs.sha256)、[事实和证据hash](attention_functional_facts.json)。

真实覆盖：1265488周期全接口/两个wave无valid期payload逐周期冻结原版对照；1263504个256-bit slot独立DMA地址oracle比较；192个wave×slot×reset/clear×写前/后中断，每次新epoch完整重载，196 epochs；4次完整双wave×128group图像；13591背压稳定检查。末slot写前/写后各4，valid中断4，非posedge异步reset97，wave0/group127边界reset/clear中断2均由实际覆盖计数及断言确认。数据包含地址/word标记和epoch互补；原断言/gold未更改。

这些结果支持固定目的写保持原周期、异步payload reset、clear hold、双wave组顺序及新epoch无旧payload泄漏；不证明综合网表48边界落实、fanout/拥塞改善、合法route、setup/hold/PW、正式CDC/reset安全或板卡通过。MLP功能尚待其独立AT结果。
