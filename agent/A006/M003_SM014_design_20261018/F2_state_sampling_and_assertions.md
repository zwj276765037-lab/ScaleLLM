# F2：原/新状态、采样和断言（M2+A3工程建议）

2026-10-18，A006；Root未选型，无生产改动。依据当前生产`hap_mlp_shared_dual_slice16x12_s44_s54.sv`、`hap_mlp_serial_ddr_command16_v5_s54.sv`、`hap_attention_board_cohort16_core.sv`及`hap_weight_meta_resident.sv`。本文件是精确设计合同，后续RTL仿真/新图验证不能由本说明替代。

## M2：保留两entry parent和branch ingress

记旧占用n，输入向量X，旧head H、tail T；`g=rst_n&&!clear`，`E=(n==0)`，`F=(n==2)`。

`in_ready=g&&!F`；`I=in_valid&&in_ready`；`V=g&&!E`；`P=V&&ready0&&ready1`。

branch0接收=`(V&&ready1)&&ready0=P`，branch1接收=`(V&&ready0)&&ready1=P`。两个branch ingress是额外独立在途状态，继续保留其两entry、指针、credit、clear和tag行为。

| g / I,P / n条件 | 原n' | 原H' | 原T' |
| --- | --- | --- | --- |
| g=0 | 0 | H保持 | T保持 |
| 10，n=0 | n+1 | X | T保持 |
| 10，n≠0 | n+1 | H保持 | X |
| 01，n=2 | n−1 | T | T保持 |
| 01，n≠2 | n−1 | H保持 | T保持 |
| 11 | n保持 | X | T保持 |
| 00 | n保持 | H保持 | T保持 |

计数按原2bit运算；不利用“非法n不可达”删改原case行为。满n=2即使P=1，本拍`in_ready=0`、I=0，下一拍才再开放输入；没有新组合credit或旁路。

原case等价精确CE（不是仅在合法占用下化简）：

```
H_CE = g && ((I&&!P&&E) || (!I&&P&&F) || (I&&P));
T_CE = g && I && !P && !E;
H_D  = (!I&&P&&F) ? old_T : X; // 只在H_CE时采样
T_D  = X;                       // 只在T_CE时采样
```

新H每bit使用所属head组LUT1(H_CE)，新T每bit使用所属tail组LUT1(T_CE)，LUT1 INIT=2'b10恒等；D仍按上式，不更改serial command gate/down相位选择或tail→head同bit连接。n计数更新独立保留原case。13120bit没有宽reset/clear赋值，失效payload保持原值，只有n清零使其不可见。

固定分组为生产TILE_W=9、payload6560的81组；其他参数实例按同一原状态方程走原CE路径，保持参数化功能。生产构建必须断言TILE_W9且81个buffer生效，不能默默落入fallback。SM015须额外使用生产宽度验证M2，不能只跑缩小TILE_W用例。

必须断言/覆盖：n≤2；full+P时I=0；两个branch accept均等P；所有I/P、0/1/2占用、连续full drain、交替/单边ready、clear与push/pop同拍；只在CE更新对应H/T，reset/clear时payload稳定；old/new每拍ready/valid/count和有效输出严格相等；branch ingress不得删除/共享parent entry。结构断言逐bit覆盖81个CE组，不以功能等价证明buffer存活。

## A3：地址同沿等价与resident单控制器

原core地址A为17bit，原pending为B。`S=system_clear`、`L=(state_r==ST_LAUNCH && weight_command_ready)`、`R=meta_rsp_fire`、`Q=meta_rd_fire`。core和resident的R均为同一`rsp_valid&&rsp_ready`连接，resident输出valid原有reset/datapath_clear门控保持。

原async reset：A=0、B=0。非reset时：

```
A' = S ? 0 : (R ? old_A+1 : (L ? 0 : old_A)); // 17bit回绕
B' = S ? 0 : (R ? 0 : (Q ? 1 : (L ? 0 : old_B)));
```

原ST_LAUNCH清零NBA在前、R递增NBA在后，L和R同拍必须递增**旧A**，不能变成0或1；不假定不可达。Q只设pending，不递增地址。timeout/协议/DDR/compute abort按原程序设`command_abort_clear_r`；`datapath_clear=S||command_abort_clear_r`会清resident，但不是A/B的地址reset事件集。保留A/B在abort时的原行为，下一次launch照旧复位。

新resident生产配置`LOCAL_ADDR_COPIES=1`，内部两helper各有17bit`a_j`；core A原样服务范围、tile/group、pending。每helper异步reset=0，独立用自己old Q计算：

```
CE_j = S || L || R;
INC_j = R && !S;
D_j = INC_j ? (old_a_j+1) : 0;
a_j' = CE_j ? D_j : old_a_j;
```

S/L由新**内部**sideband `addr_system_clear/addr_launch`送resident；R复用resident已有rsp_fire。两个helper各显式保护一个OR-LUT3(CE，INIT=8'hFE)及一个LUT2(INC，I0=R/I1=S，INIT=4'h2)，地址34FF设最小DONT_TOUCH/KEEP/SHREG_EXTRACT=NO。保护这些独立源和本地控制，不能保护整个resident/整个加法锥。不是`local<=A`，没有新寄存级；归纳式reset后`a_0=a_1=A`每拍成立，包括S/L/R组合和17bit回绕。自身increment反馈等必要本地逻辑可读取a_j，**URAM地址消费者**只属于该片。

legacy默认`LOCAL_ADDR_COPIES=0`仍走原单数组/原rd_addr路径，不消费新sideband，避免其他board core被迫改变事件语义。生产cohort明确启用1；新参数与内部端口不改变顶层时钟、外部接口/周期。SM015须编译原所有resident实例，检查默认模式不受未连接sideband影响；生产图必须真实使用split分支。

## A3：存储、返回、计数的逐沿关系

原M[d]为256bit；新M0[d]=M[d][127:0]，M1[d]=M[d][255:128]，d范围0..81919。只有一份原`wr_ready/rd_ready/wr_fire/rd_fire/rsp_valid/rd_port_open/count/error`控制：

```
wr_ready = rst_n && !datapath_clear && wr_addr<81920;
rd_ready = rst_n && !datapath_clear && token && A<81920;
rsp_valid = rst_n && !datapath_clear && valid;
```

共同wr_fire在同沿用同wr_addr写两个切片；共同rd_fire在同沿各用自己的a_j采样旧M_j[a_j]到原rsp_meta_r对应半字，直接按原位序拼接。write/read同地址同拍按原NBA读取**旧值**，不能一片新一片旧；不增加返回mux或输出级。ready合法性仍看原A，不截地址偷映射非法项。

| 状态/事件 | token' | valid' | 数据/计数 |
| --- | --- | --- | --- |
| async reset或resident clear=datapath_clear | 1 | 0 | count/error原样清零，memory与rsp数据无新增reset |
| 非clear，rd_fire | 0（优先于rsp_fire） | 1（尾NBA优先） | 两半响应同沿采样旧memory |
| 非clear，仅rsp_fire | 1 | 0 | read_count+1 |
| stall/no事件 | 保持 | 保持 | rsp数据稳定 |
| wr_fire | 不因写改变 | 不因写改变 | write_count只加1；format函数/错误判定仍全字执行一次 |

单pending与non-fall-through token保持；不实例化两份完整resident后合并ready/valid/count。最早第t沿接读，第t+1沿消费响应并开放token，第t+2沿再接读；含首尾三个采样沿，**请求间隔为2个clock周期**，上层其他限制可能更长。不宣称II提升；响应数据/valid仍在请求采样沿后原来的时间可见，无额外输出拍，输出stall任意长也逐位稳定。

必须断言/覆盖：reset及每沿a0=a1=A；有效采样地址相等；L&&R与S&&L&&R；Q&&!R地址不变；abort-only地址保持原值而resident valid清空；0/81919/81920/131071和wrap；同地址read/write旧值；一份读写/token/格式/error计数；两半同步valid/stall且拼接等于old word；反压/clear交错/重发命令标签与tile/group一致。RTL差分仿真、原生URAM RDW配置及新图结构各自验收。
