

<!-- research-agent:navigation:begin -->
生成时间（UTC）：2026-10-25T01:29:20.089604+00:00。来源修订：`7fd112f32442`。

# E001 / R002 运行结果

[负责人维护的本批运行记录](run.md)

# R002 · SM002 / A004 · 专属 DDR RTL 快速功能验证

- execution_state: completed
- verdict: pass（限专属路由、原生reader/半组/组、AXI数据口、CSR定向功能）
- applicability: 当前6份RTL和4份最终TB与PASS回执SHA256一致，见 `data/final_source_identity_check.json`；权威SHA清单 `data/rtl_worker_final_inputs.sha256`。
- review: submitted；M002整体审核由父主控负责。
- 主控后续记录（2026-10-15）：限定范围核查完成，见 [SM002审核](../../../../../results/reviews/SM002.md)；用户全局验收未发生。
- 负责人：RTL `/root/m002_rtl_repair`；工具唯一串行调度 `/root/m002_build_verify`。
- 工具/平台：Vivado/XSim 2025.2；每AT `tool_versions.txt`、`command.json`、`status.json`、`inputs.sha256` 为精确身份/环境/命令/起止时间/退出状态。

最终通过：AT002 data（11checks），AT003 layout CSR（10checks），AT008 weight/group（38checks），AT009 native frontends（7checks）。完整board RTL elaboration另属R003 AT004：88RTL、1,327,023 elaborated hierarchical cells、0 blackbox；无正式综合/implementation。

所有AT001/004/005/006/007失败保留。根因分别为新adapter声明顺序（已修）、TB读取旧complete的delta race（只修采样）、group oracle always@*未time0初始化（只修always_comb并增加非X硬断言）。AT007实际完整256bytes另经独立CPU逐字地址模型核验，见 `data/AT007_independent_oracle_crosscheck.json` 和复现脚本。

完整修改清单、各AT真实结果/数字/证据、独立期望、BD别名critical及未覆盖范围见 [worker_report.md](worker_report.md)。

## 精确复现入口

工作目录 `/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/hardw

（摘录截断；完整记录见链接。）

## 具体尝试与冻结结果

| 尝试 | 收据中的阶段状态 | 适用范围 | 原始结果 / 证据 |
| --- | --- | --- | --- |
| [AT001_dedicated_weights](attempts/AT001_dedicated_weights) | 未登记；查看原记录 | 未登记 |  |
| [AT002_dedicated_data](attempts/AT002_dedicated_data) | 未登记；查看原记录 | 未登记 |  |
| [AT003_memory_layout_csr](attempts/AT003_memory_layout_csr) | 未登记；查看原记录 | 未登记 |  |
| [AT004_dedicated_weights_full_groups](attempts/AT004_dedicated_weights_full_groups) | 未登记；查看原记录 | 未登记 |  |
| [AT005_dedicated_real_frontends](attempts/AT005_dedicated_real_frontends) | 未登记；查看原记录 | 未登记 |  |
| [AT006_dedicated_weights_full_groups](attempts/AT006_dedicated_weights_full_groups) | 未登记；查看原记录 | 未登记 |  |
| [AT007_real_frontends_diagnostic](attempts/AT007_real_frontends_diagnostic) | 未登记；查看原记录 | 未登记 |  |
| [AT008_final_weight_groups](attempts/AT008_final_weight_groups) | 未登记；查看原记录 | 未登记 |  |
| [AT009_final_real_frontends](attempts/AT009_final_real_frontends) | 未登记；查看原记录 | 未登记 |  |

## 本批问题与交付文件

- [worker_report.md](worker_report.md)

## 本批原始收据与输入身份


历史目录保持原名和原位置；新具体尝试使用 attempts/ATxxx_名称。没有收据或范围声明的结果显示未登记。

本页是原记录的导航投影；登记、送达及局部结果不代表整体验收。

<!-- research-agent:navigation:end -->
