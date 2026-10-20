# E011当前实测结果

AT020首条完整CLK raw行证明slice0URAM0连接实际输入端口core_clk/IN，leafdrivers为空，12062唯一netalias；原始1755346B/SHA36f45148保全于AT020/evidence，首row已获独立185499e2接受，整80表仍未关闭、native未终态。不能据首行称全表/selected图/G4。

此前关闭34helperD子表1906402B/3edfa18f，34/34ownQ在完整fanin，2006rawFF/C与34core_rst_n ports保留；2006实际owner/Q均在fullcone，onlycells对齐，无otherhelper/oldcore状态来源。A007正式3d6b5655限定接受。

合并隔离candidate delivery7114B/b3a1105a、CPUreceipt7376B/91f110ca：73结构/覆盖/配置/位与chain正反例PASS；collector逻辑7（4复用+受影响3PASS）；closed真实34D与80config/7360ADDR/160mode离线重放通过。后者modeowner是显式夹具投影，EN/aux/clock仍夹具；未声称原生clock/G4。流式5CPU因proc完全同字节复用，失败夹具源/log与原因保全。checks/evidence/recovery及两测试均仅proposed，v1对旧core副本/CLK双来源/链内重复decode的3个CPU误收已被独立拒收并保全，v2限定修复后新增9受影响例+2真实数据重放PASS，独立8/8，精确v2 A00720c9e2ef接受。

AT019自然native0/nullstop/survivors空，session11069实际排空；80config/7360ADDR/160mode/26960aux完整闭合。12FIRST/56MIDDLE/12LAST，12同slice无环非分支链；696空startpoints均singletonGND/VCC。68非FIRST直接ADDR未选且无驱动、直接RDB_WR_A为VCC，必须按actualCAS得有效A读/B写。66跨slice命名为共享BWE_B/EN控制。生产45源/3RTL/G2/e51核心保持；TOP01−2.896ns和22049仍OPEN，无place/route/timing成功。

两个普通测试入口main均已移至末尾，95+33=128为静态可收集数量；完整实际应用后回归尚未执行，不能写128已通过。v2检查器fd885767、checks658f6615、recovery9f658822与两测试均仅隔离proposed；生产45源未改。


---
Published: 2026-10-18T17:19:04.305640+00:00
Publication: P10b5e2508ce34d08a4572f7634d84592
