# MLP SiLU(Gate) × Up

- Production 锚点：`hap_mlp_silu_mul`；链级锚点为两个 row-local producer/lane。
- 输入/输出：Gate/Up S24 Q8.16 → SwiGLU product S32 Q16.16。
- SC leaf 是可停顿四级流水，填满后目标为 1 element/cycle。
- 当前完成的 FP16/FP32 baseline 从免费给定的浮点 Gate/Up 开始实现 SiLU 与
  乘法，只属于 `operator-only`；已经报告单 leaf 和 production 两 lane 顶层。

## Boundary-inclusive 主口径（RTL/TB 已落盘，待 Vivado 验证）

- 孤立模块从共同 Gate/Up S24 payload 开始，FP 计入两路 fixed-to-float 与
  等价输入 buffering；SC 使用 production S24 四级定点路径。
- 完整 MLP 链中 FP Gate/Up 直接来自 native-FP Gate/Up accumulator 并保持
  FP 到 SiLU×Up，不重复执行 fixed-to-float；主结论必须综合
  Gate/Up→SiLU×Up 非重叠链顶层。
- SwiGLU product 的共同观察点保持 S32 Q16.16；继续进入 native-FP Down 链时
  只在真实 product→A8 producer 边界按其独立合同处理。

## 已冻结的 boundary workload

`model/generate_boundary_vectors.py` 已生成 12 个固定 seed、每 seed 512 个
Gate/Up pair，共 6,144 vectors。9 个 `.mem` 保存共同 Gate/Up S24、显式
FP16/FP32 fixed-to-float 输入和三路 S32 SwiGLU reference。独立 verifier 使用
production `mlp_fixed.swiglu_product_s32` 与 8192-entry SiLU LUT 重算全部 SC
golden，并核对转换值、文件宽度/数量和生成器/model/data 哈希。manifest
SHA256 为 `a9f253be24dd48fc54297900c91f44268c963d81b10ac9618809ed1b811bc568`。

```bash
cd /home/user/EDA-202/zhuowenjun/ScaleLLM/ModularExperiment
python3 experiment/10_mlp_silu_multiply/model/generate_boundary_vectors.py
python3 experiment/10_mlp_silu_multiply/model/verify_boundary_vectors.py
```

当前 verifier 输出 `M10_BOUNDARY_VECTOR_VERIFY_PASS files=9 seeds=12
vectors=6144`，二次生成目录聚合哈希完全一致。workload 覆盖 3,090 个负 Gate、
3,053 个正 Gate、8 个 S24 endpoint，以及 1,166/1,149 个低于/高于 SiLU LUT
区间的样本。

## 真实 Llama trace workload

`model/generate_trace_vectors.py` 从正式 trace 的 Gate/Up BF16 tensor 选择
2 samples × layers `{0,15,31}` × tokens `{0,1,15,31,63,95,111,127}` ×
128 个 intermediate channel，共 6,144 vectors。通道从 `[0,14336)` 以精确
stride 112 均匀取样；每条 coordinate 和两个源 tensor payload hash 写入 CSV。
Gate/Up 都以 nearest-even 转为共同 S24 Q8.16 输入，再生成 production SC、
FP16、FP32 三路 S32 golden。

独立 verifier 在临时目录重新读取 12 个源 tensor 并重生成；硬件 payload
逐字节比较，manifest 结构与非浮点字段严格相等，浮点归约指标允许 `1e-13`
相对容差：

```text
M10_TRACE_VECTOR_VERIFY_PASS files=11 vectors=6144 source_tensors=12 manifest_numeric_rel_tol=1e-13 manifest_sha256=bc7b6a64fe7efd65692b9baf91b190c0a7e7ad1b9023aa4211c2eed0ee16492b
```

相对捕获 BF16 Gate/Up 的稳定 FP64 SwiGLU，SC/FP16/FP32 RMSE 分别为
`2.1860990e-4`、`8.4334996e-5`、`4.4131891e-6`；相对共同 S24 输入的
FP64 reference 分别为 `2.1860979e-4`、`8.4334977e-5`、`4.4128258e-6`。
Gate/Up BF16→S24 均无饱和，三路 S32 输出也均无饱和。真实样本未越过
±16 SiLU LUT 边界；该极值覆盖继续由 12-seed synthetic workload 提供，不能
用真实 trace 替代。

runner 已支持 `run_boundary_xsim.sh sc|fp16|fp32 0|1 trace`。当前只完成
软件 workload，等待共享机器空闲后再串行做 RTL replay。

双 lane boundary RTL、TB、FP IP 生成 Tcl、XSIM 与 OOC 入口脚本已经落盘并
通过静态完整性预检。SC 复用两条 production `hap_mlp_silu_mul`；FP 每 lane
计入两路 S24 Q8.16→FP32 转换，FP16 路径再执行 narrow，并用 reservation-
counted FIFO 吸收非阻塞转换器与 core 的背压。TB 使用全部 6,144 vectors，
覆盖 continuous/periodic backpressure、双 lane 独立顺序、输出稳定性以及
input/conversion/core/output counters。

create_boundary_all_fp_ip.tcl 是自包含的 boundary FP IP 配置；公共 OOC
runner 会直接哈希并保存它，因此正式结果不会漏记由嵌套 source 引入的
IP 配置。

这只证明实现和脚本已准备完毕；Xilinx IP 的实际 latency/端口、数值容差、协议、
周期、资源与时序仍必须由首次 Vivado elaboration、XSIM 和 OOC 验证，当前不得
把这些 RTL/TB 作为硬件 PASS 证据。
