# 下载包范围与复核

> 以下说明针对完整Release ZIP；Git目录仅是阅读子集。请从[下载页](DOWNLOADS.md)取得完整包后运行下述解压复算命令。

本包是2026-11-02的KV128、16请求七轨PMBus功耗补测证据包。先阅读[REPORT.md](REPORT.md)，正式结果仅使用`results/main_004_*v2*`和`results/summary.json`。`native/main_004`中的16个原始文件全部包含；预检、pilot、smoke、失败尝试及测后只读检查也一并保留。

本包结论为PARTIAL_WITH_LIMITS：12个窗口采集完成，空闲和完整解码步的6个完整窗口均值已建立；Attention/MLP的6个完整窗口有缺口，仅提供共同覆盖段均值。原启动器FAIL和采样器原生退出码未知未改写。

`source/analysis_final/README.md`提供仅用本包功耗日志离线复算CSV/JSON/图的命令；不用连接板卡或执行测量脚本。`source/build_report.py`从最终分析JSON重建报告和简表。`source/main_004`保留实际运行源码，其板上运行还依赖既有模型、驱动、PowerTool及发布运行环境，不能视为完整自包含的上板工程。

冻结源码README中的命令以原仓库根目录为起点。**单独解压本ZIP时**，先进入`kv128_repeat_sevenrail`目录，使用以下等价命令；只需Python 3标准库，不访问板卡，也不覆盖原始文件：

```bash
python3 source/analysis_final/kv128_sevenrail_windows.py \
  --metadata native/main_004/telemetry.json \
  --jsonl native/main_004/telemetry.jsonl \
  --windows native/main_004/workload/windows.jsonl \
  --commands native/main_004/commands.jsonl \
  --target-period-ms 140 --output recomputed_analysis.json
```

预期输出SHA-256为`a00d62ac8031a1c3dd2b642f0804323c87429f5383106b5c48a2c57ff07f4bf7`。绘图另需Matplotlib；同一目录运行：

```bash
python3 source/analysis_final/kv128_sevenrail_figures.py \
  --analysis recomputed_analysis.json \
  --metadata native/main_004/telemetry.json \
  --jsonl native/main_004/telemetry.jsonl --prefix recomputed_figure
```

打包时明确排除：

- `native/inspection_attempt_002/readonly_inspection_002/kv_snapshot.bin`：256 MiB的全层KV二进制仍保存在原本地证据库。本包保留其SHA-256、检查报告、转存记录及恢复验证日志；仅凭本包无法重新逐字节比对这个完整二进制。它不是离线功耗复算的输入。
- `results/superseded_contained_only/`和`results/superseded_prestatus/`：被更正/替代的派生结果仍在原本地目录，包中不重复附入。原始采集文件没有排除或修改。
- Python缓存文件：可重新生成，不作为实验原件。

以上排除项及大小/哈希列在`PACKAGE_MANIFEST.json`。所有纳入文件也逐项列出SHA-256；清单本身不递归纳入自己的哈希。压缩包同目录的`.sha256`记录整个ZIP身份，解压后可按清单核查内容。

CSV空单元格和JSON的null表示不支持、未建立或没有有效值，不能当作零。七轨合计是指定稳压器输出遥测，既不是整板输入，也不是已建立的严格BUSY物理功率。
