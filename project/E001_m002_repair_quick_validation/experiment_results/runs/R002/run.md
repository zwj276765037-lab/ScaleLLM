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

工作目录 `/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/hardware`。每次必须新report目录/AT，原始终态不覆盖；工具继续由项目资源负责人串行调度。

最终权重argv：`vivado/scripts/run_xsim_tb.sh hap_axi512_dual_engine_dedicated_read_tb tb/hap_axi512_dual_engine_dedicated_read_tb.sv vivado/manifests/m002_dedicated_weight_tb_sources.list HARDWARE_AGENT_SIM_PASS`。

最终native argv：`vivado/scripts/run_xsim_tb.sh hap_m002_dedicated_frontends_tb tb/hap_m002_dedicated_frontends_tb.sv vivado/manifests/m002_dedicated_frontends_tb_sources.list HARDWARE_AGENT_SIM_PASS`。

上述运行环境均 `HAP_JOBS=8`、`HAP_XSIM_TIMEOUT_SECONDS=180`，精确 `HAP_XSIM_REPORT_DIR` 见各AT command.json。data/CSR精确argv同样见其各AT command.json。

## 限制

不代表完整模型/32层/双cohort ACC/PPL、实际SmartConnect/MIG事务仿真、setup/hold/CDC静态签核、综合资源或性能、bitstream、板卡闭环。实际BD保留4条跨主地址重叠critical并附内部decoder静态解释，未据此放行正式implementation。Host KV仅保留地址区，未新增或验证off-chip KV生命周期。
