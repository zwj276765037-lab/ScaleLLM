

<!-- research-agent:navigation:begin -->
生成时间（UTC）：2026-10-18T00:06:15.625771+00:00。来源修订：`943abfac7fc3`。

# E003 / R002 运行结果

[负责人维护的本批运行记录](run.md)

# 当前：R002/AT002完整成功终态，已自动交接route

新AT002从原closed place点恢复，fresh guard/完整新place POST、独立physopt（16:19:46Z→16:38:12Z，1106s，native0）及其完整POST全部通过。worker/native/supervisor均0，于17:16:53.390716Z闭合；13原跟踪身份消失、无survivors，见[终态事实](attempts/AT002_closed_place_POST_physopt/terminal_facts.json)。1205样本独立重算peak31102734336B/minMem429566685184B/minDisk501595344896B与status一致。

closed physopt DCP SHA c6944eee…，568389035B，25成员CRC及平台身份通过；正式WNS−1.290/TNS−762.165/setup980，WHS−.620/THS−2150.556/hold33141，仍timing FAIL。完整POST当前结构/fanout/14原语与8Critical窄分类通过，新未知0、正式安全OPEN。[完整POST事实](attempts/AT002_closed_place_POST_physopt/completed_physopt_POST_facts.json)。成功父链在driver和route worker实查通过，独立R003/AT001已启动恢复源physopt点，native route_design待开始。原place/OPT/debug不重跑，AT001原POST失败保持。以下为此前过程记录。

# 当前：AT002完整新place POST通过，独立physopt已真实开始

新AT002原生place_result为completed1/eligible1、gate_issues=[]；current实际结构/fanout/14原语export及8 Critical CDC（新未知0、两条DDR1 base代表源）窄分类通过。原生日志严格记录完整place POST完成后才Command: phys_opt_design。见[64件闭合phase证据与事实](attempts/AT002_closed_place_POST_physopt/completed_place_POST_facts.json)。新place DCP全25成员CRC/平台身份PASS，SHAf2ba76…；WNS−1.819/TNS−818.651，WHS−.620/THS−2150.556，仍timing FAIL。独立physopt当前运行，未获其完成回执/DCP/POST；同

（摘录截断；完整记录见链接。）

## 具体尝试与冻结结果

| 尝试 | 收据中的阶段状态 | 适用范围 | 原始结果 / 证据 |
| --- | --- | --- | --- |
| [AT001_full_pre_place_restore_place_physopt](attempts/AT001_full_pre_place_restore_place_physopt) | 未登记；查看原记录 | 未登记 |  |
| [AT002_closed_place_POST_physopt](attempts/AT002_closed_place_POST_physopt) | completed | actual fresh complete place POST and independent physopt0/closed DCP/full POST; original place/OPT/debug historical receipts retained; timing FAIL, formal safety OPEN; route separate | [执行收据](attempts/AT002_closed_place_POST_physopt/run.json) · [report.md](attempts/AT002_closed_place_POST_physopt/report.md) |

## 本批问题与交付文件


## 本批原始收据与输入身份


历史目录保持原名和原位置；新具体尝试使用 attempts/ATxxx_名称。没有收据或范围声明的结果显示未登记。

本页是原记录的导航投影；登记、送达及局部结果不代表整体验收。

<!-- research-agent:navigation:end -->
