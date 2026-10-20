# AT004–AT007 原生重复与首差异独立审核

审核身份：A010；仅 CPU8–9，CUDA 不可见。范围为两条训练提示的诊断证据，不构成正式精度或修复验收。

独立检查 8 个 raw 文件 SHA，复算 392 对 native logits 与 48 对 manual/replay logits；所有 exact、finite、最大差值、形状及浮点字节 SHA 均与原记录一致。17 步、32 步序列长度完整且各自无 token 分叉，raw logits argmax 与登记 token IDs 一致。14 个冻结源文件仍与 R002 manifest 相符。详见 [机器可核查记录](determinism_review_AT002.json) 和 [复算脚本](review_native_diagnosis_AT004_AT007.py)。

| 尝试 | 第一提示 prefill 最大差值 | 第二提示 prefill 最大差值 | 原门结论 |
| --- | ---: | ---: | --- |
| AT004 | 0.125 | 0.125 | 未通过 |
| AT005：3 次预热 | 0.125 | 0 | 未通过 |
| AT006：对称探针 | 0.09375 | 0 | 未通过 |
| AT007：layer25 详细探针 | 0.125 | 0 | 未通过 |

AT004 确实在受控重复之后才抓取输入，并在每次 generate 返回后立即保存 CPU 值、释放 GPU 输出与 cache。AT006、AT007 两侧 prefill 输入元数据一致，forward 保存值与 API raw logits 一致；全部模块处于 eval，登记 buffer/参数版本/模型状态未变化。AT006 第一提示首个不同整层输出为 layer25；AT007 将首个观测差异缩至 `layer25.mlp.up_proj`，前面 layers0–24、layer25 两个 norm、Q/K/V/O 与 gate 输出全部相同。第二提示观察到的路径全部相同。

这支持观测边界定位。模块中间张量仅保留元数据/哈希，没有保存 up_proj 输入和权重字节，参数版本也不能证明权重字节始终不变，因此未建立单 GEMM 根因或可接受修复。AT008 已真实启动，其最终证据另作新审核，保留本记录的版本边界。

修复至少需固定输入/权重字节与布局、每次 mutation guard、固定与独立新分配输出的完整张量对照，以及失败提示和正常提示的无探针 native exact/finite 复验。任何 backend 或源码变更均须由主控明确新版本/R 边界，重新通过全部 30 配置的 v2 硬门、跨进程 32-token 重复和 pilot 资源验证；旧失败与已通过组不能混用为新版本验收。
