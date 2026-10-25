# R006：GU-only v7 硬件功能验证

A022唯一RTL/EDA owner。有效完整schema SHA318cf64064354aed52943fd21909aa8b67f11ca8fb565a37c65441d522d4938a。
新GU文件/manifest与旧v6分开，实际运行用run_mlp_gu_sim.py；8CPU/96GiB，单重锁、无墙钟或静默停止。

已完成行为PASS：AT004两列37bit等价；AT006cache128；AT007REC576；AT012真实双8×12 GU N128/fullK128；AT013完整opcode/owner/error优先级；AT016GU生产tensor字节及AXI错误；AT018真实metadata loader/bank/scheduler及padding7。
AT019真实production N128/fullK128整合运行中；AT020/022focused metadata仅syntax，AT021full生产shape仅syntax。
准备失败/编译失败/AT017 TB握手等待失败均保留，不能从后续PASS删除失败历史。

真实source复用对照在preparation/source_reuse_current.json；CE位重映射6550bit覆盖在gu_parent_ce_mapping.json。
单元mock quiescence、lane两列、bounded输出形状与完整生产层次/资源资格分开；实际当前终态以各attempt result.json/日志为准。
