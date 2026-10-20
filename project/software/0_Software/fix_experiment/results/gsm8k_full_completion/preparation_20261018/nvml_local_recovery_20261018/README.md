# 项目内显卡监控恢复

2026-10-18 实测恢复。内核驱动为580.159.03，系统NVML/CUDA用户态库为580.178.04。项目内从NVIDIA官方HTTPS包仅解包匹配版本，未安装驱动、未替换系统库、未复位或重启。

入口：`bash nvidia_smi_local.sh`，可附`-q`等原工具参数。脚本仅给此次进程指定项目内NVML库，且检查当前内核版本。系统默认`nvidia-smi`未被改写。

来源、归档内部校验、完整SHA及两个私有库身份见[local_library_receipt.json](local_library_receipt.json)。首次真实查询见[nvml_query_20261018T0425.xml](nvml_query_20261018T0425.xml)：两卡可读取；GPU1 ECC disabled，Xorg PID2653占用38MiB。ECC统计N/A不能解释为无错误，监控恢复不等于GPU1数据完整性修复。

`cuda_lib/`另供新的隔离进程做匹配CUDA库对照，不能热替换正在运行的GPU0/1进程库。GPU1原始内存错误和匹配库复测由相邻`gpu1_repair_20261018`目录保存。
