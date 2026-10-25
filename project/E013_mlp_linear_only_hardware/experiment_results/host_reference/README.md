# M006 Host整数参考与codec实测

A023于2026-10-24完成实现。首次CPU执行 **32 tests PASS**，unittest耗时5.832s，退出码0，无资源保护触发。运行身份：[AT_20261024T030431628513Z](AT_20261024T030431628513Z/manifest.json)，[原始日志](AT_20261024T030431628513Z/unittest.log)。Python3.12.3、NumPy1.26.4；CPU affinity为0–7，BLAS/OMP单线程；子进程ru_maxrss=78,396KiB（约76.6MiB），最低系统available约448.7GiB。原始源码/ROM/schema等11个SHA、8组随机输入逐数组SHA、保存的NPZ/HEX/BIN SHA、命令/环境/退出码与资源均在manifest。运行前后被测源身份一致。

## 可用API

实现位于 `project/hardware/host/scalellm_mlp_linear.py`，测试位于 `project/hardware/tests/test_scalellm_mlp_linear.py`，以 `PYTHONPATH=project/hardware` 导入 `host.scalellm_mlp_linear`。

| API | 输入与输出 |
| --- | --- |
| `hadamard32_s24_exact` / `hadamard32_s32_exact` | 整数数组，最后轴为32倍数；返回同形int64承载S27/S35 |
| `minmax_a8_scalecode_exact(x, input_bits=27或35)` | 返回q（uint8同形）与meta（uint32，shape[:-1]+(groups,)）；S35 D>4,269,834,239抛出MLPLinearFormatError |
| `pack_a8_rec576(q,meta)` | q=(16,groups*32)，meta=(16,groups)，单组meta可为(16,)；严格验证再打包bytes |
| `unpack_a8_rec576(payload, groups=...)` | 严格长度、padding、reserved、canonical-zero；返回上述row-major q/meta |
| `unpack_gu_interleaved_s24` | 精确1,376,256B，返回Gate/Up两个(16,14336)整数数组 |
| `silu_table_mul_exact` | 同形S24 Gate/Up，返回S32整数；直接用冻结ROM及RTL隐含top entry |
| `unpack_down_s32` | 精确262,144B，tile16-major→(16,4096)整数 |
| `prepare_gate_up_input` | (16,4096) **已完成RMSNorm且形成S24** 的整数→73,728B REC576 |
| `prepare_gate_up_input_from_normalized_fp32` | 现有Host已完成RMSNorm的FP32结果→S24 boundary→同上；不重复RMSNorm |
| `prepare_down_input` | 完整GU payload→SiLU乘Up/S32→H32/S35→范围检查→258,048B REC576 |

所有整数API拒绝float/bool数组，输出保留F16原始整数单位。独立的 `s24_from_normalized_fp32` 复现当前FP32 scale/half-away舍入与S24饱和；在整数转换前clip，使极端有限FP32也按数学S24饱和语义处理；该语义保持既定舍入/饱和定义，不声称逐位复现旧helper在超大有限FP32上的潜在int64转换溢出bug。正常既有FP32边界与当前公共helper逐字节对照通过，范围见上述测试。现有公共Host函数无需修改。

## 独立期望与覆盖

- H32：原 `fixbit_v2.hadamard32_normalized` / `mlp_fixed.hadamard32_product_normalized`，全部16行×128/448groups，零/冲激/交替/正负极值/half-away ties，S35结果明确超过S32范围。
- MinMax与ScaleCode：原两个整数helper逐项比较q/zp/code/shift；含零、正负常量、RNE ties、scan阈值、code ties、D=4,269,834,239及+1。原S35 helper超界仍夹码返回的情况，新入口拒绝；实际极值GU→Down验证拒绝且未调用pack。
- SiLU：冻结8192词ROM SHA为 `8263e8981b637b00143c6dfd6674f2397a73c85c6ed8934f0ee839f76db6ea67`，加隐含+16词后与旧生成参考8193词全部一致；每个地址midpoint两侧、±16端点、16×14336正负乘积和舍入ties。生产无浮点SiLU。
- Codec：由独立标量byte索引/`int.to_bytes`/`struct.pack_into`产生期望，非只做同实现往返。覆盖所有16行/128与448groups、GU所有896tile与两个matrix、最后32列block（tile894/895）、Down256tile所有列/行、正负极值；row10 metadata跨beat16/17及record7跨4KiB。非法padding/reserved/canonicalzero、缺失/多余byte或beat均拒绝。
- 两个完整Host生产prepare路径以旧数学参考和独立字节打包逐位对照。没有执行全层权重矩阵计算。

int64安全界：最大H32中间为32×2^31×11585<2^50；SiLU×Up≤2^46；S35差值<2^35，255×x与255×D均<2^43，RNE的2×remainder<2^36；ScaleCode扫描operand≤4,261,478,400。代码中的宽度校验发生在转换前，不会把uint64高位静默截成负数。

## 复现与硬件TB向量

从工程根运行 `python3 -B project/E013_mlp_linear_only_hardware/experiment_results/host_reference/run_cpu_tests.py`；它建立独立时间戳AT目录、冻结被测四份数学源、保存输入/身份/日志，限定8核/96GiB RSS与64GiB系统available底线。真实测试命令为 `python3 -B -m unittest discover -s project/hardware/tests -p test_scalellm_mlp_linear.py -v`（完整环境见manifest）。

AT内 `tb_rec576.bin` 为独立合法16行单组记录；`tb_rec576_beats.hex`有18行AXI256词，每行64个hex字符且byte0在LSB；`tb_q_rows.hex`有16行，每行32个U8以lane0在LSB编码；`tb_meta_rows.hex`有16行U24 metadata。可用readmemh直接加载，预期q/meta由独立标量索引构造。

适用范围：合成输入的CPU定点边界、Host流程与ABI布局。未加载真实32层模型权重，未改权重bytes/hash；未运行RTL/EDA/GPU/板卡。吞吐/真实应用调度/整模型准确率/板级端到端均未验证。

## 后续：生产整合TB独立gold

[生成器与全部值身份](integration_gold/manifest.json)保存完整数学参考的源码、实际命令、10240个输出/guard_sum、32KiB packed gold、96条SV row常量、六个固定值复算及与TB嵌入row逐项一致的证据。复现：从工程根运行 `python3 -B project/E013_mlp_linear_only_hardware/experiment_results/host_reference/integration_gold/generate_integration_gold.py`。这是独立CPU整数参考，未跑Vivado。AT024原SV参考实现未通过time0自检，尚未解释该失败根因；以同公式独立Python实现替换，保留六literal与全部DUT比较，不将此替换当作RTL通过。
