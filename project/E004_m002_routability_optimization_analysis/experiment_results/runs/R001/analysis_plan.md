# R001：物理证据分析与一次只读检查点查询计划

SM008合同适用；A006唯一EDA/工程写入者，R001与agent/A006所有；他人并行，只读生产，无后代。期望gpt-6.1-sol/xhigh、实际模型未独立核实。

现证据清单见existing_evidence_inventory.json；控制集合原报告22,410行已CPU复算，原生Bel Load Count合计1089753及按CE/SR来源的桶（不是FF1019698口径）见control_sets_existing_analysis.json。来源桶不是负载模块归属，slice_load不可相加成站点。

基线CLB146472/147780=99.11%、LUT814935/1182240=68.93%、FF1019698/2364480=43.13%。控制集合22410、FF slices内unused slots28860。关键缺口：目标模块每SLR/CLB BEL实际填充、高扇出与跨界分布、属性阻碍及失败样本物理位置。

## 单次只读查询

R001/AT001：先验证成功physopt DCP SHA c6944eeeafb1d58776f2f3b85ecec61ddd283ff0b367d53b997e2c091696ff91，再一次open_checkpoint，保存2025.2 help、native查询脚本/命令/日志/资源/退出。

1. 目标层次：全局hier util；Attention input/output/context/postprocess/projection、MLP整体与gate/down projection_repack、PCIe/XDMA、DDR。优先native report_utilization层次/SLR；补聚合primitive/ref、放置SLR、CLB/LUT/FF BEL填充直方图，只有小型汇总，不导出全图。
2. 属性：目标层次/primitive的DONT_TOUCH、KEEP/KEEP_HIERARCHY、ASYNC_REG及固定LOC/BEL；工具不支持的属性/选项原样记录，不当作false。repack定向SRL16E/FF位置、CE与SLR。
3. 高扇出：现SLR-crossing32项复用，新增定向capture_index bits、input_fire、known MLP4控制、repack CE，以及top10失败样本nets的drivers/loads数量、SLR/物理包络。上下文/存储宽bus只抽目标接口/代表，不做全设计net graph。
4. 位置：失败INT tile/top10信号映射到成功physopt的SLR/位置；明确布局位置是route前父点，失败router没有DCP，无法复原全量失败路由图。对原生拥塞窗口做SLR/clock-region归属。
5. 工具：保存原生help place/physopt/opt/route/report_high_fanout/report_utilization等，核directive在2025.2是否存在及作用阶段；只分析下一次候选，不安装。

单lane，CPU0–7/max8/nice5，RSS192GiB/MemAvail48GiB持续30s/disk30GiB，正常计算无wall/无输出强停。仅open/report/get和输出分析文件，不opt/physopt/place/route/set_property设计/write_checkpoint/bitstream。原DCP、RTL、XDC和既有报告只读。真实fatal/输入/资源异常按事实处理。

## 后继流程分析

只提出route失败时先保存失败DCP、route_status、时序/拥塞/DRC，再保持原始错误返回的catch/finally设计；不在本轮安装，不以捕获成功改写原native成功。最终报告区分现事实、候选因果、反证与下一次测量判据。
