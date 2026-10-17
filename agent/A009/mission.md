# A009 / SM009 / E005 实现任务

有效合同：[优化implementation合同](../../mission/M002_ddr_separation_and_timing_recovery/optimized_implementation_contract_2026-10-16.md)。角色工程实现；主控 `/root`。

独占三生产RTL：Attention hap_tensor24_buffers.sv；MLP s24/s32 history2 repacker；直接受影响TB、模块说明、E005/R001解释和A009。保留他人改动，不写共享摘要、物理/构建脚本、索引或旧工程。

实现48个固定slot LUT6边界和32个row LUT1边界，组合同拍，保留所有payload/metadata/reset/clear/valid/历史SRL/周期语义。验收须冻结原版逐周期差分及独立oracle：Attention双wave/128group/每slot reset/clear新epoch/长stall；Down S32 ROWS16/MATRICES1，Gate S24 ROWS16/MATRICES2；payload/metadata/count/error及consume/refill。

A006唯一EDA调度；本agent不启动编译、仿真、Vivado，除非其明确交付串行时段。项目共享1 EDA、8CPU/nice5、RSS192GiB、MemAvailable48GiB连续30s、disk30GiB；无墙钟/静默强停。无bitstream/板卡/GPU/PPL/ACC。

里程碑、异常及时实际消息给主控/A006，准备好先交可运行TB；功能通过不等于综合物理收敛。
