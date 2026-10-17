# E003：阶段结果

129项CPU入口验证及实际339综合输入/45 DCP来源检查通过，5份生产/测试文件安装身份已核。复用原完整AT008 debug/pre_place，RTL/XDC/算法/时钟未改。当前及后继阶段按用户补充取消固定墙钟强停。

本轮实际Vivado于12:22:11 UTC启动，fresh恢复检查通过；place_design于14:36:01 UTC真实完成，native Tcl0、耗时7295秒（2小时1分35秒）。closed place.dcp为579080094 bytes，SHA256 `37591435c8f95383a0910978b986c035a102c762b24b69b76e59b63d49e905f7`；工程全包CRC/身份及稳定性通过，主控独立核3项小证据链接。[布局事实](runs/R002/attempts/AT001_full_pre_place_restore_place_physopt/place_checkpoint_facts.json)。

正式placed时序仍FAIL：WNS−1.819ns/TNS−818.651ns，1014个setup失败端点；WHS−0.620ns/THS−2150.556ns，33141个hold失败端点；WPWS/TPWS均0、该栏失败0。A007核最差setup在PCIe→XDMA；core100MHz本域WNS−0.317ns、28个setup失败端点。独立bus-skew摘要94项均非负，最小+3.015ns；不关闭正式reset/CDC安全。[正式时序事实](runs/R002/attempts/AT001_full_pre_place_restore_place_physopt/place_timing_facts.json)、[原报告身份](runs/R002/attempts/AT001_full_pre_place_restore_place_physopt/place_physical_reports_facts.json)、[独立审核§4](runs/R004/architecture_review.md)。

正式资源LUT68.93%、CLB站点占用99.11%，不能混同两种指标。拥塞12个方向/类别组合均报告至Level6，多个热点局部URAM/RAMB或DSP100%；48行窗口有嵌套/重叠，不是48个独立失败。top32跨SLR高扇出网中4条与BUFG优化跳过名单精确重合，实际为SLR0驱动、SLR0/1两侧大量负载，涉及MLP控制；这提供布局/高扇出风险线索，尚未证明全局最差时序或最终路由根因。

15:08:08 UTC place POST实际因 `critical_CDC: new/unclassified critical CDC path` 退出1。Critical总数仍8；精确差异仅DDR1两个AUX目标的报告源由ready末级改为base_reset末级，clock pair/目标及其余6项不变。当前reset_structure和fanout均qualified，唯一gate问题为新CDC tuple未获分类；仍需核实际组合锥，不能只按数量相同豁免。[实际CDC差异](runs/R002/attempts/AT001_full_pre_place_restore_place_physopt/actual_place_CDC_delta.json)。

无固定时限或资源终止：新监督真实取得worker1，确认子树终态后才结束暂停的旧supervisor；旧manager管理性−9与Vivado/worker1分开。15:08:16状态无survivors；主控15:10:49独立复算两资源源132+1837样本，峰值34706485248 bytes及内存/磁盘低值与status一致，全部9个tracked身份和两supervisor均无对应PID/start_ticks幸存。[真实终态](runs/R002/attempts/AT001_full_pre_place_restore_place_physopt/status.json)。

AT001原失败和完整布局点/正式报告保留，独立physopt/route未运行。工程按既有授权做窄CDC核查、受影响验证与合法placed恢复，继续补POST→独立physopt→route；不重跑成功place，不热改或放宽算法/接口/时钟/安全验收。


---
Published: 2026-10-15T15:12:53.338287+00:00
Publication: P7fbec729333843068c95c0e9f058dc0d
