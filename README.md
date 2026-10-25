# ScaleLLM · VCU118 Llama 推理加速器

基于 Xilinx VCU118 的 Llama-3.1-8B-Instruct 量化推理工程。FPGA 执行 Attention 与 MLP Gate/Up，Host 执行 Down、非线性、归一化、残差、词表投影和调度。已在 Dell Windows 主机经 PCIe XDMA 完成真实模型的全部 32 层与连续两步生成。

本工程发布**设计源码、已测 bitstream、Host 推理程序和部署说明**。模型权重由使用者自行获取并导出。

| 入口 | 内容 |
| --- | --- |
| [性能、功耗与资源详细报告](docs/PERFORMANCE_AND_RESOURCES.md) | 实测与估算 token/s、功耗范围、全器件及各模块资源、计算公式和证据 |
| [部署指南](docs/DEPLOYMENT.md) | 硬件连接、驱动、Python 环境、模型准备、下载和推理 |
| [固定 bitstream 的软件优化](docs/SOFTWARE_ONLY_INFERENCE.md) | DDR 驻留范围、异步调度、精确 Down 加速、验证模式和本轮验收 |
| [硬件构建指南](docs/BUILD_HARDWARE.md) | RTL、约束、构建工具版本与源码/bitstream 对应关系 |
| [工程整理记录](docs/WORKSPACE_LAYOUT.md) | 发布目录、研究记录、保留工件与缓存清理 |
| [部署入口](deploy/scalellm.py) | 参数化路径、预检与推理运行 |
| [发布包生成器](tools/package_release.py) | 白名单打包与逐文件 SHA-256 校验 |

## 已验证范围

- FPGA：`xcvu9p-flga2104-2L-e`，计算核心 100 MHz，双 DDR UI 200 MHz。
- 模型：真实 Llama-3.1-8B-Instruct 导出的本工程固定点格式；不声称与 BF16 逐值等价。
- 完整功能运行：两条请求，每条生成 2 个新 token；`Hi` → `It's`，`Hello` → `Hello!`。
- 每次生成遍历全部 32 层；128 条 Attention 和 128 条 GU 命令均完成全输出独立参考比较。
- 当前公开入口：两条短请求、每条生成 1–2 个 token；聊天模板、prompt 与生成预算合计不超过 16 token，采用前缀重算。
- Attention RTL 的单层 KV 窗口为 128 个位置；128-token 完整推理调度与持久 KV-cache decode 尚未实现/验收。已观测到 Attention/GU 任务并发在途，扣除计算重叠后的总吞吐尚未直接实测。

## 当前 bitstream：2 条请求，每条 16 行前缀

**当前固定 bitstream 配套、已上板验证的模式是 2 条独立请求交错处理。** GU 按两个 cohort 成对调度：cohort 0 对应请求 A，cohort 1 对应请求 B；每个 cohort 的 16 行属于同一请求的 16 个 token 位置，可能含 padding。

```text
cohort 0：请求 A 的 16 个 token 位置 ── Attention ── GU
cohort 1：请求 B 的 16 个 token 位置 ── Attention ── GU
             两条请求的任务交错使用 Attention / GU 两个引擎
```

这里的 **2 × 16 行表示两条请求各自的前缀**，不是 32 条独立请求，也不是一个 32 行同时执行的计算阵列。当前软件每步重新计算前缀，经过全部 32 层后，从最后有效位置预测每条请求的 **1 个新 token**。两请求是当前配套程序和成对调度的验证规模，不代表请求队列最多只能接收两个请求。

**16 行也不是 16 个注意力头。** 本模型的 Q 形状为 `[16 个 token 位置, 32 个 query head, 每头 128 维]`，K/V 各有 8 个 head。现有 RTL 分别维护 token 行号与 head 编号，QK/softmax/PV 部分按 head 轮转；多头并行是另一种需要调整 RTL、存储和数据供给的映射。当前多行投影重点在于让不同 token 复用同一组权重读取。见[Attention 调度源码](deploy/vendor/hardware/rtl/attention/hap_attention_compute_cohort16_top.sv)。

## Prefill、decode 与 token/s 的口径

同一请求的新 token 依赖此前生成结果，因此正常自回归生成仍逐个推进；批量计算可以处理已经知道的 prompt，或不同请求各自的新增位置。

| 场景 | 一批 16 行装什么 | 一次完整 32 层计算的用途 | 当前状态 |
| --- | --- | --- | --- |
| Prefill | 同一 prompt 的已知 token | 处理输入，形成预测第一个新 token 所需的状态 | 当前数据通路适合这种组织；公开程序限短上下文 |
| 当前前缀重算 decode | 同一请求的已知前缀和 padding | 从最后有效位置预测 1 个新 token | 已上板验证 |
| 多请求增量 decode | 16 条独立请求各自的一个新增位置 | 每条请求各预测 1 个新 token，合计最多 16 个 | 目标方案，需要持久 KV、逐请求位置/掩码与隔离 |

- **Prefill 输入吞吐** = 有效输入 token 数 / prefill 时间。16 个有效输入在 0.5 秒处理完，等于 32 输入 token/s；padding 不计数，后续重复计算旧前缀不能重复算作新输入。
- **Decode 输出吞吐** = 实际新增输出 token 数 / 对应生成时间。当前 16 行前缀只能按实际产生的 1 个新 token 计数；只有 16 条独立请求各产生一个新输出时，分子才能计 16。
- **硬件计算吞吐**必须注明算子和计时边界。只累计 FPGA Attention + GU 的时间，不包含 Host Down、归一化、残差、词表投影等工作，不能直接与别人完整模型的 prefill/decode token/s 比较。只比较板上计算时，双方应采用相同算子范围、模型/精度、上下文、有效行数和并发配置。

### 当前 bit 的计算窗口实测与折算

以下来自完整推理的 128 次 Attention 和 128 次 GU，核心 100 MHz。计算窗口含内部 DDR 供数等待和背压，排除 Host、PCIe，以及窗口之外的板级装载；不是整个硬件 START→DONE 的精确时间。GU store/stall 与 compute 重叠，不能重复相加。

| 指标 | 数值 | 含义 |
| --- | ---: | --- |
| 单层 Attention compute 均值 | 8.409 ms | 板上计数实测 |
| 单层 GU compute 均值 | 7.351 ms | 板上计数实测 |
| 32 层 Attention + GU 窗口累计 | 约 0.5043 s/完整前向 | 两引擎工作量相加，不扣并行重叠 |
| 当前前缀重算的串行工作量折算 | 1.983 新 token/s | 不是并行性能上限 |
| 假设 16 行全部有效的处理量折算 | 约 31.7 行/s | `16 / 0.5043`，仅 Attention + GU 部分的 prefill 计算等价吞吐；不是完整模型 prefill 或生成吞吐 |
| 两请求逐层交错，供给与换层零耗时 | 2.586 新 token/s | `A0 + max(A1, GU0) + GU1` 的条件调度估算 |
| 充分独立就绪任务的两引擎服务率上界 | 3.716 新 token/s | 保持当前前缀重算工作量的理想上界 |

后两行是基于实测计数的模型，不是直接测得的并行总时间，也不是 DSP 算力峰值。当前真实请求含 11/12 个有效位置及 padding；31.7 行/s 不是一次已测的“16 个有效输入 prefill”结果。详见[逐命令计数与公式](docs/evidence/software_only_inference/board_compute_metrics.json)。

## 目标：多请求 KV-cache 增量 decode

以下假设持久 KV-cache、每行独立请求隔离、全模型 Attention/GU 权重驻留、metadata/KV 预取隐藏、Host 及时完成 Down 等工作，沿用当前 100 MHz 算子的成本模型，包含全部 32 层。**这是目标架构的条件估算，不能作为当前 bitstream 的实测生成性能。**

| 并发请求数与调度 | 上下文 16 | 上下文 128 |
| --- | ---: | ---: |
| 16 条请求，单批 16 行 | 29.7 新 token/s | 15.7 新 token/s |
| 16 条请求，两批各 8 行，Attention/GU 流水 | 33.8 新 token/s | 17.1 新 token/s |
| 32 条请求，两批各 16 行，Attention/GU 流水 | 53.2 新 token/s | 20.6 新 token/s |

单批 16 行在上下文 16 时完成一轮约需 0.539 秒，`16 / 0.539 ≈ 29.7 新 token/s`。两条流水配置采用持续生成、摊薄填充和排空后的稳态值；第一轮包含填排时，上下文 16 的对应吞吐约为 33.3/52.5 token/s。数字均为所有请求的**合计**，例如 16 路合计 33.8 token/s 对应每路平均约 2.11 token/s。上下文指当前 decode 时可见的 KV 长度，持续生成时会增长。

这里的 **32 条请求 = 两个批次 × 每批 16 条独立请求**，是目标模型采用的调度规模，不是已证明的最大硬件并发上限；更多请求可以排队轮转，但引擎满载后不会继续按请求数线性增加吞吐。单请求低延迟是另一个优化目标，多头/输出通道并行需要另外设计，不能把全部耗时直接除以 16。完整成本模型、带宽与预取敏感性见[性能报告](docs/PERFORMANCE_AND_RESOURCES.md)；本页数值汇总见[可复算数据](docs/evidence/software_only_inference/prefill_decode_conclusions.json)。

## 已交付的软件优化

`deploy/optimized/` 将 32 层 Attention 权重/metadata 与 GU metadata 在同一会话中一次驻留，CPU Down 可与 FPGA 任务交错执行。**当前硬件的 GU 权重地址固定，仍须逐层装载；KV preload 接口未接通，纯软件不能实现全层持久 KV 增量 decode。**

正式默认运行不依赖旧 gold，全部 32 层、两条请求、连续两步生成通过 1,032 个完整数值边界核对，128 次 Attention / GU / Down 输出一致。见[独立数值回执](docs/evidence/software_only_inference/full_numerical_audit.json)及[协议验收](docs/evidence/software_only_inference/full_protocol_review.json)。

供部署参考，本次包含 Host、PCIe、身份校验和证据落盘的正式运行为 213.643 秒生成 4 token，初始化另计 18.356 秒；离线数值审计不计入。该记录与上述板上计算口径分列。首次并发 metadata 的 watchdog 失败记录保留，最终版本只在双 GU copy/ACK 后与 Host Down 重叠预取。见[完整运行计时](docs/evidence/software_only_inference/full_metrics.json)和[软件优化说明](docs/SOFTWARE_ONLY_INFERENCE.md)。

## Bitstream

发布包中的 `bitstream/ScaleLLM_MLP_GU_only_ENGINEERING_VALIDATION.bit` 为实际板测文件：

```text
size:   80159259 bytes
sha256: 66a305348d3099ca48043324d2ef50e3a39bea84b818f6107f0ff9cdd08acc47
```

该工程验证版已合法布线并完成所述板上功能验证；原 Max-DPO 和外部 reset 物理签核仍未全部闭合。构建设计使用 Vivado 2025.2，已验证的 Dell 下载工具为 Vivado 2022.2。下载前按部署指南确认器件、接口、驱动和板卡空闲状态。

## 发布与许可

项目自有源码采用 [Apache-2.0](LICENSE)。第三方组件和 bitstream 中使用的 AMD/Xilinx IP 按各自条款处理，详见 [NOTICE](NOTICE)。Llama 模型权重、导出的权重工件、AMD 工具安装文件和机器专用驱动签名不随源码包分发。

`dist/` 中的归档由白名单生成，不包含本地 Git 历史、内部研究会话、模型权重或构建缓存。完整研究工作区保留历史实验及原始证据；使用者部署时以这里的指南和发布包为入口。
