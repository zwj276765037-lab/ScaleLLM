# M002 专属 DDR 路由合同

本次实现入口：`project/hardware`。本说明描述 2026-10-15 的修复版连接；功能仿真、完整 elaboration、时序、bitstream 和板级验收分别取证。

## 物理和逻辑接口

| 逻辑数据 | 物理目标 | RTL/BD 端口 | 时钟 |
| --- | --- | --- | --- |
| Attention weight c0/c1 两半组 | DDR0 | `ddr0_axi_*` / `M_AXI_WEIGHT_C0`，512-bit read-only | DDR0 UI 200 MHz |
| MLP gate/down c0/c1 两半组 | DDR1 | `ddr1_axi_*` / `M_AXI_WEIGHT_C1`，512-bit read-only | DDR1 UI 200 MHz |
| Attention 当前数据DMA（tensor、metadata、输出） | DDR0 | `data_axi_*` / `M_AXI_DATA`，256-bit read/write | core 100 MHz |
| MLP tensor、metadata、输出 | DDR1 | `mlp_data_axi_*` / `M_AXI_MLP_DATA`，256-bit read/write | core 100 MHz |

Host 地址图中的 KV 范围在本轮仅为 DDR0 保留区；本轮没有增加或验证 off-chip KV 的读写、跨层/跨请求生命周期，也不因数据口指向 DDR0 而声称完整 DDR KV 已实现。

board 的新增完整 AXI4 数据信号前缀是 `m_mlp_axi_*`。BD SmartConnect 负责 core→DDR UI 的跨时钟和 256→512 位转换。两个权重物理端口及其位宽不变。

保留 Attention c0/c1、MLP gate c0/c1、MLP down c0/c1 六个 CSR 字段。名字中的 c0/c1 或 ddr0/ddr1 在引擎内部仍表示逻辑半流；每一字段都是所属物理 DDR 内的 **local byte offset**。RTL 不添加 0x80000000，不删除或重排权重半组，也不修改 Hadamard、ScaleCode、format05 或 S32/F16 数值规则。

`resource_top` 令 Attention 的两个原生 reader 均使用 DDR0 clk/reset，MLP 两个 reader 均使用 DDR1 clk/reset；各 reader 原有的 core↔reader 命令和 payload CDC 保留。新路由只跨时钟传输窄描述符和单比特状态，不新增 DDR0↔DDR1 的宽 payload CDC。

## 权重序列和返回

`hap_axi512_dual_engine_dedicated_read` 使用四条 ingress FIFO，分别接受每个逻辑 reader 的描述符。核心时钟域验证一个引擎的两条描述符具有相同的序号、ARLEN、ARSIZE、ARBURST；匹配后同时消费两个 ingress，向该引擎专属 egress FIFO 先写 stream0，再写已保存的 stream1。stream1 的 pending 状态计入 quiescence，背压不能丢失第二半组。

两个引擎使用独立 egress 和物理序号，可并行推进；一条 DDR 的 FIFO 满不会阻塞另一引擎的调度。每路物理 issuer 复用 `hap_axi512_ordered_local_issue`：物理 AR 接受时保存 `{logical-stream, sequence, ARLEN}`，按 AXI 无 ID 的有序响应分流。其历史 attn/mlp owner 位在此仅标记本引擎的 logical stream0/stream1。相同 DDR 上的 burst 按 stream0/stream1 顺序串行，但允许有序 outstanding。

现有每 logical stream 的两项 elastic response buffer 保留。ARVALID 及 payload 在背压时保持；RVALID 和 payload 亦保持到该 logical reader 接受。错误 RRESP、过早/过晚 RLAST、描述符不匹配均触发 fatal freeze；不会把坏 beat 当成功数据，软件 clear 不能清除此错误，只能硬复位。

## 数据口与控制

`hap_axi256_dedicated_data_router` 将 c0 Attention 数据完整旁路至 DDR0；c1 tensor 与 c2 metadata 复用既有 `hap_axi256_3to1_arbiter` 的 command lock，经独立完整 AXI 口发往 DDR1。c0 在该 MLP 仲裁器内禁用，真实 c0 旁路不受 MLP owner 影响。

现有 owner mode 0/1/2/3、command pause、maintenance、completion ACK 和 watchdog 语义保留。数据 quiescence 同时要求 Attention data busy 清零、MLP tensor/meta 请求结束、MLP arbiter idle。全局 clear 首先暂停新命令，让已接受命令和两组 ingress/egress/tag/response 队列排空；确认 source 关闭、两个 DDR 的维护停止已返回核心域并连续稳定后，才发 delayed `engine_soft_clear` 并同步复位 FIFO。各 DDR enable、freeze、维护状态及空闲状态均保留其目标时钟域 synchronizer。

DDR reset 仍通过 source-qualified request 和核心 reset manager 复位两侧；运行时硬复位要求系统 AXI 对端一并取消已接受未完成事务，不能把任意孤立 reset 当成 AXI 活跃事务恢复机制。定向测试覆盖空闲时 core-only、DDR0-only 和 DDR1-only reset 后重启；维护测试覆盖活跃事务排空。

## CSR 兼容性与遥测

新增只读 CSR `0x2B8 MEMORY_LAYOUT_ID = 0x4D303032`（ASCII `M002`）。读取返回 OKAY；任何 full/partial/zero-strobe 写均 SLVERR 且不更改 ID。数值 `FULL_FORMAT_ID=0x48384605` 和 `ABI_VERSION=0x00050000` 保持。Host 必须在写 DDR/启动任务前校验布局 ID；旧混合 DDR 硬件无法被相同数值 format/ABI 自动识别。

保留既有遥测地址。`0x264/0x268` 计数 **logical burst pairs**，每个 pair 产生本物理 DDR 的两个 AR burst；`0x26C` 计两引擎同时 eligible 的 core cycles，不再表示竞争同一个 DDR。物理 DDR 的 HOL/HWM 仍留内部，现有 AXI-Lite 导出保持不支持/零值，不新增未经同步的跨时钟总线。快照仅在 leaf quiescent 时更新；clear 后当前计数按既有语义清零。

## 验证入口与边界

- `hap_axi512_dual_engine_dedicated_read_tb`：真实专属 adapter + 原 ordered issuer/FIFO；独立 full-width payload/地址/字节数 scoreboard，真实 assembler/join 的完整组/metadata/列顺序检查，背压、独立并行、维护及错误冻结测试。
- `hap_m002_dedicated_frontends_tb`：真实 Attention/MLP reader、命令CDC、有限深度halfgroup FIFO、assembler/join及MLP telemetry CDC；64组/引擎，长期阻塞输出令物理R背压，活跃命令维护排空与完整组/元数据检查。
- `hap_axi256_dedicated_data_router_tb`：production 实际复用的数据 router，Attention/MLP tensor/meta 三 client 完整 AXI 读写、Wstrb、响应归属及独立进度。
- `hap_mlp_memory_layout_csr_tb`：布局 ID、只读保护、AXI-Lite stall/AW-W独立握手和复位稳定性。

源/TB 被构建负责人串行编译仿真；原始运行、源身份及真实 PASS/FAIL 位于 E001/R002 的各 AT 目录。以上测试本身不证明完整数值算法、综合资源、setup/hold、可用 bitstream 或板卡性能。
