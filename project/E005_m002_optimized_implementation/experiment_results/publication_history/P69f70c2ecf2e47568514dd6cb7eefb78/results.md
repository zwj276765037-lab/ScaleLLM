# E005：功能验证进行中

Attention固定slot首版已真实通过XSim：1265488周期冻结原版对照、1263504 slot独立oracle、192中断/196epoch、4完整双wave图像、13591背压检查。原生/监督exit0，stop_reason=null，无残留；[原始事实与hash](runs/R001/attention_functional_facts.json)、[功能范围](runs/R001/attention_functional_results.md)。该结论仅为受影响input局部功能等价，不是综合网表、扇出、时序或布通通过。

MLP v1在xvlog阶段因TB变量声明顺序自然exit1，未执行功能仿真；已保存原失败，A009仅移动声明并交v2新身份重跑，RTL/刺激/oracle/断言未变。[v2交付](runs/R001/functional_delivery_v2.json)。Attention证据仍适用。

工程报告入口CPU回归156项通过；安装版R002/AT004在目标xcvu9p上下文help明确支持SSI_SpreadSLLs，目标place/physopt/router属性set/get为SSI_SpreadSLLs/Default/Default。此前无part时Advanced Flow help差异已解释，AT002缺impl_1的真实失败保留。A007已独立核Attention及安装版结果，详见[阶段审核](runs/R005/architecture_review.md)。正式新综合及物理尚未开始。


---
Published: 2026-10-16T00:38:42.022095+00:00
Publication: Pcdf47cb1848a4e869e581ba87ae8e9ee
