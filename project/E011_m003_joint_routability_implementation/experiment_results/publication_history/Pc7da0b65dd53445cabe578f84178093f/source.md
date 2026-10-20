# E011：M003联合可布线版本

G2正式冻结4424c426选择C-M2（81区域CE/13120 parent FF）、C-A3（双128bit×81920/34同沿地址FF/单控制器）、C-P1（正式overlay和C01 hard-SLR2/25保护保留）。三RTL已实现，原数学/ABI/时钟/双DDR/80边界不变。R001执行同版功能/入口检查，R002执行正式新工程/综合/严格preplace；SM018后继完整物理另R。

全部编译/XSim/Vivado单EDA、CPU0–7/nice5/max8/合成1、RSS192GiB/available48GiB持续30s/disk30GiB，无墙钟/静默强停；无bitstream/板卡/GPU/PPL/ACC。旧根、冻结原件和M004/E010不动。当前source manifest d1f90456/42源；工具环境最小适配5Tcl+1helper，生产三RTL不变。

---
Published: 2026-10-18T04:23:55.830794+00:00
Publication: P142a05578d554eadb89480f8dda65faa
