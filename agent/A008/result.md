# m002_rtl_routability_explorer：结果交付

内部记录ID：A008。

SM008 / E004 / R002 已交付 [定向RTL报告](../../project/E004_m002_routability_optimization_analysis/experiment_results/runs/R002/rtl_routability_analysis.md)、[小证据](../../project/E004_m002_routability_optimization_analysis/experiment_results/runs/R002/rtl_evidence.json)与[复算脚本](../../project/E004_m002_routability_optimization_analysis/experiment_results/runs/R002/recompute_rtl_evidence.py)。主控统一维护E004三摘要和生成索引。

17目标RTL与当前实际综合/physopt绑定manifest及route active构建一致；10打印重叠节点的30次信号提及已全部定位到源family/精确行号，综合临时net映射缺口明确保留。核心结构为6144b两级选择+快照、16row双768b postprocess、projection局部数据/control复制；全部规模是源码声明/逻辑估算，不是综合网表FF。

最小同周期候选的fixed-slice/CE方程和验证义务已给出：112是双wave48+context64的显式decoder边界实例数，净LUT变化未知；综合网表同构则不视为有效修复。input数据reset资格、singlebank最多12288b payload复用、frontend768b窄化和共享loader分级列出；singlebank仅parent合法phase消费可能等价，全端口可见性/既有non-destructive测试义务保留。高半3072b常量零不能计节省FF。

execution completed；verdict supported（source-only）；candidate benefit/equivalence inconclusive；applicability为本报告17个hash绑定源；review待主控/A007。未改生产文件、未运行EDA/功能仿真，不能保证下一次route布通。重要阶段已实际通知主控/A007；最终消息回传后由父整合。

后续主控定向补查已完成：报告§9追加现有TB入口/覆盖/缺口。input双wave TB覆盖全部24槽×256group和短stall；context TB覆盖16槽但仅wave0/group5；两者均无运行中reset/clear。给出最小中断/new-epoch/pending/drain补测义务，compute stub/全零测试的局限和runner旧timeout策略明确列出。新证据`R002/tb_regression_mapping_evidence.json`；原冻结报告已保留revision，原receipt未覆盖。本次仍无生产修改/仿真/EDA。
