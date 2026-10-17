# AT012 · 完成pre_place检查点的一次恢复入口

CPU execution=completed、exit0。新增恢复测试13项与重新执行managed隔离6项通过；96项未变诊断测试复用AT011身份，并非本次新执行。候选源码、测试、同版primitive models和write_verilog参考已冻结到source_archive与archived_sources.sha256。

真实AT008完整debug POST在derived v2目录通过最终checker组合hook：gate_issues=[]；7 async、4 AUX、3 HostSplit、14 primitive exports、688 BRAM port clocks、8精确Critical CDC，formal safety OPEN。原始图内export绝对路径仍读取原件；driver先确认图copy SHA相同，再调用完整原parser，未削弱生产准入。v1复制路径保护失败保留在actual_replay.log及首个derived目录，不是EDA失败。

真实339/45综合链、AT007 OPT祖先、AT008超时/无survivors、e58d8970...debug DCP、完整pre_place及68文件终态closure通过。历史opt/debug receipt保留原路径；新AT只执行fresh live guard→place→physopt，禁止伪造本次opt/debug。环境变量不能替代实际恢复与准入。

installation.json记录独占EDA锁及5个live脚本相对AT008 frozen source的before/after，新测试路径此前不存在；不改RTL/算法、时钟目标或原始报告。新的live guard/native DRC尚未执行，必须在AT009实际restore成功后完成。没有physical signoff、route parent或bitstream。

后续按现有授权启动唯一一次AT009；2小时、8CPU/nice5及资源保护不变。若没有新完整物理DCP，不重复place；若获得真实place/physopt DCP，只恢复缺失阶段。
