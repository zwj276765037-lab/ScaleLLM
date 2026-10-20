# MLP局部数值误差：B00116篇部分结果

[三投影PNG](mlp_projection_precision.png) · [PDF](mlp_projection_precision.pdf) · [完整文档/层级数据](mlp_projection_summary.json) · [图形源数据与身份](source_data.json)

本次仅读取已审核AT002的既有结果，没有模型前向、GPU运行、数值修改或Q001状态操作。统计范围16/1024篇，每篇先在同一投影的32层中取最大relative L2，再跨16个文档报告分位。512个层位置不当作512个独立文档。域配额合池仅作描述，不给置信区间；文档簇独立性假设未验证。

## 已有三投影

| 投影 | 每文档跨32层最大误差P50 | P95 | 全部文档最大值 |
|---|---:|---:|---:|
| 门投影 Gate | 0.006927751% | 0.007071476% | 0.007187663% |
| 上投影 Up | 0.008883741% | 0.009201428% | 0.009296128% |
| 下投影 Down | 0.069634268% | 0.071924787% | 0.072311381% |

每类各16文档/512层位置，三类合计1536层位置；图上每类16灰点，总48灰点。全部文档约束值均finite，无全零匹配、无无穷或不可估。每层原始ratio、误差/信号能量、最大位置与并列数已保留。局部0/0仍为null；若将来全零匹配仅约束max=0并单独标记，零参考非零误差→∞，任何缺失/非法所需位置→不可估，不删去后重算。当前比例由原始能量独立校验，分位与NumPy线性插值一致。

对照是**同输入当前实现 vs 保留中间精度、使用共同出口的参考**，误差=100×L2(当前−参考)/L2(参考)。Gate/Up/Down都已被原Linear observer采集。Down局部对照固定当前SwiGLU产物的同一prepared输入，并不包含Gate/Up差异、SiLU响应、乘法响应和前端量化反馈。因此Down局部误差不能替代完整MLP误差。现有局部张量分母为全部已接受的真实输出坐标，不是逐输出严格合法域误差统计。

## 现存覆盖与需要新增的对照

| 对象 | B001现存证据 | 追加采集的明确对照定义 |
|---|---|---|
| Gate/Up/Down三投影 | 每篇每层同输入current/common-exit局部张量统计；预定raw审计文档还保留Linear见证及独立整数/Fraction核查。 | 当前数据可立即展示；不需补模型运行来得到本表。 |
| SiLU表查找 | 没有独立SiLU输出张量/误差统计。生产查表、地址取整、±16外分支存在于共享路径。 | 保存同一gate_s24、量化LUT身份、地址与SiLU整数输出。以固定量化LUT及既定地址函数作算术参考；该纯查表可能同值，但地址量化/LUT对真实SiLU的逼近损失不能由此称0。若需真实SiLU对照，必须单列函数近似诊断，不能混成额外舍入误差。 |
| 门控逐元素乘法 | 没有独立同输入乘法误差统计；仅有S32 overflow计数（该批未触发）。 | 固定同一SiLU整数值s与up整数码u，exact实值=(s*u)/2^32；current为half-away(s*u/2^16)的F16/S32共同出口。并列current−exact及current−共同出口参考；后者共同路径为0不代表前者为0。 |
| SwiGLU整体（SiLU+门控） | 连续网络两路调用同一生产函数，但各自gate/up可不同；无该节点独立局部影子统计/完整raw见证。CPU节点参考可处理，但B001没有相应真实数组。 | 同一gate/up固定码输入，保留相同量化LUT/地址/外分支，exact=共同SiLU值×up的精确乘积，共同S32出口；另单列两路不同gate/up输入的传播差。不能将两类对照混合。 |
| 完整MLP分支输出 | 未单独hook MLP输出；down_proj局部记录只比较同一prepared输入。32层decoder输出已保存/统计，其中混有attention、MLP和残差。 | 固定同一post-attention RMSNorm输出x，分别完整运行MLP_current(x)与MLP_reference(x)，各自重新计算Gate/Up与Down激活码、共同SiLU/乘法/Host出口；比较最终FP32分支输出。另记录Down S32转Host前后以拆开共同转换损失。 |
| MLP残差 | 没有第二残差前/后独立统计；仅完整decoder层输出与final norm统计。 | 固定同一残差r和同一MLP输入x，比较FP32(r+MLP_current(x))与FP32(r+MLP_reference(x))；另保存自由传播两路各自r、支路输出、相加输出和误差向量内积，不能把残差误差直接归于MLP。 |

参考定义保持合同v3，不把BF16原权重或真实SiLU代入主参考。共享SiLU/乘法/Host函数只能说明两臂采用同一规则，不能证明共同出口/函数近似的数值损失为零。

## 实现位置与审计边界

- [生产SwiGLU地址/表/乘法](/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/software/0_Software/FPtoQ/experiment/v5_fullchain.py:1526)
- [生产MLP Gate/Up→SwiGLU→Down→Host](/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/software/0_Software/FPtoQ/experiment/v5_fullchain.py:1580)
- [observer五类节点映射](/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/software/0_Software/rounding_precision/experiment/numerical_reference/local_observer.py:18)
- [本批trace_layers=None](/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/software/0_Software/rounding_precision/experiment/numerical_model_stream.py:126)
- [独立CPU SwiGLU exact](/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/software/0_Software/rounding_precision/experiment/numerical_reference/exact_reductions.py:136)
- [合同SwiGLU/Host共同出口](/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/software/0_Software/rounding_precision/source/numerical_fidelity_contract_v3.md:53)

生产文件另有record_mlp（1210起），但本批trace_layers=None未启用；它使用原BF16权重F.linear及真实F.silu作为部分参考，与本轮同量化权重/同LUT的额外舍入定义不一致，不能直接补进本表或声称已覆盖。

B001最终generic_v2独审仅1篇预定raw文档（c4:6896）的五类384见证，另16篇的覆盖/公式身份核对；这些不等于全部16篇每个MLP内部输出都被独立重算。SiLU/乘法/SwiGLU/Host缺口须按上表新采集，不能用未采集填0。

## 复现与实际核查

在此目录运行（CPU1、CUDA_VISIBLE_DEVICES为空）：

```bash
python -B summarize_mlp.py --attempt <已审核AT002路径> --output <新的summary.json>
python -B plot_mlp.py --summary <summary.json> --output-dir <新的图目录>
```

实际通过：3×16×32唯一层坐标/文档覆盖；原始能量重算所有ratio；P50/P95/max独立NumPy核对；零/∞/不可估与整数分位不做0×∞；48个点数完整；输入/产物SHA核查。已目视PNG，中文可读、分位标注未碰撞，图脚注明未测范围。新图不修改旧图或任何冻结消费源。
