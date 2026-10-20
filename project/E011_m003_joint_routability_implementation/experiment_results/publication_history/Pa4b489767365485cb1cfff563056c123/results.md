# E011 当前结果

AT028自然failed/native1终态保持：11:56:29.726006Z，stop=null、survivors空、3RTL不变。17归属PID/start退出、锁空，194原/归档及48源核准。直接失败点为原生INIT后的overlay注册guard，未OPT；DDR信息puts与11个几何嵌套pblock告警不是直接退出位置。

根因实证：原XPR overlay USED_IN_SYNTHESIS0/IMPLEMENTATION1、global/LATE/TCL；生成原生driver创建in-memory GateLvl工程并read_xdc -unmanaged，使原生INIT registry变为1/1、global/LATE。DCP内late.xdc的SRC_FILE_INFO同路径实际为order:LATE/unmanaged:yes；原INIT FILE_TYPE未导出，未凭扩展名推断。持久XPR策略不能直接当临时原生工程文件属性。

AT029于2026-10-19 12:51:42.925170Z（北京20:51:42）实际启动恢复原INIT并完成其剩余验证→新OPT→条件debug/preplace。监督565520/start10390975，Vivado565652/start10391332；199绑定/52实际源和原单锁/保护核准。尚无本次原生终态、完整INIT POST/OPT/G4/物理结果。

AT027已自然native0并冻结/独审接受，结构与预算LUT+111/FF+34/CARRY8+4、BRAM/URAM/DSP不增；它不代替AT029当前阶段。TOP01−2.896ns与G1差22049仍OPEN。


---
Published: 2026-10-19T12:54:01.373475+00:00
Publication: P472ad7be88c240c5b850c1f06502fbc2
