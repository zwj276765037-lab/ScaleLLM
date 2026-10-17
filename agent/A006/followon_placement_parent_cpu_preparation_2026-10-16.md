# 后继纯放置实验：原父链和入口的CPU准备

此项仅由主控授权准备原DCP、约束及策略身份；不启动EDA，不复制DCP，不改生产或E006冻结运行源。新合同、目标选择器在原OPT/pre-place实际命中以及新物理实验仍未执行。

## 可复用原检查点

| 身份 | 原路径 | 字节 | SHA256 |
| --- | --- | --- | --- |
| 原始E005 OPT | `project/hardware/vivado/reports/m002_E005_R004_AT001_fresh_place_physopt/opt.dcp` | 218327530 | `af634c358eecf869c83cb45c0755d0164b39d5a9f5aed316bcaa52cd3c02919e` |
| AT002继承OPT，同字节 | `project/hardware/vivado/reports/m002_E005_R004_AT002_native_OPT_POST_recovery_place_physopt/opt.dcp` | 218327530 | 同上 |
| 已准入pre-place | `project/hardware/vivado/reports/m002_E005_R004_AT003_current_CDC_bound_OPT_place_physopt/debug_materialized.dcp` | 396068466 | `8451b2a86885d5ebb7bcb58dc24c352ac442492425c174269f9a803bb39c202f` |

以上全部重新读取hash，并检查DCP package的part/top/board/tool；均为xcvu9p-flga2104-2L-e、scalellm_vcu118_f05_bd_wrapper、VCU118、Vivado2025.2/build6299465。原OPT是完成opt_design的真实检查点，原始POST失败不改写；pre-place的phase为debug_materialized_pre_place，已有[完整准入](../../project/hardware/vivado/reports/m002_E005_R004_AT003_current_CDC_bound_OPT_place_physopt/pre_place_evidence.json)。若新合同采用已准入pre-place，可避免重复综合/OPT/debug；这不是当前新运行的准入或安全签核。

## 约束和策略

约束模式为embedded_checkpoint_inherited。已核162个现存注册XDC的原hash；另13个原始`.Xil`生成临时路径目前不在，但均有原`source_archives`明确映射，保留的generated_phy/debug snapshots逐一重hash全等。因此175个记录来源全部有身份依据，不重建临时路径，也不重复加载历史XDC。原4个项目约束文件全部匹配，board_clock_domains.xdc的处理顺序为LATE，其他3个为NORMAL；ddr_timing_recovery.xdc没有添加placement或timing exceptions。

项目候选策略为Vivado Implementation Defaults；OPT=Default、place=SSI_SpreadSLLs、physopt=Default、route=Default；AUTO_INCREMENTAL_CHECKPOINT=0、INCREMENTAL_CHECKPOINT为空。真正执行依据是原生[implementation_run.log](../../project/hardware/vivado/reports/m002_E005_R004_AT003_current_CDC_bound_OPT_place_physopt/implementation_run.log)第208/215行的place SSI_SpreadSLLs和第1136行的physopt Default，不只依据XPR设置。

已有[m002_resume_physical.tcl](../../project/hardware/vivado/scripts/m002_resume_physical.tcl)支持post_debug_pre_place恢复分支；open_checkpoint创建临时project后恢复执行政策，以直接命令directive执行。原launcher绑定E005合同，新实验必须使用自己合同和AT/report/source/附加物理约束身份，不把原impl_1 FAIL改称成功父链。

## 必须在新运行实际核对

77,360是physopt图中候选primitive数量，不保证原OPT/pre-place图命中。实际选择的原检查点打开后，逐根/叶核精确NAME、REF、IS_PRIMITIVE、数量、去重及cache/bundle排除，再核目标SLR属性读回。候选差异如实保留并按新合同处理，不用physopt名字猜匹配成功。

验收以native exact hierarchy资源报告加闭合primitive/site/LOC互斥CPU统计为主，不重复大leaf-list report_utilization成本。原hold/正式CDC/reset/IO安全及合法routed验收未完成；本CPU准备不改变E005失败终态。

完整身份见[准备receipt](followon_placement_parent_cpu_preparation_2026-10-16.json)，77398B/SHA256 `f451933a965e9067faf05e9274050f48bd7fba9338e7b5da0f5d34a03a27ccdb`；其中原13临时路径缺席观察保留，其身份补证见[archive resolution](followon_placement_parent_constraint_archive_resolution_2026-10-16.json)，11686B/SHA256 `868b8d6a616bd62ca80905627133717b0525e0d23a75949a9341709c5135652d`，175来源全有依据、未解决差异0。实际producer见[CPU脚本](prepare_followon_placement_parent_cpu.py)。
