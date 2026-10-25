# A023 启动配置

- 任务：M006 / SM026 / E013 Host数值支撑。
- 父代理明确配置：gpt-6.1-sol / xhigh；本运行未通过独立API取得模型遥测，不将配置文字当测量。
- 实际运行身份：协作代理 `/root/mlp_linear_host_reference`（父代理已真实创建并派发任务）。
- 角色：engineering；无后代。
- 根路径、所有权和资源见 [mission.md](mission.md)。
- 技能：已读取research-agent/hardware-agent及engineering/hardware/console参考，采用合同内连续实现与独立整数证据。

## CSR测试支撑续接

继续复用实际协作代理 `/root/mlp_linear_host_reference`，父代理明确沿用gpt-6.1-sol/xhigh。此轮只新增TB/manifest并更新A023四md；不创建后代，不运行EDA。A022是生产RTL与真实仿真的唯一owner。

## revision3生产整合TB续接

Root明确复用gpt-6.1-sol/xhigh与当前协作身份。实际完成源码/static/Python窄参考复算；A023不执行EDA。当前可用metadata/compute/transport端口均来自真实生产图，A022拥有生产参数和故障屏障修复。

## 新板级入口与参考修复续接

复用同一实际协作身份/父配置，未创建后代。实际仅系统Tcl8.6.14/Python3.12.3与静态阅读/小型CPU参考生成；无Vivado/xsim执行。公开Vivado Tcl接口按本地安装2025.2的doc/eng/man核对（report_route_status/report_cdc/report_drc/get_timing_paths/report_compile_order/report_timing_summary/check_timing/get_clocks/get_drc_violations），不依赖猜测参数property。

## GU-only Host与v7 CSR续接

复用相同角色/配置，无后代。实际CPU Python3.12.3/NumPy1.26.4，affinity最多8核、BLAS/OMP/MKL1、RLIMIT_AS8GiB与available64GiB保护。Host分26项数值/任务和16项真实adapter/fake transport测试，均native0；无GPU/板卡/EDA。CSR只编写测试台/manifest并静态检查，真实仿真交A022。
