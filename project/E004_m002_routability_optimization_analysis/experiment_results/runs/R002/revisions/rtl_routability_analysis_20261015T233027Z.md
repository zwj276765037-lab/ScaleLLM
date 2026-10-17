# SM008 / E004 / R002：Attention 定向 RTL 可布线性事实与候选

负责人 A008 `/root/m002_rtl_routability_explorer`，2026-10-16 本地日期。角色为工程实验中的只读代码探索。本报告供主控与 A007 方案评判；没有修改生产 RTL/XDC/构建脚本，没有运行 EDA、仿真、GPU、板卡或后代 agent。实际运行模型/强度未独立核实，启动请求为 gpt-6.1-sol/xhigh。

**源码支持最明确的关注点是：6144 位记录在 input/context/frontend 之间组装、两级选择、再次快照；postprocess 同时保存两份 16 行 × 768 位记录，并做全行 pair 选择和四行量化选择；projection 已主动做大量物理复制，不能以源码存在复制便全部删掉。** 这些结构与 E003 打印的冲突样本相符，但目前不是全量失败信号的归因，也没有任何候选的布通收益测量。

## 1. 证据与身份

- 冻结基线：`project/E003_m002_full_implementation/experiment_results/engineering_final_report_2026-10-16.md`。
- 原始失败：`project/hardware/vivado/reports/m002_E003_R003_AT001_full_route/vivado.log`，Phase9 248289 signals 因拥塞失败，最后 Route35-2 报 245279 overlapping nodes。两者单位不同。该日志打印10个节点，每个3个信号，共30次信号提及；这不是随机/全量样本。
- 实际构建：同目录 `effective_build_identity.txt`；Vivado2025.2，`xcvu9p-flga2104-2L-e`，生产宏选择 `hap_attention_board_cohort16_core`，相关17个源码均为 `SystemVerilog:1:1` 的实际 active 源。
- 哈希权威：`project/hardware/vivado/reports/m002_E002_R001_AT002_fresh_synth/inputs.sha256`，SHA256 `1dc14fef9dbe62ba0a55a7eebef3a5c0a277574c674e2d3310d5d69e10f711d3`。A006 指出成功 physopt 的 `diagnostic_evidence.json.synthesis.manifest` 精确绑定此 manifest；本批随后直接抽取该字段并验证path/87188B/hash三项一致。仅核对17个目标文件，全部当前 SHA256 与其一致；没有重扫 DCP/旧工程。
- 可复算交付：[小证据](rtl_evidence.json)、[只读复算脚本](recompute_rtl_evidence.py)。包含每个目标源 hash、实际构建 active 检查、10个节点的完整信号与原始日志行号、规模算式和有限地址覆盖断言。执行 `python3 project/E004_m002_routability_optimization_analysis/experiment_results/runs/R002/recompute_rtl_evidence.py`，exit0。

以下所有 register bit 是**源码声明的 payload 位**，不是综合 FF 数，也不是优化后可回收 FF 保证值。RAM 位不计作 FF；DSP 内寄存器、BRAM 输出寄存器、综合共享/常量消除、复制/重定时会改变映射。`W×(N−1)` 的 mux2-equivalent 是 W 位 N 选1的普通二叉 mux 规模口径，**不是 LUT 数/门数测量**，Vivado可能合并两级选择、用 LUT/MUXF、重新编码或共享译码。

本报告未读取新的网表测量；实际综合/physopt FF、LUT、扇出、SLR 位置与 packing 由 A006 的 R001 独立证据给出，不能把下面数字替代它。

## 2. 生产数据流与真正的并行度

所有以下数据路径都在 core100MHz 内，内部窄化不需要新增跨时钟路径；DDR0/UI200、DDR1/UI200职责和 Host ABI 不可改。

```text
DDR0 AXI256 row-major input
  → 两个 3072×256b BRAM wave image
  → 各一个6144b group组装寄存器（24拍×256b，BRAM读两级）
  → wave 6144b 2:1
  → input/context 6144b 2:1 ← context 16拍×384b组装
  → frontend 6144b快照
  → serializer 8:1×768b，逐row送单个Hadamard32
  → 8个quantizer结果共2048b+192b metadata → 两wave activation cache
  → 单个8row×16col projection阵列，wave0/wave1复用128个lane
  → 每wave 3072b tile，Q/K/V进postprocess；Wo进双wave output buffer
  → output每pair两个3072b tile，24拍×256b写回row-major BRAM
  → DDR0 AXI256 output
```

具体源位置：`rtl/attention/` 下 `hap_attention_board_cohort16_core.sv:305,380,393` 接入输入/输出/compute；`hap_attention_compute_cohort16_top.sv:177,187,207` 选择 input/context 并接 projection；`hap_attention_frontend_8row.sv:116,119` 每拍至多送一行768b给 Hadamard；`hap_projection_core16x16_w8_reuse.sv:340` 设置 `DUAL_CONTEXT(1)`；`hap_a8w8_array_16x16_s42_col3.sv:9,141,240` 默认 ACTIVE_ROWS=8，仅128个实际 lane。

**必须保留的同拍并行**：当前 frontend `in_fire` 一拍快照全6144b；当前 projection group issue 同拍提供8行A8及16列W8给128 lane；postprocess→`hap_kv12_quantizer4` 一拍快照4×768b=3072b；output `in_fire` 一拍捕获8×16×24=3072b。改变这些握手的含义需要协议改造。Hadamard 单row消费、RoPE 单pair48b消费、output单beat256b写入本身无需把整个历史记录做同拍计算。

array 声明的 `16×16×24=6144b out_s24` 中，高8行3072b在 `hap_a8w8_array_16x16_s42_col3.sv:252` 明确接常量0，projection在`:263`只取低3072b。**不能把这3072b零线列为可节省寄存器。**

## 3. 可复算结构规模、端口与选择

路径以下均相对 `project/hardware/rtl/attention/`，行号来自本次已哈希绑定的当前源。

| 结构与源码 | 当前读写/时序协议 | 声明规模和选择范围 |
|---|---|---|
| input 单wave，`hap_tensor24_buffers.sv:21,28,36,37,50,95` | DMA每拍最多写256b；load时同步BRAM读256b→额外256b stage→第0..23槽；有效后等ready，整组握手后才下一组 | 每wave3072×256=786432b RAM（96KiB），512b读pipeline，6144b组装；双wave RAM192KiB、组装12288b、读pipeline1024b。动态写为24个256b槽；应理解为24路选择性更新/译码，不能直接说有24选1宽读mux |
| input wave选择，`hap_tensor24_cohort16_buffers.sv:40,45,58,69,96` | 两loader同load_start；wave0的0..127组全部握手后才wave1，wave1首组长时间保持 | 6144b 2:1（generic6144 mux2）；双方payload实存，不是假重复 |
| input/context选择，`hap_attention_compute_cohort16_top.sv:177,187` | 只有ST_INPUT_FILL或ST_CONTEXT_SEND发送，descriptor/wave/group随数据 | 第二个6144b 2:1（generic6144 mux2）。与前级选择可被综合合并，不能简单按真实LUT相加 |
| frontend，`hap_attention_frontend_8row.sv:47,60,83,100,119,175,224,240` | in_fire全组快照；serializer逐row握手；第8行被Hadamard接收才释放input_buffer_valid；quant结果按row收齐再进cache | 快照6144b；row读8:1×768b（generic5376 mux2）；另2048b A8+192b meta bundle。24个DONT_TOUCH LUT1各驱动256b快照CE |
| context，`hap_attention_cohort16_local_stores.sv:251,255,264,265,283,305` | 384b行tile先打拍再写4个96b BRAM；read每拍4×96=384b，16slot后drain1拍再整组送frontend；写/读代码为独立端口 | 4×4096×96=1572864b=192KiB RAM；write_data384b+read_region384b+组装6144b=6912b payload寄存器；动态写16个384b槽；12b地址。`:249`的“96KiB”注释滞后，实际声明是192KiB |
| postprocess row bank，`hap_attention_cohort16_local_stores.sv:107,110,114,122,126` | projection每wave每row384b半组写；Q/K供RoPE逐48b读；K的RoPE按48b写post；V odd half合成全768b post；quant分4row消费 | 每row两个768b，16row共24576b；每row 16:1×48b读，16row generic11520 mux2；post的48b更新16槽，另768b全写/V复制 |
| postprocess选择，`hap_attention_cohort16_local_stores.sv:150,161,172,189,210` | 同一个rope_read_pair_r广播16row，每row先取pair，随后rope_input_row取一row；quant_row只走0/4/8/12 | row选择16:1×48=generic720；quant四组选择4:1×3072=generic9216。源码`reg quant_s24_r`/`rope_input_pair_s24_r`由always@*完整赋值，**是组合选择，不是额外寄存器** |
| output 单wave，`hap_tensor24_buffers.sv:153,163,177,184,196,221,232` | even/odd tile各捕获3072b；odd后连续24次256b写；该wave在write_active期间背压；BRAM一次一个read response | 每wave96KiB RAM，6144b tile payload+256b response；双wave payload12800b。write_data可视24:1×256b，generic双wave11776；wrapper response2:1×256b，再generic256 |
| projection weight FIFO，`hap_projection_core16x16_w8_reuse.sv:88,94,101,171,174,233,538,549` | 两项FIFO；一权重group服务wave0和wave1，仅wave1 capture后pop，支持push/pop同拍；group必须连续0..127 | 2×(7+4096+256)=8718b明确DONT_TOUCH/registers存储，异步head2:1×4359b；写使能按16列256b切分。短深宽FIFO不能简单BRAM替换，BRAM端口/latency和低深利用率都需评估 |
| projection group stage，`hap_projection_core16x16_w8_reuse.sv:113,117,122,364,386` | frontend read response+同一weight head一次capture_group，再issue_group给array；读pending/valid控制必须保持 | payload13000b：wave1+group7+actmeta192+act复制8192+zero复制256+weight4096+weightmeta256。原始A8只有2048b，复制额外6144b；zero原64b复制至256b，额外192b；这些DONT_TOUCH复制用于局部扇出 |
| six shard stages，`hap_a8w8_col_shard_s42.sv:59,100,151,221`；center拆分见`hap_a8w8_col_shard_center12_s42.sv:145,170,195,222` | 左2、中2/4/4/2、右2列，共六个local owner；下一拍launch进lane；stage capture/launch所有shard锁步 | activation共6×2048=12288b，各shard metadata/weight加后payload18304b。跨两级stage并非同一有效拍，不能把stage全部合并。GLOBAL_COL_BASE/4决定activation region，复制合并必须保留这层映射 |
| lane和accumulator，`hap_a8w8_group32_lane_s42.sv:29,39,45,79,105,123`；`hap_linear_tile_accum_dual_s42.sv:41,87,108,154` | lane II=2：高半128b activation/weight留一拍，16路乘法后归约；每lane42b×16深distributed FIFO异步head；双wave独立S42累加，最后固定4拍finalize窗口 | 128lane的高半act/wgt合32768b，product声明32768b、sum2声明17408b；这些可能进DSP/FF。laneFIFO共128×16×42=86016b LUTRAM意图，非FF。双waveaccum状态10752b、输出6144b；center region2还有显式split/input FIFO，不能忽略其pipeline |

input与context组装的有限地址复算：input24槽恰好覆盖6144位一次；context `(slot>>1)*768+(slot&1)*384=slot*384`，16槽恰好覆盖6144位一次；`{wave,slot[3:1],group,slot[0]}` 在2×16×128组合下恰好覆盖4096个384b BRAM word。它证明地址算式的覆盖，**不证明RTL在clear/stall下正确执行所有槽**。

## 4. 控制、复位与KEEP/DONT_TOUCH的具体边界

1. **input capture_index_r 是已出现冲突的控制来源。** `hap_tensor24_buffers.sv:26,95` 的5b index控制24个256b目的槽；低3b在原route样本反复出现。逻辑上这可化为24个等值译码和固定256b片段，每个槽CE对应256个payload位；实际capture_index一个bit的load数由综合译码/复制决定，不能拿6144直接报fanout。当前无显式slot-local capture层次/控制边界。动态写重写为静态bank可改善物理所有权，若网表已是同样译码则只换语法没有收益。
2. **6144b输入payload有异步reset，clear没有清payload。** `hap_tensor24_buffers.sv:59,68`：`activation_r<=0`只在`!rst_n`，每wave6144b；clear只清active/valid/index/pending/error。frontend/context/postprocess/output、projection大数据payload均已经是无reset，不能声称可再删那些大reset。input的12288b异步reset资格是候选，需要完整填24槽后valid的验证；无效期数据允许未定义，必须确认没有调试/安全接口依赖复位零值。
3. **既有LUT1控制副本不是无缘由装饰。** output的32个LUT1/wave位于`hap_tensor24_buffers.sv:191`，每个CE限制在128或256bit；frontend24个在`:83`注释有历史6144-load BUFG问题；projection group stage的53个在`hap_projection_core16x16_w8_reuse.sv:364`，weight FIFO有1+36个受保护control（`:178,191,214`）；shard有local activation/meta/weight捕获及每lane clear（`hap_a8w8_col_shard_s42.sv:98,110,122,145`）。移除全部DONT_TOUCH可能重新合并成大扇出网并恢复BUFG问题。历史注释的3042/5841/7170等load数不是E003当前实测。
4. **DONT_TOUCH的代价也真实存在。** projection weight FIFO、group复制数据、shard数据stage不允许普通合并/重定时；KEEP_HIERARCHY维护query/post/context owner，query四份read/write11b地址也显式keep/dont_touch。优化候选应以具体物理owner为单位审查：某个冗余副本是否在同一区域、能否只解除该数据对象而保留有用的local CE/边界。不能先删保护后假设工具会自动恢复良好局部性。
5. **expected_output_wave/finalize_wave 属于宽mux/分组写控制。** dual accumulator `:87`每bank384或768b输出2:1；`:166,207`选择wave和finalize半组，再按静态lane更新，不是旧96-lane动态全选。样本中`expected_output_wave_r_reg_rep__0`证明实际发生了控制复制；并不证明复制错误或可删。

## 5. 原始10节点 → 当前源码映射

下表保留全部30次信号提及。公共前缀为 `scalellm_vcu118_f05_bd_i/core/inst/u_core/u_compute/u_attention/`；`P` 表示 `u_compute/g_projection_rtl.u_projection/`。完整不缩写信号及精确原日志行号见 `rtl_evidence.json.route_samples`。层次和命名family可以映射；`i___5_i_2_n_0`、`p_5_in`、`data11`等综合临时节点无法仅靠RTL确定精确驱动逻辑，应由A006检查点对象/ORIG_REF定位，不能编造原变量。

| 节点、日志首行 | 三个contending net（缩写） | 源码落点和能确定的含义 |
|---|---|---|
| 1 INT_X91Y829/BYPASS_E11，540 | input/wave1/capture_index bit1；P/left2/shard/row5col0/lane/fifo_mem生成节点；P/center/region0/row7col1/lane/high_wgt_s8_r[125] | input index见`hap_tensor24_buffers.sv:26,95`；laneFIFO见`hap_a8w8_group32_lane_s42.sv:79,105,209`；128b high weight见`:30,126`。后者对应32元素group高半的第31个weight的bit5（源总元素编号，从0算）；该lane为global col3,row7 |
| 2 INT_X57Y792/BYPASS_W5，556 | output/wave0/i___5_i_2_n_0；P/center/region0/accum/expected_output_wave_r复制；output/wave0/odd_lo_r生成网 | 输出未知临时网只定位`hap_tensor24_buffers.sv:153,177,221`的serializer/BRAM owner；odd_lo family见`:165,180,239`。wave选择见`hap_linear_tile_accum_dual_s42.sv:49,87`。InstTerms另显示region0 out_s24[36,37]，对应row0/globalcol3的S24 bit12/13 |
| 3 INT_X85Y763/BYPASS_W5，571 | input/wave1/capture_index bit1；input/wave0/activation_r_reg生成alias[3245]；context_store/activation_s24[3291] | input动态片段/最终wave选择见`hap_tensor24_buffers.sv:37,95`及cohort buffer`:45`；context buffer见local_stores`:264,306`，3291为row4/group元素9/bit3。前端选择/捕获逻辑可能被综合推入源层次并形成跨owner别名；实际优化来历及源寄存器准确编号不能仅凭alias认定 |
| 4 INT_X34Y858/NN1_E_BEG2，586 | postprocess/rope_read_pair_r[3]；P/center/region1/accum/out_s24[420]；postprocess/row12/post_group_s24_r[527]生成逻辑 | local_stores`:150,176,110`的4b pair广播和16选1；`:108,122,126` post更新。region1为4列lane，out420对应row4/globalcol5/S24 bit12；accum`:87`为双wave输出选择 |
| 5 INT_X99Y765/WW2_E_BEG6，593 | input/wave1/capture_index bits0,2；input/wave1/wave1_s24[3115] | input`:26,95`；wave output经cohort`:34,45,76`连出。3115在6144b逻辑记录上为row4/group元素1/S24 bit19。`wave1_s24`是连接family，不能据名额外加6144b寄存器 |
| 6 INT_X18Y815/INT_INT_SDQ_32_INT_OUT1，600 | output/wave1/p_5_in；P/center/region3/row7col1/lane/high_act_u8_r[80],[79] | output临时网仅确定owner，候选范围同`:177,184,221`；lane high_act128b见lane`:29,125`，对应高半group元素26bit0、元素25bit7；globalcol13,row7，非全数组32768b单网 |
| 7 INT_X27Y850/INT_INT_SDQ_60_INT_OUT1，607 | output/wave1/i___5_i_2_n_0；P/center/region3/accum/finalize_wave_r；同bank/out_s24[16] | output临时网待网表；finalize选择见accum`:52,166,183,414`；region3 out16对应row0/globalcol12/S24 bit16。此bank为16lane，不走96lane动态分支 |
| 8 INT_X40Y812/EE2_W_BEG5，614 | postprocess/rope_read_pair_r[3]；row8/post_group_s24[205]；row12/data11[8] | pair广播同节点4；row8 post205在768b记录为元素8/S24 bit13，local_stores`:108,112`；data11是综合生成网，仅确定row12 bank内，不伪映射到特定源码变量 |
| 9 INT_X94Y824/INT_NODE_SDQ_8_INT_OUT0，621 | input/wave0/capture_index bit2；input/wave0/activation_r[5887]更新逻辑；P/frontend/input_fire_local_21 | input`:95`更新记录末行row7的部分（5887对应元素21bit7）；frontend`:88,93,175`的local capture域21覆盖逻辑记录[5376..5631]。该生成网与local21 family对应，实际接收FF数需A006确认，源码意图256b |
| 10 INT_X90Y735/INT_NODE_SDQ_70_INT_OUT0，628 | input/wave1/capture_index bit2；context_store/activation_s24[2408]；P/center/region0/row0col0/lane/sum2_r生成net | input同上；context2408为row3/元素4/S24 bit8，local_stores`:306`；lane sum2是8个S17加法结果寄存器，lane`:45,151`，globalcol2,row0。综合后缀`_1048`不能作为额外数组维度/复制数量 |

**边界**：节点1/3/5/9/10含input capture控制，4/8含同一RoPE pair控制，2/6/7含output serializer；这为定向查fanout/位置提供强线索。10个node均在Attention，不支持“245279全部由Attention/某单一RTL造成”的推断。临时网和优化alias的精确pin连通仍需网表证据。

## 6. 不改周期/端口的候选：先把目的bank和控制局部化

### C1：input/context静态目的槽，局部capture控制与数据owner

- 修改范围：`hap_tensor24_buffers.sv:37,59,95`，`hap_attention_cohort16_local_stores.sv:264,304`；保持activation6144b端口/valid周期、BRAMpipeline和组顺序。
- 机制：把变量part-select目的写改为generate固定256b×24或384b×16 bank，CE由明确槽等值译码控制；每bank有唯一owner，必要时按已实测扇出限制local同值control。与现有frontend/output的bank手法对齐。这里不是给slot数据加任意pipeline，也不是把同一index未经时序对齐另打拍。
- 预测：使高扇出地址译码和数据放置可控，减少跨区域CE/长线，不承诺LUT/FF减少。若综合已同样展开，语法重写可能零收益；区分性检查是目标control实际fanout/复制、6144b组装每bank位置、局部拥塞，而不是diff大小。
- 回归：每个源每组所有位的位精确scoreboard；slot0/23、context slot0/15、连续组和wave切换；read_pending/drain的两级次序；ready低时整组和tag保持；clear/rst在每个slot中断后重入无旧值泄露。综合检查无RAM变寄存器、无意外barrel mux、非时钟控制不得新增BUFG。

供主控最小实施范围使用（对应主控方案的C2；本报告候选编号独立）：

| 固定目的 | 保持原行为的同拍CE方程 | 数据与reset/clear边界 |
|---|---|---|
| input slot s=0..23 | `write_qual = !clear && active_r && !output_valid_r && read_stage_valid_r`；`slot_ce[s] = write_qual && capture_index_r==s` | 固定`activation_r[s*256 +:256] <- read_stage_data_r`，全slot保留原异步rst清0、clear时hold；原控制always的index/pending/valid更新全部不动，不加拍 |
| context slot s=0..15、region r=0..3 | `slot_region_ce[s][r] = read_pending_r && read_slot_r==s` | 固定`activation_buffer_r[s*384+r*96 +:96] <- read_region[r]`；保持原无data reset、并保留clear边沿旧pending可能写无效payload的原语义；parent有效性和16slot+drain不动 |

如果局部综合证实普通固定slice仍被合并成相同高扇出译码，可以评估**限定且可计数的组合物理边界**：input每wave24个local LUT6（5b index+1b预计算write_qual），两wave共48个，每个只驱动256b目的CE；唯一context store的16×4=64个local LUT5（4b slot+1b pending），每个只驱动96b目的CE。LUT是真值等式的组合实现，不能打拍，局部DONT_TOUCH仅保护已判定需要的CE副本，不扩散到整块data。采用该具体原语实现时，生产全设计是48+64=112个**显式protected decoder边界实例/标量CE输出**；它不是净LUT增量或全译码逻辑的LUT数量上界。write_qual自身的active/output_valid/read_stage/clear等组合逻辑仍需资源，原译码被替换/共享/删除也影响净值；完整设计的LUT delta待综合，不能把整个CE表达式假定为一个LUT6。

这些边界可能增加site与control资源；index/qual到本地译码仍要跨区域，源data仍广播到所有目的，因此绝不是消除所有宽连线或保证降低拥塞。当前综合可能已经等价展开，新增保护也可能让局部密度更差。此前阶段消息的88是漏乘input双wave的混合口径，本报告以112个边界实例修正，相关资源净变化保持未知。

判定其是否有实效须对比优化前后：目标CE驱动对象与load数、slot译码是否重复到每bit、index网fanout、同一区域内FF/LUT packing与congestion、BRAM类型、setup/hold。仅FF总数不变或RTL更清晰不足以声称改善；若综合网表函数/控制分布同构且没有位置/拥塞改善证据，应判该分支未取得有效修复，不据此直接启动一次完整route。

### C2：有依据地解除input activation数据的异步reset

- 修改范围只限`hap_tensor24_buffers.sv:68`及其数据always组织，双wave共12288b数据reset；保留active/valid/index/pending/error的原reset/clear。
- 机制：24个独立写槽全部完成后才输出valid，clear现已不清payload，说明现有协议本来就依赖有效位和完整覆盖。候选可去除大数据reset负载并改善control set/packing；**不是减少12288个数据位**，也不保证实际多收回同数FF。
- 尚需证明：所有`output_valid`上升都严格晚于同一epoch24个槽写入；reset/clear打断任一pending read后不会拼接旧epoch；非法load_start/地址仍原样报错；无效payload复位零值不构成外部ABI。复算脚本仅证明槽覆盖算式，未证明这些执行义务。只移除data reset，不放松安全审计。

### C3：保持3072b/6144b快照，静态行/beat选择和局部mux owner

- 修改范围：frontend`:119`，output`:172,177`，postprocess`:110,189,210`。采用显式行/槽bank和层次化选择，确保选择和data在同一owner附近；同周期方案不能以额外valid延迟偷换等价。
- 预测：减少分散宽bus在中心汇聚的布局压力；普通case/onehot写法不自动减少函数所需选路。onehot选择可能以更多AND/OR和控制线换深度，应以LUT/route估计、control fanout和slack决定，不能宣称“onehot天然省布线”。postprocess在保留同拍四worker输入时仍需要4×768b的数据。
- output当前已有beat-local6144b两tile储存和32个local CE/wave；不要把旧三tile9216b注释当当前可再次节省3072b的空间。

## 7. 数据寿命变化的较大候选

### C4：postprocess单bank按Q/K/V阶段复用，条件性少12288b payload

范围为`hap_attention_cohort16_local_stores.sv:93,107,122,126`和parent `hap_attention_compute_cohort16_top.sv:292,306,709,741,756`。候选用每row一个768b bank取代projection_pair与post_group双bank；Q直接供RoPE→query_store，K在该bank原址写回RoPE，V直接供quant。上限预测16×768=12288个源码payload位减少；mux/CE逻辑可能增加，不能写成实测少12288 FF或已安全。

| 当前合法阶段 | 原数据读写与生命周期 | 单bank需要保持的条件 |
|---|---|---|
| 每个Q/K/V group32的两projection half | 先偶tile波0/1写16行低384b，再奇tile波0/1写16行高384b；parent只在奇tile的wave1退休后转后处理（`:709,715,727`） | 两half/两wave全部覆盖后才能暴露完整768b；无valid仅因一wave完成就前进 |
| Q（tile<256） | RoPE输入256 pair按row0..15、pair0..15顺序；结果进独立query_store（`:338,340`）；该pair结束后projection_tile推进，不再从旧projection读Q | Q已存query后，原bank可被下一个Q或K覆盖；后续QK从query BRAM读，不依赖原projection bank。不得与query_store合并而破坏这一保留 |
| K（256..319） | RoPE输入同样256 pair；输出以`rope_output_index`按同序写post_group；最后输出index255后才quant（`:743,745,750`） | K读pair地址与写pair地址是同一row/pair映射；每地址在一次后处理只读/写各一次。`hap_rope_pair_s24.sv:98,117,152,165,174`显示输入→乘法→round→sum→FIFO的保序前缀流水，out_ready固定1，所以输出j在输入j之后，写回的是已读过的pair。单bank组合读在posedge输入采样，写为NBA，即使同拍同址也应明确read-beforewrite语义。仍需断言每write之前已read、无第二次read读到已变换值；禁止把实现变成与推断RAM冲突模式不明的端口 |
| V（320..383） | 不走RoPE；奇tile capture把当前高384b和旧even低384b复制到post_group；parent等wave1后进quant | 单bank删复制前需保证偶/奇half都已写完，16行均完成；量化输入与原拼接bit顺序逐位一致 |
| quant阶段 | 四路worker同拍各取一行768b，row batch0/4/8/12；parent等四路batch_last后才下一row batch或projection（`:756`，quantizer4`:41,68,75`） | 所选4行在in_fire前稳定；最后K写回NBA已在进入quant的前一边沿生效。quant期间无projection/RoPE写。单bank不能偷改成1worker序列化或改变KV12舍入/元数据 |
| clear/abort | parent清状态/indices，RoPE/quant清有效位；宽data原本不清。board的`datapath_clear`含soft_clear/command_abort，compute另含launch_compute_clear（board`:146`） | 清掉所有未完成结果资格，再次读取前必须整组重写。新的任何read/muxpipeline、版本/credit必须随compute_clear失效，不能误用仅datapath_clear |

源码说明当前合法FSM下存在可复用的数据寿命，没有发现必须同时保留旧projection与新post的跨phase需求；这仍是**条件等价分析，未取得修改后RTL/仿真/综合网表证据**。尤其K的读写并发、可推断存储类别、额外CE/mux面积和是否让同一bank连接更分散，必须实测。保留单bank之外的原始参考作为独立对照，不能更改expected结果。

**可见性限制**：这里最多主张parent合法phase中的accepted消费有条件等价，不能主张postprocess模块逐拍全端口等价。`rope_input_pair_s24`与`quant_s24`没有输出valid：K原位写回后，重新窥视/回绕RoPE游标会看到新值；projection capture期间窥视quant也可能与旧双bank不同。现有 `project/hardware/tb/hap_attention_cohort16_local_stores_tb.sv:200,219,247,252` 明确检查pair cursor及non-destructive wrap（目前并未覆盖K同地址写回后再读原pair的全部可见性）。实施者必须核查模块接口/调试窥视和这些原断言的合同含义；不能删除原测试或改expected来宣布等价。若原模块的非破坏性可见性是必须保留的接口要求，此单bank候选需拒绝，或另立明确的内部接口改造及parent级独立oracle验证。只靠合法parent当前不读该端口不能自行改写既有模块合同。

### C5：frontend改768b行接口/源所有权，窄化宽连接

当前producer只保证到6144b `activation_fire`的快照语义；**不能删frontend快照后边读边让源继续写。**

- input源在`hap_tensor24_buffers.sv:114`握手即启动下一group refill；frontend却要到`hap_attention_frontend_8row.sv:240`第8行Hadamard输入握手才释放快照。Hadamard/quant/cache允许背压，无固定8拍完成保证。
- context源在parent `:865`握手即进入下一group的16次读取；8行还没全部消费时组装寄存器可开始变化。
- 最小合法机制：让源拥有组快照直到consumer确认row7退休，再返还group credit；wave/group/context source choice必须在整组期间锁定；或保留独立snapshot/双buffer，每个slot有busy epoch。前者可能去掉frontend6144b快照，并把跨owner总线从6144b缩到768b；后者可能保吞吐但不省相同位数。
- 预测收益是宽连接/大快照减少，内部延迟/吞吐和control变化较大。若引入同步行RAM/registered mux，应把新数据valid和row/wave/group tag逐级延迟；原先一次组fire不能再隐含“所有行已复制完”。量化/cache完成、release两wave、project_start、清空/abort都重验。不能依据平均无stall周期证明所有权安全。

### C6：保留双wave BRAM image，共享input loader

`hap_tensor24_cohort16_buffers.sv:58,69,96`两loader同时预取，但只顺序发wave0全部128group再wave1；wave1首group会长期holding。可评估保留两份96KiB image，改为单物理loader、6144b组装和read pipeline，用wave选择BRAM读地址，外部192KiB row-major/DMA格式不变。预测少6144b组装、512b读stage和6144b wave mux。原先wave1首group已预取，共享会在wave切换引入一次约24拍加读pipeline的填组等待，必须重新量化，不能称同周期替换。ready/valid可容纳等待但cycle计数、watchdog/complete、clear和波顺序都需要回归。输出若尝试共享serializer也会改变原先两个wave同时独立背压能力，不能在本候选中顺带合并。

### C7：projection复制与宽权重head的物理owner改造

优先研究“复制在哪里”，不能一开始把2048b A8四份合并：group复制额外6144b、zero192b，下一拍六shard还有12288b activation stage，这是既有SLR/region扇出控制的设计。若A006实测某些副本实际同区拥挤，可试将复制移至消费者本地、给column-local两项weight storage明确owner，或只解除被证实多余的对象DONT_TOUCH。须保持pipeline两级的数据epoch、波0/1每group交替、权重仅波1 pop、128group标签/descriptor、GLOBAL_COL_BASE/4映射、128lane锁步及audit overflow/saturation。权重FIFO 8718b和4359b 2:1 head值得检查，但2entry直接换BRAM很可能浪费容量且改变read latency；未经局部综合不能报收益。

lane 16深LUTRAM FIFO的86016b来自真实128lane，不是模板16×16复制；未经容量/II/latency证明缩FIFO或改lane数会改变架构，不列为安全局部清理。也不改DSP数学、S42/S24边界、舍入或遥测。

## 8. 给下一阶段的区分性验证义务

本轮只分析，不启动下述动作；由主控/A007依据R001物理实测选择最小集合和实施合同。

1. **先明确真实因果基线**：目标模块的综合/physopt LUT、FF、RAM、control set、packing和SLR实测；capture_index/rope_read_pair/input_fire/expected_output_wave的真实load数/复制/位置。对照本报告的源码声明值，尤其不要把目标寄存器声明bit或临时net名当实际cell计数。缺失败route DCP，不能恢复全量245279节点空间归因。
2. **先分清同周期改写与寿命改变**：C1/C3同周期bank/局部译码，先确认综合网表确有改变；C2改reset资格；C4单bank改别名与写互斥；C5/C6改内部握手/周期。若将多个candidate同时改，至少保留每项独立源码diff和局部综合网表指标，避免又一次完整route失败后无法分辨作用。
3. **数值/协议检查**：独立bit-exact输入、projection/Q/K/V/RoPE/KV12/context/Wo与输出DMA映像scoreboard；原Hadamard/ScaleCode/format05/Attention format03/ABI/舍入及telemetry保持。随机背压、长stall、首末group/tile/wave、zero/extreme/signed/round-boundary、clear/abort及epoch重入必须覆盖；新增周期必须检查pipeline drain/tag对齐。不能为适配新代码删用例或放松期望。
4. **综合与局部物理门槛**：不得出现RAM→FF爆炸/新黑盒/新BUFG data control/新未约束路径；比较相同器件、时钟、XDC下目标FF/LUT、扇出、control sets、packing/SLR、setup/hold和局部拥塞。C1/C3若映射同构或拥塞未改善，不声称已优化。C4先看是否实降payload FF/局部LUT密度，再承认收益；C5/C6记录真实cycle/吞吐差。
5. **下一次完整route独立取证**：允许的时钟保持core100MHz/UI200+200MHz；next route必须自然成功并保存closed DCP/完整POST，`routable>0`、`fully_routed==routable`且unrouted/partial/errors均0；setup/hold/CDC/安全另判。即使再次失败也必须保存失败点DCP/route_status等可诊断产物。RTL功能通过和局部资源变好都不代表布通。

本批execution=completed，verdict=supported（仅上述源码结构/规模/样本映射事实），applicability=上述17文件与E003实际构建哈希一致的当前RTL；候选收益、物理因果和修改后的等价性仍inconclusive/unverified，review待主控/A007。生产实现未改，算法/接口/时钟无变化。
