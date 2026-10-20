# E011当前实测结果

AT020于16:38:25.830432Z实际启动session74874/supervisor86001/leader86002/start3111217/native86095/start3111314，原e51core消费/包fa5e/reviewc1d0/唯一锁owner86001已绑定；初始RSS3.74GiB。当前载核心，34D/80clock是采集目标，不是已取得原生结果。

AT019于16:22:19.460375Z自然native0，stop=null/survivors空、峰值12940132352B（约12.05GiB）；session11069实际finalexit0排空。完整80URAM、7360ADDR/CAS地址、160mode、26960aux输入记录已关闭/hash；45源/3RTL/G2/e51核心身份不变，4trackedPID+supervisor退出、EDA锁可取得释放。

实测FIRST12/MIDDLE56/LAST12。696空startpoints均有singletonGND/VCC驱动；只12FIRST的ADDR_A22直接GND，其余68非FIRST的直接ADDR_A/B各1564条无driver，须结合实际CAS选择解释。aux仅CLK80条无leafdriver（standalone顶层input候选），其他auxdriver非空。动态native all_fanin startpoints为FF/C、directdriver为FF/Q，原始值保持，不迎合检查改写。

首cell92行独立14b398c8保持；完整80cell及终态已独立ee740a27限定接受（issues0），12条同slice级联链有效A读/B写按实际选择确认。66条aux跨slice命名已定位为共享BWE_B/EN控制，无CAS/address跨片违规。helper D_startpoints是否需API语义适配及CLOCK端口需下一小probe真实证据，无selected全图/预算/G4/place/route通过。AT018自然失败事实与两次apply独立成功保留。TOP01−2.896ns/22049 OPEN。


---
Published: 2026-10-18T16:40:10.314665+00:00
Publication: Pa291694988ce4e5897a95d4f52607d05
