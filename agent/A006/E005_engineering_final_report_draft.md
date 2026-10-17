> 此草稿已由[固定工程最终报告](../../project/E005_m002_optimized_implementation/experiment_results/engineering_final_report_2026-10-16.md)替代；以下保留准备过程，不作为当前状态。

# SM009 / E005 工程最终报告（补采收尾中草稿）

本次完整implementation已取得新place/physopt父链，但Default route合法布通FAIL。失败现场与自然终态已封存；R006只读补采的placed阶段已完成，双phase与完整会话核验已通过；当前按合同补测新峰区域。本文件尚不是最终工程交付。

## 当前已核结论

- 局部RTL与功能由A009完成；实际Attention/Gate/Down差分、独立oracle与中断/背压覆盖见`R001/rtl_functional_final_facts.json`。局部功能通过不替代全系统或板级验证。
- 新综合真实48/16/16边界成立；原综合监督UNKNOWN与约2097.385秒观测缺口保留，后续独立恢复资格不追溯覆盖原状态。342源/45DCP父链已绑定。
- 原生OPT成功后原POST准入失败、后续CDC代表来源适配失败均保持独立AT。窄恢复及当前图适配实际198项、219项CPU检查通过；成功综合/OPT不重跑。raw debug verified0及hub300MHz声明对实际50MHz问题保持。
- R004/AT003新SSI_SpreadSLLs place及独立Default physopt、完整POST和诊断父链均通过；physopt原生说明setup非负、跳过setup优化且未改网表。正式hold仍FAIL，formal reset/CDC/外部IO安全仍OPEN。
- R004/AT004一次完整Default route自然失败；未改策略、未强停、未重复route。

## 布线前与失败路由

| 指标 | E005 physopt（布线前） | E005失败route诊断图 |
| --- | ---: | ---: |
| WNS / TNS (ns) | +0.103 / 0 | −13.528 / −1920757.000 |
| WHS / THS (ns) | −0.695 / −2145.408 | −0.258 / −468.768 |
| Hold failing endpoints | 30885 | 13151 |
| WPWS / TPWS (ns) | 0 / 0 | −0.537 / −3.018 |

阶段不同，不据此推导route时序改善。失败route不合法，全部诊断值均不能作routed签核。physopt资源CLB LUTs801751、CLB Registers1017050、CLB143802/97.31%，SLR1CLB99.85%，SLL18983，BRAM941/URAM752/DSP5451。

Phase9原生报告1148579重叠节点、758463因拥塞未布通信号，单位不同。route_status明确routable2031772、fully routed1273309、routing errors/resource conflicts各758463；未显式报告unrouted/partially routed，不补0。DRC含RTSTAT-13并说明RTSTAT-*未运行，report命令0不代表DRC通过。失败congestion文件只有Placer Final24行与Router Initial21行，无Router Final表，末期拥塞使用原生日志和R005既有独立审核。

R005同阶段独立比较表明E003→E005重叠节点245279→1148579、拥塞失败信号248289→758463，四方向末期Max Cong均上升、有效峰6→7。两个RTL及SSI布局同时改变，一次组合实验不分离孤立因果或判定方法普遍性。

## 自然终态与现场

AT004于2026-10-16T13:56:35.660913Z自然结束，Tcl/Vivado/worker/监督均1，stop_reason=null。checkpoint/status/timing/congestion/drc五项失败capture均原生0，原错误随后重抛。failed DCP779113008bytes、SHA2566d1cf5ef3fea7b8ca0ab7ba27aaa61383ce487a640bcb63248cb6a9af7009590，为diagnostic_failed_route，不进入成功route父链。原6个PID/start均不在，锁已释放，144生产输入未变。

3515资源样本，采样峰树RSS27.288212GiB、最低MemAvailable385.292797GiB、最低磁盘404.394199GiB，最大间隔6.013834秒，无保护触发。原生内部total15510.3秒、route含自动DRC15782秒、外层Tcl含1449秒失败capture共17233秒、整AT17864.645122秒属不同时间域，不直接混比。见`R004/AT004/route_terminal_engineering_summary.json`和其绑定的完整事实。

## R006只读补采（AT002闭合，AT003新峰区域进行中）

AT001在Vivado前因两条历史CPU记录缺state字段被拒，原失败保留。窄schema guard修复仅绑定两条原终态/双hash/PID-start，其他running/UNKNOWN/一般缺state仍拒；23项CPU检查通过。新AT002实际4cfa wrapper及Tcl归档、单EDA/cpu0–7/max8/nice5执行，依次只读各自closed place和physopt；无物理命令或checkpoint写入。

placed自然phase0、60项query全0；80边界与94目标net、14上游源、56原placedLOC实际device映射、48旧窗齐。原place DCP重新hash不变。Attention/Gate/Down边界精确源相对cross-SLR leaf pins0/1917/0；Gate rows2/4/6/7各384、row5为381。14上游共389leaf pins、13cross。负载各在单一SLR不能代替driver-relative计算。固定窗原生拥塞API未验证支持，统一UNAVAILABLE；实际GRID/tile/site/SLR资源与attached segments占用不是拥塞等级，重叠窗口不相加。

### placed三个精确目标层次

| 根层次 | Total LUTs | Logic LUTs | SRLs | FFs | RAMB36 / RAMB18 |
| --- | ---: | ---: | ---: | ---: | ---: |
| input | 6422 | 6422 | 0 | 12383 | 42 / 2 |
| Gate repack | 7024 | 4720 | 2304 | 6245 | 0 / 0 |
| Down repack | 5216 | 2141 | 3075 | 8282 | 0 / 0 |

三者LUTRAM/URAM/DSP均0。原生hierarchy重复root/parent行不相加；FFs为该表原列，不把全局CLB Registers另行混称FF。上述placed数据及原device映射/48窗已获A007独立复核，见`R005/R006_AT002_place_supplement_review_evidence.json`。源相对cross0的边界有75组，负载各在单一SLR有79组，两种计数不混用。Attention虽无跨SLR叶pin，单SLR负载仍有Xspan59–68、Yspan186–192，不能判为紧凑局部化。

## 验证边界

算法Hadamard/ScaleCode、format05、位宽/舍入、HostABI、双DDR角色、core100/UI200+200MHz保持；旧工程只读。正式CDC/reset/release/transaction/外部IO仍OPEN。原综合UNKNOWN、debug raw verified0、300MHz/50MHz、vendorXPM例外、外部input1/output2缺delay、OPT辅助coverage_limited保留。本轮不运行bitstream、板卡、GPU、PPL或ACC，也未获得可用bitstream。

AT002已于14:45:12.436500Z自然native/监督0闭合，20工程核验true；两phase各60queries0、144/两原DCP/archived源保持、原4PID/start无活体/锁释放。A007独立160身份核验表明physopt的80/94/97及48旧窗、48tile列表、四hierarchy数据均与placed相同，56mapping仅phase标签不同。422资源样本树RSS峰22.775665GiB、最低MemAvailable375.224209GiB、最低磁盘403.499451GiB、最大间隔5.146364秒。AT002的new_peak_source_reports空字典项仅N/A，不作为新峰已测证据。

审计识别新48行窗口和旧48窗端点零重合，旧aggregate不能推出新峰device映射。主控确认原合同比较义务，AT003新尝试已14:46:16.548276Z实际启动，supervisor899702/start927452343，精确ownplaceDCP open、CPU0–7/nice5/kernelFLOCK、a4178f固定源码与独立NW001–NW010目标均核符。仅每phase12峰行对应10unique区域的实际GRID/tile/site/SLR资源与attachedsegments，原新48行全保留；不重复80/94net/层次或物理命令，固定拥塞UNAVAILABLE。待完成该双phase映射与自然终态、144/原DCP/源码/资源/进程锁核验，随后提交最终工程交付。三摘要/mission/results由主控整合。

## AT003新峰placed阶段已实测（physopt/终态待补）

placed自然phase0、752秒、15项query全0，原place DCP/archived源重hash保持；原新48行全部保存，12峰行对应10unique NW区域。全部区域site实际映射到SLR1；各区SLICEL/M site容量2944–3072、occupied同值，表示CLB站点有primitive占用，不意味着LUT/BEL容量100%或固定拥塞等级。primitive54671–56489、attachedsegments235599–323764；重叠窗口不相加，附着segments不作边界crossings。原报告峰Level6与当前测得occupancy为不同量，fixed-window congestion仍UNAVAILABLE。原会话继续physopt加载，完整结果与自然终态待核。
