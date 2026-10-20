# R005 常驻执行与独审接口资格

截至本记录，静态实现与独立 CPU 测试无阻断；此结论只支持按冻结合同执行，整体数值精度仍为 inconclusive。实际 GPU 是否完成、1024 文档结果和最终 PNG 必须由真实终态及后续独审确认。

直接来源为活动版本 `extended_session_cache.py` 的 `context`、`run_extended_numerical_session.py` 的 `validate_plan/execute_groups/outputs`、`bounded_extended_session.py` 的 `directory_bytes/monitor/finalize_manifest/main`；精确版本 SHA 见同名 JSON。装配只缓存模型加载、V5 挂接与原始输出头三个 API；同 checkpoint/device/format 的对象被重用，各组仍使用冻结测量入口。分组 `execution_receipt.json` 是同一个真实 GPU 进程的片段，不是独立 GPU launch。

已核修复：更新 JSON 使用原子替换；输出签名仅含实验数据；总存储计入所有兄弟分组；计划读取前后校验身份；执行身份暂不可取时仅有界回收自有直接子进程；临时文件恰好被原子替换的 FileNotFoundError 不误报运行失败。其余来源、资源、覆盖与 I/O 异常保留失败语义。

本次亲自执行缓存 2 项、编排 8 项 CPU 测试全部通过（0.003s、0.072s）；独立扩展 checker 5 项通过（3.212s）。测试范围包括两组合并/失败保全、来源改变、覆盖遗漏、有限退出、临时文件消失、独立同 LUT 乘积和 Host、原始 BF16 头与 dot 重算、shared-process 身份拒绝。CPU fixture 不计入正式文档。

新 checker 已绑定真实 global completed/native0/reaped/source unchanged，逐组核对 canonical 路径、shared PID/starttime/PGID/argv、完整 1024 global roster、源/输入/输出 SHA、共享 loader/head 来源。旧 core auditor 源不改，只在 `/tmp` 建只读路径视图，报告显式携带 canonical group 与 shared runtime，结束删除视图。单组 combined checker 上限 60 秒、CPU 1、RSS 8 GiB；该上限不是预测总耗时。

后处理源码 `make_inputs.py/aggregate_final.py/render_final.py` 本版静审无阻断：要求完整 1024 和所有明确组/独审身份，不接受开发数据；域内区间条件为未验证 IID，family=1；固定域配额合池仅描述；P99 上端点无穷保留；零信号与不可估样本不丢弃。13 列区分同输入局部、同 LUT 精确乘积出口损失、整 MLP 分支干预及连续路径末端；Top1 一致性不等于任务准确率。最终真实 PNG 尚需数据完成后目视审查。

适用范围保持最多 128 个真实 token、32 层 prefill；原始见证为预选文档/位置，未声称每个完整分支都被独立重执行。LM-head 浮点归约误差与位宽舍入差异分开报告，无统一“通过”阈值。
