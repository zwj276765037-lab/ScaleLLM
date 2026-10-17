# R001 功能执行交付：A009 → A006

状态：2026-10-16，已执行。Attention AT001/v1和MLP AT003/v2实际PASS；AT002/v1编译失败原证据保留。以下保留首次交付执行说明；最终结果见run.md。A006唯一EDA调度；A009不启动EDA。原版身份见 `frozen_before/manifest.json`；本次10个输入身份见 `functional_delivery_v1.json`。实际运行每次另建AT，保留失败原日志，不覆盖v1身份。

## Attention 固定slot

- TOP：`hap_tensor24_input_slot_ce_tb`
- TB_PATH：`tb/hap_tensor24_input_slot_ce_tb.sv`
- PASS_MARKER完整行：`PASS: hap_tensor24_input_slot_ce`
- 请A006建立只含以下4项的测试manifest（相对hardware根）：

```text
rtl/attention/hap_tensor24_buffers.sv
rtl/attention/hap_tensor24_cohort16_buffers.sv
tb/m002_ce_reference/hap_tensor24_input_buffer_frozen.sv
tb/m002_ce_reference/hap_tensor24_input_buffer16_frozen.sv
```

冻结原版外部接口及两个物理wave的payload/valid/group逐周期比较，比较包括无valid期payload。独立row-major地址oracle逐256-bit槽检查，生产2wave×128group×24slot；非零地址/word/epoch互补payload。测试预期实际打印覆盖：192个2wave×24slot×reset/clear×写前/后中断；每次重写完整6144beat新epoch后校验两个首组；4次完整256group发送；257拍及随机短背压；last_slot_before/after各4，valid_interrupts4，异步非posedge reset97，wave0/group127边界中断2。上述数字为测试设计断言，只有真实日志达到后才能写PASS。有限2000000仿真周期完成断言，不是外部墙钟强停。

## MLP Gate/Down 输出CE

- TOP：`hap_mlp_repack_output_ce_tb`
- TB_PATH：`tb/hap_mlp_repack_output_ce_tb.sv`
- PASS_MARKER完整行：`PASS: hap_mlp_repack_output_ce`
- 请A006建立只含以下4项的测试manifest：

```text
rtl/mlp/hap_mlp_projection_repack12_to16_s24_history2.sv
rtl/mlp/hap_mlp_projection_repack12_to16_s32_history2.sv
tb/m002_ce_reference/hap_mlp_projection_repack12_to16_s24_history2_frozen.sv
tb/m002_ce_reference/hap_mlp_projection_repack12_to16_s32_history2_frozen.sv
```

同一top并行仿真两个小checker，Down生产ROWS16/MATRICES1/DATA_W32、Gate生产ROWS16/MATRICES2/DATA_W24；同一XSim进程，不增加EDA并发。每个接口全部payload/metadata/count/error/in_ready逐周期冻结原版比较。独立列FIFO把每个accepted输入的合法列追加到对应matrix，累积16列即按row取出，独立预测payload/metadata、容量、顺序与错误；不复用DUT case拼接/SRL。

覆盖16/32/48列完整记录、终尾4/8/12、全部16row、matrix交替、带高符号位payload、随机短stall及211拍长stall、背压payload/tag稳定、同拍消费/补入、rst/clear与产生输出资格同拍（payload保持但原SRL仍按input_fire推进）、清除后不同block重入；非法首pass、非连续mask、短非终尾、错block、非法matrix或pass、Gate mask/last不一致，以及1..12中所有非4终尾残余错误。每个checker有100000仿真周期完成断言。冻结原版与独立oracle若不一致应定位DUT/TB，不能删断言或改期待迎合DUT。

## 统一运行条件

使用A006更新的 `run_xsim_tb.sh TOP TB_PATH MANIFEST PASS_MARKER`，`HAP_XSIM_TIMEOUT_SECONDS=0`；串行、8CPU/nice5、资源监督按合同。runner需实际冻结manifest、TB、生产源、4个参考源、工具和启动入口；本表不是运行收据。两个新增TB不修改旧gold/旧断言；其余未改回归可引用原身份或由A006选择必要相关项。源在任何实际运行期间不可热改；A006明确发回终态后A009才修受影响源。

解释边界：`rtl_static_checks.json`只证明文本边界、参考派生和有限LUT真值表；功能PASS仍NOT_RUN。功能即使通过，也不证明48/32物理driver落实、扇出改善、合法route或时序通过。
