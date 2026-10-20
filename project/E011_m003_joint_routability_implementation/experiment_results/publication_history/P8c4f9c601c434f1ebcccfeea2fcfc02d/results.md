# E011当前实测结果

AT019于16:22:19.460375Z自然native0，stop=null/survivors空、峰值12940132352B（约12.05GiB）；session11069实际finalexit0排空。完整80URAM、7360ADDR/CAS地址、160mode、26960aux输入记录已关闭/hash；45源/3RTL/G2/e51核心身份不变，4trackedPID+supervisor退出、EDA锁可取得释放。

实测FIRST12/MIDDLE56/LAST12。696空startpoints均有singletonGND/VCC驱动；只12FIRST的ADDR_A22直接GND，其余68非FIRST的直接ADDR_A/B各1564条无driver，须结合实际CAS选择解释。aux仅CLK80条无leafdriver（standalone顶层input候选），其他auxdriver非空。动态native all_fanin startpoints为FF/C、directdriver为FF/Q，原始值保持，不迎合检查改写。

首cell92行已获独立14b398c8限定接受；完整数据独审进行中。helper D_startpoints是否需API语义适配及CLOCK端口需下一小probe真实证据，无selected全图/预算/G4/place/route通过。AT018自然失败事实与两次apply独立成功保留。TOP01−2.896ns/22049 OPEN。


---
Published: 2026-10-18T16:33:27.823451+00:00
Publication: P878b6a74f40a4dd9af72ae1ea2ef33d2
