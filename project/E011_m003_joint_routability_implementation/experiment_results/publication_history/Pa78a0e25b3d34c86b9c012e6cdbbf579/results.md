# E011 当前结果

A007实际G4 no_blocker=true，绑定AT035 package94e3f335，真实review06954c10；正式reset/CDC safety仍OPEN。G4允许进入固定物理，不等于物理成功。原AT035完成debug Tcl0/blackboxes0/COMPLETE_INTERNAL/gate=[]/新critical0，outer native1来自preplace后的冗余close_project，未改写。

R003/AT001实际启动时间为2026-10-19T18:20:23.378500Z。supervisor700439/start12363065，native700547/start12363405。198 owned归档绑定/51运行源全部匹配，实际CPU0–7/nice5、EDA锁与原192GiB/48GiB×30秒/30GiB保护通过。尚无restore完成、place、physopt或route结果；preplace WNS+0.904/WHS−0.814/PW−0.012仅为前置阶段，不能作最终签核。

AT027综合预算LUT+111/FF+34/CARRY8+4、RAM/DSP不增，TOP01−2.896ns/G1差22049继续OPEN；合法route、最终时序、正式安全尚未宣告。

19:22:22Z一次小时有界观察：原native700547/start12363405仍在且无终态，日志已实际调用place_design SSI_SpreadSLLs，布局前DRC 0 Errors，当前Phase2.1 Floorplanning。树RSS26.49GiB/MemAvailable464.53GiB/磁盘367.43GiB，未触发资源保护；没有place完成或route结果。

21:23:31Z小时实查：原生place_design completed successfully，elapsed02:14:59，0 Critical Warnings/0 Errors、160 Warnings。原生place.dcp已生成，仍在完整place POST（report_utilization后timing update）。这只是原生命令/检查点完成，不替代尚未完成的全部POST及独立阶段审核。原native仍在，无终态/保护触发。


---
Published: 2026-10-19T21:23:58.910211+00:00
Publication: P75ac5163242548998a8a682948eff19d
