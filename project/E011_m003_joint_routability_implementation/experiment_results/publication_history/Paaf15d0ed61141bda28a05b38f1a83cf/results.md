# E011 当前实测结果

AT027于2026-10-19 09:49:43.849307Z自然completed/native0，stop=null、survivors空、3RTL不变；后核13个精确PID/start均已退出、唯一EDA锁空，194原/归档输入全部匹配。

完整原生snapshot SHA15064a9187b007ca8456f70a40cd24b843c56bd975adcd67e6be6113e1d7fb17，结构资格passed/errors=[]。81个M2 LUT1、34个新增地址FF、两片各40URAM保留；51复位行为按实际来源/函数/初值/极性严格通过。六源最终NAME数量S17/L9/R3/reset807/read1/write3均等于原生计数；独立core时钟源clkout1_buf/O及12602 aliases通过已审checker。

同阶段预算passed/errors=[]：全局LUT+111、FF+34、CARRY8+4，BRAM/URAM/DSP均不增。两次overlay实际应用成功。此资源报告继承自原AT003相同RTL的post_synth，并非本次重综合。

恢复综合包已冻结并核22依赖实际读取：[M003_frozen_synthesis.json](../../../project/E011_m003_joint_routability_implementation/experiment_results/runs/R002/attempts/AT027_reset_semantics_postreport_recovery/M003_frozen_synthesis.json)。原AT003/AT025失败不改写。AT023原生80时钟采集3755ms/完整作业318.178s仍仅为时钟采集效率证据。

AT028于10:53:51.135249Z实际启动，尚无本次INIT/OPT/debug终态、G4或物理结果。TOP01−2.896ns与G1对账差22049仍OPEN；功能/综合资格不代表时序、布通或全局成功。

2026-10-19 11:48:50Z Root一次读取及本次离线日志核实：AT028 link_design成功，elapsed46:23，init.dcp已写，INIT完整POST/OPT尚无通过结论。init_result的completed0为未完成阶段，不用DCP存在代替资格。AT027最终全量独审已接受51复位、全导出、48源、预算与23生产/22消费冻结（A007回执SHA f1bf83f611ecd1e44715f45d614e23c7712423b3ecc7c2dce11e7d939347ae4a）；G4仍等待AT028实际包。

DDR Designutils20-1307来自不变f096a53a第9行信息puts；沿用A007既审限定分类，无时序例外/物理约束被跳过。11条Constraints18-5685对应SLR2内11个CR块先于C01整SLR2块创建的几何嵌套。已保存导出离线反向核AT027：13120FF+81CE正确CR、9492 C01仅SLR2且无额外PBLOCKS，全部通过；该旧阶段基线不代替AT028实际INIT/OPT/debug/restore。


---
Published: 2026-10-19T11:54:56.643197+00:00
Publication: Pfad03ec62bc94c4a93b72a9925df67c1
