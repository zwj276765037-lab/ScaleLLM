# ScaleLLM MLP Down S45/S54→S32/F16 修复与硬件交接方案

> 目标模型：Llama-3.1-8B-Instruct  
> 目标数据流：V5 production full-chain、Hadamard32、Group32、A8W4、ScaleCode  
> 最终候选 ABI：`0x48384605`（`0x48384604` 仅为 Down-S32 中间候选）  
> 当前状态：**软件精度 APPROVED；真实 RTL/Host 迁移仍为 HOLD，达到 15/15 审计前不得硬件签核。**

## 1. 已确认的故障与修复边界

故障不是“MLP 没做 Hadamard”，也不是 Gate/Up 的 Group32、ScaleCode、
S37 guard 或 S44 accumulator。Gate/Up 输入使用 S24/F16 Hadamard，SwiGLU
乘积进入 Down 前使用 S32/F16 Hadamard。第一处错误位于 `down_proj` 的末端：

```text
S32/F16 SwiGLU product
→ Hadamard32 S35/F16
→ Group32 U8 + ScaleCode
→ A8W4 Down
→ [旧格式] S37/F24 group guard
→ [旧格式] S46/F24 accumulation over 448 groups
→ round-away by 8 bits to F16
→ [错误] saturate to S24/F16
→ Host FP32 residual
```

S24/F16 只能表示 `[-128, 127.9999847412]`，而 layer 31 的软件 trace 已观测
到 Down 参考绝对最大值 `587.8696`。旧硬件孪生的 MLP-only 和 Full V5 分别
出现 `20,251` 和 `18,044` 次末级输出饱和。Down-S32 中间候选解决了该问题，
并使 Full V5 全量 ACC/PPL 通过。

随后 MLP-only 全量 ARC-Challenge/WinoGrande 压力测试又观测到 Down 的
`total_shift_min=12..13`。旧合法范围 `[20,44]` 会产生
`391,016,448` 个 total-shift format events 和 `65,688,536` 个数学 S37
guard overflow events，并由 RTL zero-guard 丢弃对应贡献。因此最终修复范围为：

> 保持 MLP 输入、Gate/Up 输出、Gate/Up S37/S44、Hadamard、Group32 和外部
> A8/W4 数据格式不变；Down 合法 total shift 扩为 `[12,44]`，Down group
> guard 扩为 S45/F24，跨 448 groups accumulator 扩为 S54/F24，最终输出及
> 后续传输 ABI 改为 signed S32/F16。每个 packed S24 Gate/Up lane 在进入
> SwiGLU 的 32-bit 运算器前必须按 bit `[23]` 符号扩展，禁止零扩展。

## 2. 软件先行验证状态

统一使用 matched `hardware_128` 协议：完整 WikiText-2 test，2,257 个
非重叠 128-token blocks，286,639 scoring tokens。基线与候选使用相同模型、
tokenizer、数据顺序、随机种子和 batch 口径。

| 配置 | PPL | 相对 BF16 | 门槛 | 状态 |
|---|---:|---:|---:|---|
| Matched BF16 | 17.208506 | 0 | — | 基线 |
| 旧 MLP-only S24 | 27.801928 | +61.559% | +10% | FAIL |
| 新 MLP-only Down-S32 | 18.452719 | +7.230% | +10% | PASS |
| 旧 Full V5 S24 | 27.639944 | +60.618% | +15% | FAIL |
| 新 Full V5 Down-S32 | 18.555656 | +7.828% | +15% | PASS |

六任务 ACC 结果如下。WinoGrande 候选在两张 A6000 上独立运行，外围 BF16
Attention/LM 路径有 3 个样本的跨 GPU 浮点差异；签核采用较低值。

| 配置 | Macro ACC | 相对 BF16 | 门槛 | 状态 |
|---|---:|---:|---:|---|
| Matched BF16 | 75.3853% | 0 | — | 基线 |
| MLP-only 最终候选 | 74.6469% | -0.7384 pp | ≥ -1.0 pp | PASS |
| Full V5 Down-S32 | 74.6364% | -0.7489 pp | ≥ -1.5 pp | PASS |

| 任务 | BF16 | MLP-only 最终候选 | Full V5 Down-S32 |
|---|---:|---:|---:|
| PIQA | 81.4472% | 80.5767% | 80.3591% |
| ARC-Easy | 79.7138% | 78.4933% | 78.1566% |
| ARC-Challenge | 55.3754% | 54.5222% | 54.1809% |
| BoolQ | 83.2722% | 81.4679% | 82.2324% |
| HellaSwag | 79.4961% | 78.7094% | 78.6198% |
| WinoGrande | 73.0071% | 74.1121%（复核 74.3489%） | 74.2699% |

MLP-only Down-S32 PPL 全流覆盖 `37,866,176,512` 个激活元素；Full V5
Down-S32 覆盖 `75,732,353,024` 个激活元素。最终候选组成分片的下列计数均为 0：

- FP→fixed saturation；
- Hadamard saturation；
- activation ScaleCode format error；
- total-shift format error；
- Gate/Up S37 group guard overflow；
- Down S45 group guard overflow；
- S44/S54 accumulator overflow；
- Down S32 terminal output saturation；
- SwiGLU overflow。

Full V5 的 QK `±16` clamp 计数不为 0，但这是 Attention 已知合同，Attention-only
ACC/PPL 已独立通过，不能归因于 MLP Down。旧 S37/S46 zero-guard 压力分片只用于
定位，不进入最终候选汇总；其中一个全局 Hadamard 计数器发生内存污染并已归档。
最终 S45/S54 严格分片没有该问题，所有审计字段为 0。

### 2.1 软件数值孪生修正说明

本轮同时修复了三个只属于软件执行器的问题，不能误写成新的硬件位宽需求：

1. packed S24 Gate/Up 在 SwiGLU 消费边界显式按 24-bit 二补码符号扩展；RTL
   必须具有同样语义。
2. SwiGLU product 使用真实 `int32` 存储，并分块完成 int64 临时计算、范围检查和
   LUT/multiply，避免数千万元素的临时缓冲污染。
3. WinoGrande 候选使用 batch 8；batch 32 曾出现不可能的临时超 S32 值。两张
   GPU 的 batch-8 严格运行均为零异常，ACC 分别为 74.1121% 和 74.3489%。
   报告按较低值签核，不把跨 GPU 浮点差异包装成确定性提升。

## 3. 冻结后的数值合同

| 节点 | 修复后格式 | 是否改变 |
|---|---|---|
| Host RMSNorm→FPGA MLP 输入 | S24/F16 | 否 |
| Gate/Up Hadamard 输出 | S27/F16 | 否 |
| Gate/Up 在线激活 | Group32 U8 + U24 metadata | 否 |
| Gate/Up 权重 | Group32 W4 + U16 metadata | 否 |
| Gate/Up group guard / accumulator / output | S37/F24、S44/F24、S24/F16 | 否 |
| Gate/Up packed lane→SwiGLU | S24 按 bit `[23]` 符号扩展 | 明确合同 |
| SiLU×Up product | S32/F16，32-bit 存储 | 否 |
| Down Hadamard 输出 | S35/F16 | 否 |
| Down 在线激活与权重 | Group32 U8/W4 + ScaleCode | 否 |
| **Down total shift** | **`[12,44]`** | **由 `[20,44]` 扩展** |
| **Down group guard / accumulator** | **S45/F24、S54/F24** | **是** |
| **Down terminal output** | **S32/F16** | **是** |
| Host residual add | FP32 | 否；解包输入改为 S32/F16 |

S32/F16 的实数范围为 `[-32768, 32767.9999847412]`，步长仍为 `2^-16`。
当前 trace 最低需要 S27/F16 才能覆盖 587.87；选择 S32 而非 S27/S28 是为了
保留 16 位小数、按 32-bit Host/AXI 字对齐，并为尚未观测到的长尾留出余量。
S45 guard 来自 W4 最坏界在 `total_shift=12` 时的精确上界；448 个 Group32
累加再增加 9 个整数位，因此 S54 是不依赖样本分布的安全 accumulator 宽度。

## 4. RTL 修改清单

### 4.1 Down accumulator finalizer

文件：将 `rtl/mlp/hap_mlp_down_group_major_accum_s46.sv` 升级为对应 S54 实现
（建议新文件名 `hap_mlp_down_group_major_accum_s54.sv`，避免旧 ABI 混用）。

1. Down 的合法 total shift 改为 `[12,44]`；Gate/Up 仍为原范围和位宽。
2. Down 单组 guard 改为 signed S45/F24，448 组 accumulator 改为
   signed S54/F24；加法溢出检查至少使用 S55。
3. round-half-away-from-zero 仍只在完整 448 组累加结束后执行一次。
4. `out_projection_s24[LANES*24-1:0]` 改为
   `out_projection_s32[LANES*32-1:0]`。
5. `finalized_projection_s24` 和输出寄存器改为 `LANES*32`。
6. 将 `saturate_s24`/`did_saturate_s24` 替换为 signed-32 版本，阈值必须是
   `[-2147483648, 2147483647]` 的 raw Q16 值；不能直接截取低 32 bit。
7. 禁止对 total shift 12…19 继续使用 zero-guard；这些贡献必须进入 S45/S54。
8. 原饱和计数改成专用 `down_output_saturation_count`，表示 S32 末级饱和，
   与 Gate/Up 的 S24 saturation 分开。
9. Gate/Up S24 tile 在送入 SiLU/SwiGLU 前，对每个 24-bit lane 使用
   `{{8{lane[23]}}, lane}` 符号扩展；禁止 `{8'b0, lane}` 零扩展。

### 4.2 Shared slice、elastic queue 与 inverse repack

文件：

- `rtl/mlp/hap_mlp_shared_dual_slice16x12_s44_s46.sv`（升级为 S44/S54 版本）
- `rtl/mlp/hap_mlp_down_v5_scheduler16_s46.sv`（升级为 S54 版本）

要求：

1. Gate/Up 路径继续使用 `16×12×24`，不得因 Down 修复一起扩宽。
2. Down slice 从 `16×12×24` 改为 `16×12×32`；两个 8-row 子 slice、
   head/tail elastic buffer 和所有局部 payload 宽度同步修改。
3. 新增 Down-only `repack12_to16_s32`，输入为 `16×12×32`，输出为
   `16×16×32`。不要修改 Gate/Up 仍在使用的 S24 repacker。
4. ready/valid、tile tag、首尾 tile 和 backpressure 行为必须保持不变。

### 4.3 Command 与 production top

文件：

- `rtl/mlp/hap_mlp_serial_ddr_command16_v5_s46.sv`（升级为 S54 版本）
- `rtl/mlp/hap_mlp_full_command16_v5_s46.sv`（升级为 S54 版本）
- `rtl/integration/hap_attention_mlp_resource_top.sv`
- `rtl/integration/hap_attention_mlp_production_core.sv`

所有 Down 输出端口统一命名为 `projection_s32x16x16` 或
`mlp_projection_s32x16x16`，宽度统一为 `16*16*32 = 8192 bit`。production
core 的当前 `[6143:0]` S24 net 必须改为 `[8191:0]` S32 net。禁止在任意 adapter
中重新压回 24 bit，也禁止仅扩端口而内部仍接 S24 payload。

### 4.4 Tensor DMA

文件：`rtl/integration/hap_mlp_tensor_dma_bridge.sv`

H2C 输入合同保持原样：

- `mlp_input_s24x16x32 = 12288 bit`；
- 每个输入 Group32 为 48 个 AXI256 beats；
- 总 H2C payload 为 192 KiB。

C2H 输出修改为：

- `mlp_out_s32x16x16 = 8192 bit`；
- 每 tile 32 个 AXI256 beats；
- 256 tiles 共 8,192 beats；
- 总 C2H payload 为 `262144 bytes = 256 KiB`。

必须同步修改：

1. `OUTPUT_TILES*24` → `OUTPUT_TILES*32`；
2. `output_tile_beat_r[0:23]` → `[0:31]`；
3. hold mask 从 24 bit → 32 bit；
4. issue counter 扩成至少 6 bit，使状态可以表示 32；
5. 4-beat mux group 从 6 组 → 8 组，并覆盖 group 0…7；
6. `output_issue_count < 24` → `< 32`；
7. 最后一个 beat 判定从 23 → 31；
8. clear/reset/arm_store/output_fire/final-beat 的所有常量同步改为 32；
9. DMA 完成时严格检查 `output_beat_count == 8192` 和
   `output_tile_count == 256`。

元素顺序必须保持当前 row-major tile flattening；每个 S32 元素按 little-endian
二补码发送，不能把四字节元素拆成旧式 packed-S24 三字节布局。

### 4.5 AXI-Lite、格式号和可观测性

文件：`rtl/integration/hap_mlp_axil_control.sv`

1. `FULL_FORMAT_ID` 从 `0x48384603` 升级为 `0x48384605`；
   `0x48384604` 仅表示未扩 Down shift/guard 的中间候选，禁止用于最终 bitstream。
2. 导出独立 `down_output_saturation_count`。建议在确认寄存器表无冲突后使用
   `0x2AC`，或由硬件部门分配下一个 ABI-reserved word；RTL 与 Host 地址必须
   同一次提交同步冻结。
3. Host 启动命令必须要求 v5 ID；v3/v4 Host 不得驱动 v5 bitstream，v5 Host
   也不得接受 v3/v4 bitstream。
4. `down_output_saturation_count != 0` 必须令运行结果 fail-closed，不能只记录
   warning。

## 5. Host 修改清单

文件：

- `host/scalellm_memory.py`
- `host/scalellm_hostops.py`
- `host/scalellm_hardware.py`

修改要求：

1. 拆分输入与输出字节数：
   - `MLP_INPUT_PAYLOAD_BYTES = 16*4096*3 = 196608`；
   - `MLP_OUTPUT_PAYLOAD_BYTES = 16*4096*4 = 262144`。
2. H2C 保留 `pack_s24_q16` 和 192 KiB write；不得把入口误改为 S32。
3. 新增 `unpack_s32_q16`：按 little-endian `int32` 读取，转换为 FP32 后除以
   `65536.0`。必须对 buffer 长度、元素个数和只读/可写属性做严格检查。
4. C2H read、short-read 检查和本地 buffer 改用 256 KiB。
5. residual add 必须使用解包后的 FP32 tensor；不得先 cast BF16 再加 residual。
6. `MLP_FORMAT_ID` 升级为 `0x48384605`，并读取/检查独立 Down S32 saturation
   counter。
7. artifact `scalecode_manifest.json` 同步生成 v5 ID；v2/v3/v4 artifact 不得复用。

## 6. 必须新增或更新的验证

硬件部门提交后，以下项目必须全部通过：

1. packed S24→S32 符号扩展：`0x000000`、`0x7fffff`、`0x800000`、
   `0xff10ff`、`0xffffff`；负数必须按 bit `[23]` 扩展。
2. Down total shift 12…19 定向向量：不得 zero-guard；逐组 S45 与软件 golden
   bit-exact，S45 overflow counter 为 0。
3. S54→S32 finalizer 定向向量：0、±0.5 LSB、round ties、±128、±512、
   ±1024、S32 最大/最小值、正负 S32 overflow。
4. Down `12→16` repack：所有 row/lane/tile tag 逐位比对，包含 backpressure。
5. DMA：单 tile 32 beats、256 tiles 8,192 beats、随机 stall、最后 beat、
   little-endian 负数回环。
6. Host pack/unpack：`[-587.8696, -128, 0, 127.99998, 587.8696]` 和 S32
   边界 round-trip。
7. RTL/XSim 与软件 golden：所有新增 S45/S54/S32 向量 0 mismatch。
8. production source closure：新增 S32 repacker/adapter 必须进入 active V5
   manifest。
9. 静态迁移审计 `audit_mlp_down_s32_migration.py` 必须扩展检查 S45/S54、
   `[12,44]` 和符号扩展，并达到 `15/15 PASS`。
10. 全量精度：WikiText-2 PPL、六任务 ACC 和所有格式/overflow/saturation
   fail-closed 条件必须同时通过。

## 7. 禁止的“局部修复”

以下修改不能解决问题：

- 只把 S46 accumulator 扩成 S54、但 total-shift 下界和 group guard 仍停在
  20/S37；必须同时采用 `[12,44]` 与 S45。
- 只修改 finalizer，而 scheduler/DMA/Host 仍按 24 bit 解释。
- 将 S24/F16 改成 S24/F13 而不重新验证整个 ABI；这会改变小数精度和所有
  scale/residual 接口。
- 删除 Down Hadamard；Hadamard 是 A8 分组量化前的离群值抑制，不是末级
  饱和原因。
- 扩宽 Gate/Up 或 Host ingress；当前证据不要求这些路径增加带宽。
- 在每个 Group32 后提前 round/saturate；必须保持 S54 中跨 448 groups 累加。

## 8. 最终放行条件

软件精度结论已经 APPROVED；只有同时满足以下条件，硬件迁移状态才能从 HOLD
改为 APPROVED：

- MLP-only 与 Full V5 全量 PPL 已通过（当前已满足）；
- MLP-only 六任务 Macro ACC 下降不超过 1.0 pp；
- Full V5 六任务 Macro ACC 下降不超过 1.5 pp；
- 软件全流所有 MLP format/guard/accumulator/S32-output 错误计数为 0；
- 修改后的真实 RTL/Host migration audit 为 15/15；
- RTL regression 与 DMA/Host ABI regression 全部通过。

截至 2026-09-18 的真实工程审计仍为 `4/15 PASS`，且现有审计脚本只覆盖
`0x48384604` 中间目标。硬件提交前还必须把审计目标升级为 `0x48384605`，加入
S45/S54、`[12,44]` 和 S24 符号扩展检查；因此当前绝不能声称 RTL 已完成迁移。

## 9. 可直接转发硬件部门的最终通知

Llama-3.1-8B-Instruct 软件全量验证已经完成：最终 MLP 修复不能只把 Down 输出
从 S24/F16 改成 S32/F16，还必须把 Down 的合法 total shift 从 `[20,44]` 扩为
`[12,44]`，单 Group32 guard 从 S37/F24 扩为 S45/F24，448 组累加器从
S46/F24 扩为 S54/F24；Gate/Up 仍保持 S24/F16、S37/S44，MLP 输入和
Hadamard/Group32/A8W4/ScaleCode 均不改。Gate/Up 每个 packed 24-bit lane
进入 SiLU/SwiGLU 的 32-bit 运算器前必须用 bit `[23]` 做符号扩展，禁止零扩展。
Down 最终输出及 shared/scheduler/repack/top/DMA/Host 全链路统一为 S32/F16：
8192 bit/tile、32 个 AXI256 beats/tile、C2H 256 KiB；H2C 输入仍为 S24/F16、
192 KiB。最终 ABI 号统一升级到 `0x48384605`，并独立导出 Down-S32 saturation、
S45 guard overflow、S54 accumulator overflow 和 total-shift format counter，
任一非零必须 fail-closed。软件候选的 PPL 为 18.4527（相对 BF16 +7.230%），
保守六任务 Macro ACC 为 74.6469%（相对 BF16 -0.7384 pp），所有候选格式、
guard、accumulator 和输出饱和计数均为 0；但真实 RTL/Host 当前审计仍只有
4/15，完成 `0x48384605` 全链路修改和回归前不得签核。
