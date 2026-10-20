

<!-- research-agent:navigation:begin -->
生成时间（UTC）：2026-10-20T08:57:35.240611+00:00。来源修订：`cfb9c0cd3fc1`。

# E005 / R001 运行结果

[负责人维护的本批运行记录](run.md)

# R001 — M002 / SM009 / E005 同周期RTL优化与功能验证

execution_state: completed（RTL实现与本批功能范围）；verdict: supported/PASS local functional scope；applicability: Attention functional_delivery_v1 / AT001，MLP functional_delivery_v2 / AT003；review: A007独立审核另记，非用户最终验收。

3生产RTL已实现并冻结：Attention双wave48固定slot标量LUT6，MLP Gate/Down32默认row标量LUT1，均无新周期，保持payload异步reset/clear hold或原resetless保持、metadata、历史SRL和控制优先级。80为计划边界数量，实际新综合网表落实/资源/fanout仍待A006核验。

- [最终小facts与3生产RTL SHA256](rtl_functional_final_facts.json)
- [Attention功能结果](attention_functional_results.md) / [小facts](attention_functional_facts.json)
- [MLP功能结果](mlp_functional_results.md) / [小facts](mlp_functional_facts.json)
- [执行清单与覆盖](functional_execution_list.md)
- [v1输入SHA256](functional_delivery_v1.json) / [v2输入SHA256](functional_delivery_v2.json)
- [修改前精确小文件](frozen_before/manifest.json) / [参考唯一派生](frozen_before/simulation_reference_derivation.json)
- [15项Python静态边界核验](rtl_static_checks.json)，仅静态证明
- [Attention diff](hap_tensor24_buffers.diff) / [Gate diff](hap_mlp_projection_repack12_to16_s24_history2.diff) / [Down diff](hap_mlp_projection_repack12_to16_s32_history2.diff)
- [模块实现说明](../../../../hardware/source/m002_routability_ce.md)

AT001 Attent

（摘录截断；完整记录见链接。）

## 具体尝试与冻结结果

| 尝试 | 收据中的阶段状态 | 适用范围 | 原始结果 / 证据 |
| --- | --- | --- | --- |
| [frozen_before](frozen_before) | 未登记；查看原记录 | 未登记 | [manifest.json](frozen_before/manifest.json) |
| [AT001_attention_slot_ce_v1](attempts/AT001_attention_slot_ce_v1) | 未登记；查看原记录 | 未登记 |  |
| [AT002_mlp_output_ce_v1](attempts/AT002_mlp_output_ce_v1) | 未登记；查看原记录 | 未登记 |  |
| [AT003_mlp_output_ce_v2](attempts/AT003_mlp_output_ce_v2) | 未登记；查看原记录 | 未登记 |  |

## 本批问题与交付文件

- [attention_functional_results.md](attention_functional_results.md)
- [functional_execution_list.md](functional_execution_list.md)
- [mlp_functional_results.md](mlp_functional_results.md)

## 本批原始收据与输入身份


历史目录保持原名和原位置；新具体尝试使用 attempts/ATxxx_名称。没有收据或范围声明的结果显示未登记。

本页是原记录的导航投影；登记、送达及局部结果不代表整体验收。

<!-- research-agent:navigation:end -->
