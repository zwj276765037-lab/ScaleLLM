# E011：M003联合可布线版本实施

依据Root G2正式冻结（mission/M003_joint_routability_closure/g2_joint_design_freeze_2026-10-18.md）与SM014 manifest6d74e85d。selected C-M2（按原CR head42/tail39个LUT1）、C-A3（2×128bit×81920、34同沿地址FF、单控制器）、C-P1（正式overlay、C01hard-SLR2保留）。仅project/hardware；M004/E010和旧根/旧包不动。

R001为SM015/SM016同版RTL、局部/联合功能和入口正负对照；后续新综合和物理另R登记。全部源/基线/工具/实际运行身份见各AT和job收据，仿真不替代新图/时序。资源预算新增34FF/≤177LUT/≤8CARRY8、URAM总80且40+40，80边界/数学/周期原样。CPU0–7/nice5/max8、单EDA、RSS192GiB/avail48GiB持续30s/disk30GiB，无墙钟/静默强停、无bitstream/板卡/GPU/PPL/ACC。

---
Published: 2026-10-18T04:04:47.977317+00:00
Publication: P91aa504ae3554b88b625176121195252
