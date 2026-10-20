# F1：真实字段、D/Q与消费者

E009固定导出单次离线提取；真实FF按primitive Q driver识别，名字不作为payload判据。全逐pin附件：[寄存器pin](F1_register_pins.tsv)、[Q全部读者](F1_Q_all_readers.tsv)、[D驱动与已导上游输入](F1_D_drivers_and_selected_inputs.tsv)、[CE/clock/reset](F1_CE_clock_reset.tsv)、[helper单列](F1_helpers_separate.tsv)；字段数组附件[F1_field_summary.json](F1_field_summary.json)。

生产TILE_W=9，每entry6560bit。下表Q数量是原生输入pin行数，不是网冲突数量。所有tail字段每bit都是1个同bit head-D helper读者；head D全部6560bit已覆盖。

| 字段 | packed位 | 宽度 | head Q实际branch0/1读者pin | head D driver SLR1/2 |
| --- | --- | --- | --- | --- |
| down/first/last | 0/1/2 | 各1 | 各2/2 | 各1/0 |
| tile | 3..11 | 9 | 9/9 | 9/0 |
| activation | 12..4619 | 4608 | 2304/2304，各半私有、每bit一读者 | 1/4607 |
| weights | 4620..6155 | 1536 | 1536/1536，共享 | 1535/1 |
| activation code | 6156..6283 | 128 | 64/64，各半私有 | 1/127 |
| activation shift | 6284..6379 | 96 | 48/48，各半私有 | 0/96 |
| weight code | 6380..6475 | 96 | 96/96，共享 | 96/0 |
| weight shift | 6476..6547 | 72 | 72/72，共享 | 72/0 |
| mask | 6548..6559 | 12 | 12/12，共享 | 12/0 |

私有每branch2416=2304+64+48，共享1728=1536+96+72+12+12tags。私有Q主要在SLR2，branch0接SLR0、branch1接SLR2；共享主要SLR1→SLR0/2。仅搬head不消除源至D代价；D driver位置与Q位置大部分相同，完整上游cone未导出不能猜测能同时搬走。

## Payload与helper、缺失项

HEAD13509 canonical=6560真实FF Q+6949helper/其他driver；TAIL6561=6560Q+1helper；META35=17Q+18helper。canonical `parent_head_r[0]`和`parent_tail_r[0]`实际为CE网络，各driver是`parent_*_r[6559]_i_1/O`的LUT6，SLR2 SLICE_X77Y604/X77Y614，各驱动完整6560FF CE；绝不是Q[0]。

head与tail所有6560 Q/CE完整；head D完整；**tail D、meta D/CE、所有C pin**不在已固定网级导出内。上游只保留选中网的一跳输入，其他NOT_MEASURED。不能以空表断言未接clock/reset或没有D逻辑。M2不改D选择，缺项不阻止精确组合等价方案，但新图G4必须逐bit核D/CE/Q/clock/reset；选C-M1真改payload银行才需针对性闭合旧上游细节。

RTL上游：serial command的P_GATE_RUN/P_DOWN_RUN选择gate/down各字段，tile仅down时取值否则0；parent_input_payload按上述位序拼接。M2保留全部输入和选择、H full+pop时读旧T、其他写H时读X；不增加上游数据/选择的逻辑fanout，物理线长受新placement影响须重测。

## A3真正变化

原core A为17个FDCE，Q251个原生pin读者=12 URAM×17位=204个地址pin+47logic（37个u_meta外、10个metadata逻辑），全SLR1。12直接根有deep属性；元store全部80URAM已定位（全部SLR1），其余68个只有固定轻量表的NAME/REF/LOC/BEL与native site/CR，lane/cascade等未测。

新A3：core A仍服务标签/范围/原控制，原204个URAM地址pin改由两片各17Q独立驱动；每Q允许自己的increment反馈及必要本地逻辑，但URAM地址读者必须只在所属片。每片实际数组读表达式使用自己的a_j；不是多counter仍喂同一个原`meta_mem[rd_addr]`。写地址/公共控制/256bit响应的上游和代价见[F2](F2_state_sampling_and_assertions.md)、[F3](F3_complete_costs_and_budgets.md)。两片width边界为8列×16bit，保持format05各column位域完整。

M2 81组逐bit mapping与原CR见[F1_F3_C_M2_region_groups.json](F1_F3_C_M2_region_groups.json)；它不改本表任何Q读者。E008 C01与E009 TOP01身份分别由[F4 A3/C01](F4_C_A3_two_slice_resource_rules.md)限定，不能将TOP01代表当C01证据。
