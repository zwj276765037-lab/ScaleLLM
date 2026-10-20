# E011：M003选定联合版本的实施协议

依据G2 `mission/M003_joint_routability_closure/g2_joint_design_freeze_2026-10-18.md`（4424c426…）及SM014 34文件manifest6d74e85d…；只选择C-M2+C-A3+C-P1，不修改冻结原件、M004/E010或旧根。A006唯一生产/公共入口/EDA负责人，A007独立只读审核，Root维护合同与最终决定。期望Sol xhigh；实际运行模型配置未核验。

R001是同版RTL、局部/联合回归及入口正负例；新综合和完整物理各另R。原始AT/job/源归档不可覆盖。AT001相对$0校验路径失败；AT002五本地native通过，新增core native虽打印PASS但精确marker未独占行导致收尾失败；AT003只修marker重验并补无force production smoke。不得把这些收尾失败写成RTL失败，也不把局部PASS写成整体时序成功。

平台为VCU118、xcvu9p-flga2104-2L-e、Vivado/XSim2025.2 Build6299465；core100MHz、双DDR UI200MHz、原05数学/ABI/双DDR和E005 input48/outputCE32不变。全部编译/XSim/Vivado共享`.m002_eda.lock`；CPU0–7、nice5、max8、合成并发1。owned PID/start树RSS>192GiB、MemAvailable<48GiB持续30s、disk<30GiB才触发资源保护。没有墙钟/静默强停；不运行bitstream/板卡/GPU/PPL/ACC。命令退出后仍监测已核归属子树直至排空，再释放锁。

局部期望来自独立队列/整数算法/保全旧模块；M2 TILE9 parent旧/新/独立队列差分、真实完整branches/kernels的DT4生产宽dispatch及default TILE2兼容dispatch分开。A3为全81920容量mode1/default0对旧模块与独立内存/token/count/format参考，读写同址旧值、stall、非法81920/131071、S/L/R事件、L+R尾NBA、abort-only与async reset；helper用真实UNISIM进行131072 carry/wrap。实际cohort core boundary强制的仅环境/state/preload/ready，真实A/helper/pending/NBA/sideband/tags/storage路径逐沿比较，明确不声称整板端到端。无force完整production top smoke执行实际AXIL读/响应背压/公共维护与生产参数资格；没有完整层命令/DDR事务，不占用M004的producer/joint流程。

联合回归为现有cohort16 integration、two-wave复用、v5调度/gather、MLP与全算法reference、builder源/ROM和M002安全/恢复测试，同版三RTL SHA不变。旧测试需要hardware/tests在PYTHONPATH，首轮缺此路径的导入失败保留；最终按正确路径运行。SM016 fixture模式仅验证检查器，不能产生native或G4通过。负例覆盖来源、正式注册、缺失/重复角色、错CE/master/bit、unknown/fixed/macro、同容量错CR/SLR、越池/cascade、merge/unloaded/cross-slice、S/L/R/clock/reset、URAM读写配置、25/80保护及restore缺约束。

`m003_entry_manifest.json`冻结所选生产源、overlay/data/spec、当前builder/物理/检查/owned supervisor。构建器正式注册overlay为enabled、global、implementation-only、LATE；原被拒mission0004/0005仍被拒。native原XPR生成candidate registration原件；implementation临时子工程消费该原件/源身份，避免把临时read_xdc默认属性误作原XPR政策。恢复先核candidate registry与独立review/checkpoint包，随后检有效pblock/角色/资源集，绝不先重加overlay掩盖丢失。

G3a/G3b真实证据与A007无阻断后，直接`run_m003_owned.py -- … run_m003_stage.py --stage create/synth`新建项目并正式综合。新图需23生产synth/OOC与22实际consumed DCP逐hash绑定，不能复用旧RTL DCP。原生helper/81CE/6560+6560/40+40URAM/34counter/C01/80保护及完整pin/config资源图必须核验。M2新81LUT1；A3≤96LUT、34FF、≤8CARRY8；联合≤177LUT、FF增量≤34，无额外URAM/BRAM/DSP；精确新增锥与A007已核同stage同metric E005 report差值分别检查，拒绝改名route或错器件/工具报告。

SM017使用新native INIT，显式opt_design及实际需要的implement_debug_core；复用原严格时钟覆盖、reset/IO结构、CDC分类/未知critical、debug实际时钟关系、DRC和全局容量判据。G4正常成功停于新post-debug preplace包，独立审核该实际包无阻断后，A006据A007原review派生绑定，直接SM018：place SSI_SpreadSLLs、phys_opt Default、route Default，增量关闭、不扫seed。允许结构合法但负时序的一次诊断route，最终验收不降标。正常失败保全原AT后只作同范围适配；结构/池/片数/预算/策略变化报Root重新冻结。

所有阶段起止、原生退出、原始输入/工具/数据/XDC/IP身份、资源样本、幸存进程及报告在AT/job记录。TOP01 −2.896ns清空至控制读取路径未直接处理，22,049统计差异OPEN。任何新综合网表/布局/route/时序结果未产生前均写待核，不承诺一次布通。最终合法route、全时钟setup/hold/PW及原+0.5ns余量、DRC/CDC/reset/IO/bus-skew与可复现性逐项验收。


## 2026-10-19T08:12:12.132042+00:00 用户最新管理覆盖：仅每小时分析

用户要求「不需要一直盯着项目进程 太浪费token了 只负责一小时一次的分析」。从此取消工程持续轮询、agent驻留等待及每阶段唤醒，取代上文常驻观察/逐阶段followup/本轮自动连续重试机制。当前AT027和原run_m003_owned.py资源保护监督保持正常运行，不强停EDA，不动锁/guard/冻结源；A006无额外纯观察进程，未停止任何进程。A007由Root另行安排核身份结束自己只读observer。本轮不启动新EDA/重试、不做新技术审核。后续仅由每小时有界检查发现结果后触发必要分析，具体调度由Root管理；A006保留project唯一写入owner，本轮结束。
