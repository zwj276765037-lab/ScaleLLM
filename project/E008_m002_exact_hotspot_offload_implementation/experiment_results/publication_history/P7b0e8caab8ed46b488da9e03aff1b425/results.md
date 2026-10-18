# E008：PDU后AT004已实际恢复，尚在网表恢复阶段

用户明确“可以继续了”后，AT004_C01_PDU_resume_full_implementation已于2026-10-17T09:23:05.136988Z（北京时间17:23:05）真实启动。[原生启动事实](runs/R001/attempts/AT004_C01_PDU_resume_full_implementation/native_start_verified.json)：39归档源匹配b9dc、144生产输入保持、父DCP8451匹配，supervisor14547/start69484、native14680/start70786，CPU0–7/nice5与唯一项目EDA/锁一致。当前初始化/恢复正式父网表，完整pre-place/place/physopt/route均待本AT完成。

重启环境核验通过：workspace原路径rw ext4、boot_id1342c043…，初始MemAvailable493.74GiB、磁盘391.64GiB；真实入口验证、全部旧owners结束及lane空闲已核。Vivado2025.2 build6299465版本确认；本机node-locked许可lmdiag0，lmstat的无SERVER仅不适用于该许可类型，实际原生place仍需checkout。未改消费源、原合同、选型或验收。

AT003于08:44:09Z按用户PDU关机指令停止，14项收尾和[独立恢复输入核查](../../../agent/A007/E008_PDU_resume_review_20261017/AT003_stop_and_resume_input_review.json)通过，原始停止记录保留。它已完成并独立接受完整restored preplace，但place Phase1.3中断，没有当前E008 DCP；AT004从冻结debug_materialized父图重新加载和资格，不能恢复中途place。无需重做综合/OPT/debug或无关功能测试。

当前C01方法仍未取得迁移后物理结论。原AT001/AT002入口自然失败与修复、AT003用户停机不作C01方法反驳；无place完成、physopt、route合法性或正式时序通过结论。Hadamard、ScaleCode、format05、ABI、core/双DDR时钟及全部禁区保持。


---
Published: 2026-10-17T09:25:06.578918+00:00
Publication: Pa2056d0d6dfa4db09df418591b2ef659
