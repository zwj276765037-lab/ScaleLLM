# KV128、16 请求、七轨重复功耗测量合同

状态：**PARTIAL_WITH_LIMITS，最终方法验收完成**；2026-11-02。main_004完成12/12正式窗口；空闲与完整KV128解码步各3次建立全窗遥测均值，Attention/MLP各3次仅建立共同覆盖时段均值，详见[最终验收记录](method_review.md)。本段仅更新实测状态，以下预注册采样、覆盖和有效性合同不作事后放宽。本合同服务于已授权的本轮补测。硬件仍为 VCU118 / XCVU9P、Decode16、80 MHz 发布镜像；不修改 RTL、bitstream、稳压器设置，不综合、不重新烧录。阶段内普通脚本修复和验证连续执行，最终集中验收。

## 1. 测量对象、范围和不可替代的结果

用户已明确：**完整推理窗口是固定 KV128 的一次完整解码步，含 32 层 FPGA Attention/MLP、CPU Down、LM head 和 token commit，至少三次独立恢复后的重复**。不要求每次从位置 0 重新构建到 127。真实历史只需受控构建一次，或复用有完整身份和恢复验证的既有状态；不能用五层 Attention 和一层 MLP 的旧捕获代替完整 32 层状态。

四类窗口均至少 3 次：`idle`、`attention_repeat`、`mlp_repeat`、`full_kv128_step`。A/M 重复是固定真实输入的命令重放，完整步是正常 runtime.step()；两者代表不同工作负载。重复 A 采用已有真实捕获的五层固定循环 0→8→16→24→31，完成整轮五层后才停止，使各层次数相等；M 为 layer 0。分别报告各层次数、cycles与条件读数。五层循环是本轮明确定义的混合重放负载，不称为全32层平均Attention功耗。

主要可建立量为**七个指定稳压器输出的、按实际观测时间加权的遥测均值**。它不是整板输入功率、芯片独占功率或无误差瞬时功率。物理测量/滤波窗口未有可信上界时，`strict_active_mean_w`、`physical_active_energy_j` 保持 null。长重复减少边界比例，但不会自动证明传感器时间窗或绝对精度。

| 地址 | 电源轨 | 器件 | 本轮主要功率 | 独立 POUT 字段 |
|---|---|---|---|---|
| 0x70 | VCCINT_FPGA | MAX20751 | 实测 VOUT × IOUT | 每 sweep 读取 0x96 |
| 0x11 | VCC1V8_FPGA | MAX15301 | 实测 VOUT × IOUT | null，文档未支持 |
| 0x12 | VADJ_1V8_FPGA | MAX15301 | 实测 VOUT × IOUT | null，文档未支持 |
| 0x15 | VCCINTIO_BRAM_FPGA | MAX15301 | 实测 VOUT × IOUT | null，文档未支持 |
| 0x14 | VCC1V2_FPGA | MAX15301 | 实测 VOUT × IOUT | null，文档未支持 |
| 0x72 | MGTAVCC_FPGA | MAX20751 | 实测 VOUT × IOUT | 每 sweep 读取 0x96 |
| 0x73 | MGTAVTT_FPGA | MAX20751 | 实测 VOUT × IOUT | 每 sweep 读取 0x96 |

MAX15301 官方完整命令指南及数据手册命令表未列 READ_POUT/0x96。四轨必须留 `read_pout_raw=null`、`pout_status=NOT_SUPPORTED_BY_DOCUMENTED_COMMAND_SET`，不可伪造码值、把 V×I 填入原始 POUT、或把没有发出的事务赋予读取时戳。本轮不向这四轨试发未知 0x96。支持范围不足是硬件事实，不应阻止七轨 V×I 连续测量。

## 2. 已核实的传感器事实及保留的未知

官方链接、核查位置、下载情况见 [references/source_facts.md](references/source_facts.md)。

| 项目 | 证据 | 合同解释 |
|---|---|---|
| MAX20751 IOUT 更新 | 数据手册 Rev 2, 3/15, p.6：512 µs | 表列更新值；本轮未证明最大延迟，不作为完整物理窗上界 |
| MAX20751 VOUT / POUT 更新 | 同手册 p.7：各 3 ms | 不推导成 3 ms 矩形平均、不等于 USB 读取周期 |
| MAX20751 分辨率 | p.6–7：IOUT 0.5 A，VOUT 5 mV，POUT 2 W | 与现场 raw 指数/码差分别核对；分辨率不是准确度 |
| MAX20751 内部平均/滤波核及寄存器年龄 | 已查两份官方文件未获得可用数值上界 | `UNKNOWN`；不从输出码保持时长反推更新率 |
| MAX15301 IOUT | 指南 p.30：8-bit 基础测量，filtered and decimated，需电流校准 | 返回更多码位不等于更高模拟精度；只读保存现有校准 |
| MAX15301 VOUT/IOUT 遥测更新周期、内部平均窗口 | 已查资料未建立 | `UNKNOWN`；INSNS 每 4 µs 是输入电压路径，不能移用；READ_DUTY_CYCLE 的 256 PWM 周期平均也不能移用 |
| 现有主机读延迟 | 历史 VCCINT V/I 包络中位约 10.6 ms | 仅历史；本轮按器件/寄存器/状态测 p50/p95/max 后定频率 |
| 校准及真实板级电流误差 | 可保存 IOUT_CAL_GAIN/OFFSET，但没有外部标准仪器校准 | 不宣称本轮建立绝对精度；器件高电流特定条件误差不可直接套轻载 |

所有 fresh 读取是发起新的 API/总线读取，不保证取得刚刚完成的新 ADC 转换。相同码不证明缓存/未更新；变化码也不证明完整转换发生于 BUSY 内。寄存器间不保证同时采样。

### 2.1 数值合同

每次保留小端原始字节和原始 word，独立于 PowerTool 物理值解析重算。Linear11：`e=sign5(word>>11)`，`m=sign11(word & 0x7ff)`，`value=m*2**e`。不清零合法负电流/负功率，不用标称电压填补丢失电压。

MAX20751 必须现场读到 `VOUT_MODE=0x20`，VOUT 为 VR12 VID：`V=0.25+(raw16-1)/200`，有效码为 1..255；0、高字节异常或模式冲突保留原码并判为无效。示例原始码 121/131/191 分别是 0.85/0.90/1.20 V。IOUT 指数应为 −1，POUT 指数应为 +1，异常不得悄悄解释为正常电流。来源为官方 PMBus 指南 Table 9、§7.4 Eq.28；旧 `raw/512` 反馈电压解释已经撤回。

MAX15301 应现场核对 `VOUT_MODE=0x14`（Linear、指数 −12），`V=unsigned16/4096`；IOUT 按返回 Linear11 解码。现有校准读出后不二次施加到 READ_IOUT，避免重复校准。不能通过改变系数让读数接近预期值。

主要记录 `p_vi=V*I`，三条 MAX20751 另存 `p_pout`。逐轨报告 raw 码集合、相邻不同码最小差/指数、编码步长、变化比例、负值、V/I/P 读取偏移。固定 V=0.85 V 时，0.5 A 电流步长对应 V×I 0.425 W；V 变化时不能把所有乘积解释为单一 0.425 W 格点。POUT 2 W 档更粗，不能据此证明 V×I 更准确。VI 与 POUT 时间不重合时，不以逐点差值评价仪器误差；用同一长窗的时间加权差与散点作一致性诊断。

## 3. 先表征，再确定采样频率

1. 持有既有板卡独占租约；32-bit 官方 PowerTool runtime 及 XML/DLL 文件核对既有哈希；只开放表中地址。前后 CSR 验证发布 ABI、80 MHz、layout/format/capability。记录 bit 文件 SHA；它与 CSR 只构成运行身份链，不是整片 bitstream 读回。WMI boot 时间几秒差异不能单独证明重新开机；采样器/命令跟踪使用当前同机 QPC，旧 QPC 不可跨启动拼接。
2. 一次只读配置阶段读 VOUT_MODE、已知支持的 IOUT_CAL_GAIN/IOUT_CAL_OFFSET；保存每次读取原码及包络。不得写稳压器、mux、清 fault、切换电压或传感器模式。
3. 先运行 60 s 七轨空闲读延迟 pilot，17 个 fresh 事务/sweep（3×3+4×2），无额外人为 sleep；实际probe_001冻结入口上限为MaxSeconds=60、MaxSweeps=10000、外层100 s硬限（2026-11-02主控报告已启动）。这是只读读延迟pilot，不是正式重复窗；该上限不等于会取得10000 sweeps。保存实际 sweep、各轨各命令、V/I 包络 p50/p95/max 和异常。A/M 短功能 pilot 记录负载状态下延迟是否变化，参数确定不依赖功率差是否“好看”。
4. 主采样目标周期 `D=max(0.100 s,1.25*pilot_sweep_start_to_start_p95)`，向上取整至 10 ms。这里使用实际sweep起点到下一起点间隔（含日志等开销）的最近秩p95；duration另报。若实现采用等效更慢周期，运行前固定且说明原因。用单调时钟按 sweep 起点调度；超期不重叠、不补发追赶，不把 sleep 参数当实际频率。D、实际每轨间隔、错过期限数必须保存。若 D>1 s，先检查接口/重读开销，保留 pilot 并报告观测能力不足，不以无限加长窗口绕过。
5. 以上 D 是主机延迟约束下的观测设计，**不是测出的传感器更新率或Nyquist保证**。MAX15301 时窗与两器件内部平均窗保持 UNKNOWN 后可继续长窗遥测统计；严格命令物理功率指标继续不可建立。

**probe_001结果与正式冻结值（2026-11-02独立复核）**：594轮、4158轨点，10098遥测事务和7次mode读取，API错误0。实际sweep起点周期中位101.6167 ms、p95 106.529 ms、最大170.1735 ms；sweep duration中位100.51735 ms、p95 104.931 ms、最大164.0938 ms。按既定规则得到 **D=140 ms（名义7.142857 sweep/s），G=3D=420 ms**；正式采样器采用起点调度。该频率是观测频率，不是物理传感器独立样本率。正式负载下仍记录实际各轨间隔/延迟，不能把空闲pilot延迟当负载上界。

短测三条MAX20751全程恒码：VCCINT V×I=5.525 W、POUT=6 W；MGTAVCC 0.45 W/0 W；MGTAVTT 1.80 W/2 W。恒码无法证明器件ADC未更新或物理功率恒定。四条MAX15301均有动态码；VADJ的556/594个IOUT值为负（范围−0.06134033203125..0.01922607421875 A），按有符号返回值保留，不截零或当disabled。此空闲pilot不计入正式三次idle重复，也不替代正式窗的时间加权功率。

短测未读CAL，单读原码嵌入完成rail_point后持久化；正式采样器须补齐只读CAL与逐read即时日志，修复连续执行，不将短测成功误写为正式原始记录合同已全部完成。原始证据与独立复核见[method_review.md](method_review.md)。

保持固定地址次序并在每个sweep循环改变起始轨（probe_001实际为sweep mod 7）；记录每次完整次序。可采用预先固定的循环轮换以减少地址顺序锁相，不能基于读数决定下一条读哪轨。V、I、P 的同轨读取次序为 V→I→P，或明确保存已批准的固定变体。

## 4. 窗口、长重复和采集边界

- `idle`：权重/请求恢复完成后，FPGA 无命令、无本任务DMA；每个正式窗 120 s，至少 3 窗。采样器正常运行；主机监护活动保持一致。idle 不等于整板所有负载关闭。
- `attention_repeat` / `mlp_repeat`：每窗目标至少 120 s，至少 200 个各轨有效 V/I 观测，至少 3 窗。用自然完成的原命令构成持续重复，不拉长 BUSY、不插入 RTL 等待。达到时长后在正常 ACK 完成的静默边界停止。恢复、输入DMA、descriptor写、完成输出读与ACK间隙计入整个重复负载窗，逐类记录。
- `full_kv128_step`：起点为恢复完毕后即将调用 runtime.step()，在embedding/首层准备前；终点为完整32层、LM head、token commit完成返回后。窗口含全部CPU/传输/调度间隙，至少3次恢复。恢复操作和预备校验在窗外但仍连续记录电源，并有独立区间。
- 主采样在每个正式窗之前至少10 s开始，并延续至窗后至少10 s，以便每轨时间积分覆盖两端。这是边界观测设计，不宣称10 s保证内部物理稳定。
- 在三个区组内安排 idle 与 A/M/full，预先固定平衡顺序，例如区组1 A→M→full、区组2 M→full→A、区组3 full→A→M，各区组配idle。完整步恢复条件可能要求调整顺序，调整在运行前登记；不看功率结果后挑选保留重复。
- 不把未知温度记作受控。报告执行先后、冷却/静置时长和长窗首尾漂移。主结果保留完整窗，另可报告固定去除前后10 s的敏感性结果，不以“稳定段”择优替代正式窗。

每条命令记录 START写前后、每次STATUS读前后与值、首次/末次BUSY、首次DONE、completion descriptor、DONE_ERROR、bytes、cycles、ACK与静默确认。保守BUSY内窗为 `[first_busy.after+2 ticks,last_busy.before-2 ticks]`，至少两次BUSY观察且长度为正。`core_time=cycles/80e6` 与 QPC 内窗分别报告；饱和/零cycles不接受。报告command数、core累计时间、BUSY可证内窗并集长度、各类间隙p50/p95/max、cycle/wall比与BUSY内窗/wall比；二者不是同一占空比。

相邻命令的host间隙可用上一条ACK/完成至下一条START等操作边界分解；不得将“正式窗减BUSY保守内窗”全部解释为真实硬件空闲，因为BUSY边界观察也不完整。

## 5. 请求身份与可重复恢复合同

### 5.1 所有重放

固定原16请求、active_mask=0xffff、每槽position=127、原request epoch、真实token history、输入、权重、量化参数与RoPE。KV128表示本命令追加position127后读取0..127。不能使用随机、重复填充、零填充KV或仅改变descriptor长度替代真实历史。每条实际执行使用不重复、非零command_id和buffer_generation，禁止溢出；保留batch_tag与request epoch的原语义，另设run/block/repeat/iteration标识，不能只改标签就声称恢复完成。

每命令正常完成后验证全部completion descriptor与当前命令相等、错误为0、字节数正确、cycles非零非饱和、输出长度和至少基准hash一致，然后合法ACK并确认静默。对捕获输出的逐字节一致性是重放一致性证据，不能改称独立模型数值oracle。失败后保留pending/DONE证据并停止，不绕过ACK或用旧输出代替。

### 5.2 Attention重放

使用旧真实layer 0/8/16/24/31 KV128捕获中各层自身的input、descriptor、RoPE、kv_before和output及其身份。五层固定循环，不能共用layer0输入冒充其它层。完整该层KV为8 MiB；每槽512 KiB，position127写入槽为每槽4 KiB，共16×4 KiB=64 KiB。地址由既有layout计算：`0x60000000 + layer*0x800000 + slot*0x80000 + position*0x1000`，禁止手工推断其他位置。

基准路径每次恢复该层完整8 MiB kv_before并readback hash，恢复时间计入重复窗内间隙。经局部功能验证可改为只恢复16个position127槽：先完整恢复一次并readback；执行一次后验证全层差异仅发生在这16个目标槽、0..126历史hash不变；后续每次目标槽恢复并readback验证，循环结束再核对完整历史hash。输出必须匹配基准。若不能证明局部恢复等价，继续完整恢复，不牺牲状态正确性追求高BUSY比例。

现有KV DMA先完成当前position全部K/V写入，再reload 0..position；持久record存{112零,meta16,s12数据384}，不携带request epoch。epoch只在当前命令/握手中验证，故正确epoch不能证明DDR历史正确。确认该实现与发布镜像源身份后方能使用局部恢复结论。不以重复A的结果更新逻辑position或generated tokens。

### 5.3 MLP重放

固定真实layer0 MLP输入、当前层Gate/Up权重及metadata；遵守原输出校验/ACK。该命令不写KV，无须制造KV恢复DMA。此窗的“MLP”指发布镜像中的在线Gate/Up+SwiGLU命令，CPU Down只属于完整步；必须在图注中明确。

### 5.4 完整KV128解码步

入口必须是完成position126后、position127尚未提交的全部32层真实历史和host状态。可一次受控warmup构建，保存全部256 MiB KV（或有数学/字节级充分证明的等价恢复集）、16槽的epoch/position/prompt/generated/max_new_tokens/finished、输入token、EOS保持策略，以及runtime/asset状态身份。

每次step前验证所有16槽position127且活跃、输入token一致、历史0..126一致、所有层KV目标槽恢复、模型/权重/RoPE身份匹配；完整拷贝/readback校验为基准。可证明只写当前position后采用逐层目标槽恢复，但必须在每次重复前检查history hash及host深复制状态。batch_tag恢复到入口语义；command_id/buffer_generation不能倒退复用，使用新的执行身份。不同状态类别必须分开，不能把整个runtime对象粗暴回滚造成completion身份重用。

**已授权现存DDR恢复路线（带限制的来源核验）**：为避免无必要地重新执行约3小时自然前缀，可在尚未发新命令、独占且无竞争的前提下，只读核查当前发布CSR、旧run末命令completion身份、操作系统真实启动事件及已保存执行/清理轨迹。WMI启动时间几秒差异单列，不以该差异独断重启。对旧捕获5层逐槽比较position0..126完整字节；position127已被最后一次真实执行写入，不要求它与旧kv_before相等。其余27层作全量record格式/padding与非全零检查并保存每层hash；此检查不能证明其历史来源。随后保存全部32层当前DDR快照，并将position127恢复为明确的基准值，host入口由原prompt+完整token历史重建。对每次恢复进行readback hash。

现存DDR路线首次完整step必须逐字节匹配旧5个Attention输出与L0 MLP输出，全部16个末步token匹配旧run，并通过64命令/全槽/层序/commit验收，之后才能将恢复后的状态用于正式3次测量。该路线仅为**同一实现、旧真实运行连续状态的功耗负载核验 PASS_WITH_LIMITS**；其余27层KV的历史未独立逐字节认证，输出/token匹配也不是独立完整模型oracle。任一连续身份、已有历史比对或完整step验证失败即停止沿用，不可忽略冲突，转已授权的一次受控warmup重建路线。保存证据不足时标INCOMPLETE，不改措辞绕过。

每次step恰有32 Attention+32 MLP，层序0..31，16请求全活跃；包含CPU Down和LM head；最终position128、正确token commit。逐次记录token IDs/输出hash，与首次同状态执行比较。三个step为同一真实checkpoint的受控技术重复，不能声称三套独立prompt或独立训练样本。原独立完整模型oracle未建立这一限制保留。

## 6. 原始记录的最低合同

每条bus_read包含run/block/repeat/sweep/read_id、rail/address/regulator/command/code、UTC、同机QPC频率和before/after ticks、原始字节、byte_count、小端word、API状态/异常、fresh_hardware_read。API未暴露ACK/native返回码时明确NOT_EXPOSED；不得推断成功ACK。采样器与命令端同机、同启动期的QPC校验记录保留。

每个rail sample引用具体V/I/P read_id，记录VI包络、V与I中点偏移、mode、原始码、解码值/指数、valid与reason、V×I；POUT不存在明确unsupported。失败事务也立即流式保存，不能等整个sweep成功才写。若进程中止，保留已写记录与原始退出码/未知状态，不能事后伪造exit0。

## 7. 时间权重、异步七轨求和与重复差异

令同轨V/I事务包络为 `[a_i,b_i]`，主要点时间 `t_i=(a_i+b_i)/2`，值 `p_i=V_i I_i`；POUT使用自己的事务中点。这个时间是观测定位约定，不是ADC采样时刻。每轨单独排序，要求严格单调、有效解码、无重用read_id。超长事务保留但不用于正常插值：VI包络或相邻点间隔大于 `G=3D` 标为缺口，G在主测前冻结。无效点不得删除后跨过失败时间连线。

相邻合格点间用分段线性 `p_r(t)` 插值；禁止窗口边界外推。每轨有效覆盖 `C_r` 是相邻有效点所支持的区间与目标窗 `W=[A,B]` 的交集。单轨完整窗结果与仅覆盖区域结果分别报告。

七轨共同覆盖 `C=交集_r C_r`，可由多段区间组成。先取所有轨断点、窗端点和缺口端点的有序并集，逐段检查七轨均有支持；仅在共同段积分：

`E_r(C)=Σsegments (right-left)*(p_r(left)+p_r(right))/2`

`P_r(C)=E_r(C)/|C|`

`E_7(C)=Σ_r E_r(C)`，`P_7(C)=Σ_r P_r(C)=E_7(C)/|C|`

这是同一时间支持上的遥测求和。**不得将不同时间段的各轨均值直接相加，不得给一轮异步读数之和虚构共同测量时刻。** `coverage=|C|/(B-A)`。只有C完全覆盖W（允许不超过2 QPC ticks数值舍入）才给 `full_window_telemetry_mean_w`；否则该字段null，明确报告 `covered_telemetry_mean_w`、缺失秒数/区间和coverage。严禁把coverage<1时的E除以完整墙钟而把缺口当零。

同一方法用于每个重复，保留轨间异步偏移和每轨原始点。另做前值保持（zero-order hold）与线性插值的敏感性对照，使用同一C和G，不将二者差当完整误差棒。至少报告完整窗/固定去边10 s两种口径（后者有足够长度才适用）。不得用FPGA duty去除主机间隙或外推连续满载功率。

重复统计以正式窗为单位，n>=3：给每次结果、算术平均、样本SD、min/max、range和（均值非零时）CV。另给按有效时长加权的pooled均值 `ΣE_j/Σ|C_j|`；它与等权重复均值分开。三次技术重复的离散度不是校准精度或置信度；同一窗口的数千采样点不是数千独立实验。idle差值按预先配对的相邻区组计算并给逐次差，未知系统误差不随样本数缩小。

### 7.1 条件BUSY读数

只有完整V/I包络位于同一命令的保守BUSY内窗时标 `transaction_contained_busy=true`。报告每轨每opcode/layer的入选点数、被覆盖命令数、总命令数和相对phase分布。条件均值/中位数/分位数与全窗时间加权均值放在不同字段/表中。

`physical_aperture_contained_busy=null`，除非未来有独立证明。不得把有条件点的平均或统计误差条标作整个命令的物理平均功率。BUSY内窗上的插值积分即便计算，也只能标为窗口筛选的遥测估计，不能替代上述物理指标。

## 8. 图表与交付

交付原始JSONL、phase/command/read/rail CSV、逐重复和总汇总JSON、as-run源码与配置manifest、退出/清理回执、离线复算入口及静态PNG/SVG。

图至少包括：七轨原始V×I点随时间及各窗边界；三轨V×I与POUT原始码/编码阶梯对照；同时间支持的七轨总遥测曲线（标注插值和异步）；BUSY内窗和间隙时间带；四种窗口每次重复的均值点及SD（图注为重复离散度）；条件BUSY读数独立图。点不能通过平滑隐藏；长图可分面并另给降采样概览，但数值积分始终使用全部合格原始点。坐标单位、测量点数、覆盖和七轨非整板范围必须可见。

## 9. 资源、停止与阶段验收

只运行一个本任务板卡作业和一个PMBus采样器，独占租约；不运行Vivado。沿用主机资源上限CPU0–7、任务进程树RSS<=8 GiB、系统可用RAM>=2 GiB；CPU可用集合不符先处理配置而不是越界。命令超时复用现有120 s上界但正常耗时基于pilot核查；主测墙钟预算在执行入口记录，包括一次warmup的实测/历史估计（旧完整128步约9843 s）。不得隐瞒warmup成本。每个A/M正式窗硬上限180 s到达后在安全ACK边界收尾，不能无限等待凑足采样。

身份/mode不符、合法地址通信异常、QPC域无法对齐、内存保护触发、请求/KV/输出验证失败、命令错误/超时、sampler失联、租约丢失时停止新命令，保存已得证据并清理自有进程；不得影响他人进程。异常原始码保留；禁止通过删异常或减覆盖使测量PASS。真正硬件pending错误按既有恢复协议处理，不擅自复位/重烧。

### 9.1 同合同安全停止后的恢复（main_001已触发）

因主机监护实现问题而在无pending命令的正常ACK边界停止，不改变RTL、bitstream、数值参考或覆盖时，实施者连续修复并复测；不新增逐次审批门。保留失败尝试原始FAIL、退出码和全部日志，新尝试使用新run_id。失败资格前缀不计入正式12个窗口，也不能补足下一次64命令资格。

main_001在资格阶段完成43条命令8193..8235后停止，末命令为Attention/layer21、DONE_CYCLES=3599001。恢复前必须独立核对这43条trace及当前live CSR全部字段：静默STATUS=0、ADMISSION_ERROR/DONE_ERROR=0、ACK_ID=8235、完成descriptor全部64 words、输入/输出bytes和cycles与末trace一致；不能只检查ACK_ID。任何不一致都保存并停止沿用。当前live全32层256 MiB KV必须与inspection_002快照（SHA256 `fa610d68fab6045573a355313f78808c93b7273dbf1edc2e8f61bc3ea1ad81c8`）逐字节相等，比较前不得先写快照以掩盖变化。旧snapshot哈希与文件身份也核查；live相等是本次恢复前置条件，不能由旧snapshot自身哈希替代。

通过上述只读恢复检查后，新命令ID和buffer_generation从8235之后继续递增（首条8236），保留请求position127/epoch和原batch_tag语义，host checkpoint恢复。重新执行完整64命令资格、6个旧捕获output/16个末步token比对，然后重新执行原定12正式窗口。当前state的历史来源限制与未知传感器时窗保持不变。

心跳监护保留10 s停写阈值。避免在同一表达式先读取wall time再stat可能刚被更新的mtime而产生负age；优先用单调时钟与已观察到的文件增长/序列进展计时，文件缺失/缩短/身份变化按错误处理。初始监测状态必须来自已就绪且有raw记录的sampler，不能每次检查都重置停写计时。若仅采用先stat后time的等价局部修复，也保留同一10 s门槛并覆盖并发更新时间的回归。源码诊断未记录现场age时，不把负age写成已直接观测值。

阶段可给 `PASS_WITH_LIMITS` 仅当四类各>=3有效正式窗、七轨原始数据及时间权重可复核、完整步64命令和16请求恢复正确、模式/解码/退出清理均已核对。覆盖不满的重复可作为明确降级观察保留，但不能计为完整窗均值通过；不足三次则整体 `INCOMPLETE`，不挑剩余点凑重复。传感器物理时间窗和整板范围限制即使阶段通过仍保留。最终审核见 [method_review.md](method_review.md)。

## 10. 仓库证据位置

- [已有测量说明](../DOWNLOADS.md#archive-files)：旧七轨积分、MAX20751勘误、KV128条件观察的边界。
- [PMBus v2合同](../DOWNLOADS.md#archive-files)：fresh读取与QPC BUSY内窗。
- [现有VCCINT采样器](../DOWNLOADS.md#archive-files)：原始读取记录可复用；三轨/七轨扩展不能照搬每10组POUT。
- [真实KV128捕获](../DOWNLOADS.md#archive-files)：position127/epoch1、真实input/kv_before/RoPE/descriptor。
- [后端与完整step](../DOWNLOADS.md#archive-files)：run的完成/ACK协议，step的32层及原子token commit。
- [布局](../DOWNLOADS.md#archive-files)：KV_BASE、KV_BYTES、每层/槽地址。
- [KV DMA](../DOWNLOADS.md#archive-files)：当前position写入及reload协议。这里只读方法证据，未修改RTL。
