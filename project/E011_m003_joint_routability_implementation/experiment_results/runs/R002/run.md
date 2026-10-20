# R002 — SM017新工程、综合与原生preplace资格

Execution state: running（实际G4独审中，当前无活动EDA）；verdict: inconclusive。当前R002/AT035实际debug全POST及preplace包已成，最后outer native1仅为产物保存后的重复close_project错误；原始失败保留。

最新实际包SHA94e3f3350af829d7fd61d4e01988e262b1344697801a062d762a8ca295e98e52、DCP SHA3543a85449d4a988f1eee9f1d7259b6e7ba5e8b55c8ab13d61c6f083a1f24af0。447源码归档/451阶段输入、当前debug probe与原pre_place_evidence(create=False)均核；A007已真实派发集中G4，后继R003固定完整物理仅planned。下文初期源版本及构建过程为历史。

前置为R001当前同版G3a/G3b真实通过及A007独立无阻断，不增普通Root/用户批准。原41源manifest62d55ff9通过G3b；工具环境适配后当前42源manifestd1f90456，并获A007 f4419b2a同范围无阻断、G2 4424c426/SM0146d74e85d与production三RTL固定。目标新项目为project/hardware/vivado/project/scalellm_m003_E011_R002_AT002，不使用旧RTL DCP替代新综合。

入口为run_m003_owned.py监督run_m003_stage.py的create、synth和qualify；实际命令、时间、版本、源/IP/XDC/数据身份与原生退出登记各独立AT/job。AT001先正式构建；后继正式新综合产生23个top/OOC和22个实际consumed DCP并逐SHA绑定。新图必须真实核81/13120、34 helper/17 original core/40+40 URAM、C01/25和原80保护、D/Q/CE/S/L/R/reset/clock、实际native范围/资源/宏/级联/RDW配置与预算。

同stage同metric预算基线为A007已核E005原生post_synth报告，header/part/top/tool与基线reviewSHA固定。精确新增锥与module/global report差值分别核验；不拿旧失败route数量当综合预算。随后新INIT、显式opt/debug、实际逐phase CDC探针和原严格reset/CDC/debug/clock/resource/DRC gate，正常成功停于新post-debug preplace包等待既定独立G4技术结论。G4通过后直接新SM018批次固定完整实现，不增加用户批准。

单EDA、CPU0–7/nice5/max8、RSS192GiB/MemAvailable48GiB持续30s/disk30GiB、无墙钟/静默强停；无bitstream/板卡/GPU/PPL/ACC。普通同范围来源/API/工具适配保全AT重试；结构/池/预算/策略变化报Root重冻结。负时序单列且允许合法候选一次诊断route；尚未有综合/物理成功。


AT001于04:17:06Z启动/04:17:12Z自然环境失败：Vivado PYTHONHOME/PYTHONPATH污染系统Python，工程创建前退出1、stop null/survivors空，所有187源字节保全。AT002清理的仅系统子进程环境、三RTL不变，191相关检查0；实际constructor已越过旧故障并写fcd55349输入manifest。原生进程正常推进，绝无固定墙钟/无输出强停。
