# M006 有界 SLR 取证入口

这是终态后打开保存DCP的只读诊断，不改变网表、约束或物理实现，不发放物理成功凭证。R005/AT001_physopt_slr只读会话已真实启动；当前原生SLR查询结果待采，CPU准备不替代原生结果。

- `run_slr_probe.py` 验证R004父终态、归属进程退出、输入/原成功qualification/DCP及实际保存阶段，统一EDA锁与32核/192GiB保护。
- `inspect_slr.tcl` 优先采metadata、保留shared kernel双branch、MLP/Down/GU repack/A8 cache/Attention对照的逐SLR资源、实际占用SLICE、跨界、整板方向拥塞、七个旧热点窗。最多400条跨SLR路径样本，不代表全部路径/违例。
- `observe_routed_checkpoint.py` 仅在当前原root活跃、父未终态、原生已完成route和DCP导出时保存hash与日志prefix；诊断入口拒绝无此历史锚的routed来源。
- `test_slr_probe.py` 与 `check_cpu.py` 仅核入口证据规则和系统Tcl语法完整性；R005/preparation/AT005_cpu 为当前25项CPU记录，包含最后原生日志最多4个去重代表新窗解析，不能证明Vivado命令已原生成功。

父实现尚未终态时`--check-only`即拒绝。父自然终态后，选择实际存在且已完成/导出的最佳阶段：成功route用`routed`；若route自然错误且未保存该阶段，只能用实际`physopt`或`placed`，结果中保留pre-route标签与父FAIL。不得为诊断盲目重跑route。

调用例（在本项目新根；实际父阶段满足后才运行）：

```text
python3 project/E013_mlp_linear_only_hardware/experiment_source/slr_probe/run_slr_probe.py AT001_saved_stage --parent project/E013_mlp_linear_only_hardware/experiment_results/runs/R004/attempts/AT001_impl --stage physopt
```

输出R005新attempt及hardware/vivado/reports/m006_slr_*。`sections.tsv`保留每份报告的COLLECTED/ERROR/UNAVAILABLE/NO_MATCH；报告命令不适用时为PARTIAL。结果分开回答局部压力是否下降、是否足够合法布通，并与原全局route/setup/hold/CDC独立判据一起解释。

新窗取父终态日志最后Congestion Report中的代表采样，非severity全局Top4。角点先原生tile→SLR/clock_region，再查询包围clock_region矩形；资源范围不是精确INT窗。若DCP只有physopt/placed，资源仅为该早期保存布局在这些空间内的占用，不称该DCP实际route拥塞。8scope父子不相加。
