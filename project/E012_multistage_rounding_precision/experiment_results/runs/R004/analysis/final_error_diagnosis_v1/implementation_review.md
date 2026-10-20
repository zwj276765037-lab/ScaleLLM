# 最终输出误差：有界只读实现复核 v1

本轮结论：**尚未发现已确认的配对或首末层接线错误；也尚未识别最终1.44%/1.76%误差的因果主因。** 五类局部对照与两条连续路径使用同一套共同出口参考算术，但比较的输入轨迹不同，所以局部<0.1%不能作为整网输出<0.1%的保证。不能把“运行成功、局部见证0 mismatch/0界违例”改写为精度满足用户要求。

范围：只读既有M005 v3、Q001消费源与B00116正式文档证据；CPU1做JSON计数汇总，无GPU、无模型前向、不改变源/计划/数值定义、不干预Q001。报告责任A015。源码行号对应本轮读取版本。

## 1. 局部与整体的口径

- [合同v3](/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/software/0_Software/rounding_precision/source/numerical_fidelity_contract_v3.md:7)固定相同量化权重、Hadamard/A8/KV12、量化LUT、设计clip与共有出口；不是用原BF16权重或真实exp/silu替换参考。
- 局部：[observer节点映射](/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/software/0_Software/rounding_precision/experiment/numerical_reference/local_observer.py:18)对应Linear/RoPE/QK/Softmax/PV；[先current再shadow并返回原current](/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/software/0_Software/rounding_precision/experiment/numerical_reference/local_observer.py:165)保留当前轨迹，只对**同一个调用输入**计算共同出口参考。shadow计数独立。
- 整体：[arithmetic_context](/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/software/0_Software/rounding_precision/experiment/numerical_reference/gpu_reference.py:205)使用与observer相同的五个参考函数、六个开关；仅替换算术节点，不替换权重、量化器、LUT或Host操作。[两臂顺序执行](/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/software/0_Software/rounding_precision/experiment/numerical_model_stream.py:218)对同一encoded输入先current再reference，use_cache=False，非teacher-forced逐层重置。两路各自由自身隐藏状态重新量化。
- [动态trace](/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/software/0_Software/rounding_precision/experiment/numerical_model_stream.py:159)只包装原prepare_fixed_activation/_kv12_quantize并返回原结果，按(layer,function,ordinal)配对；[逐层输出配对](/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/software/0_Software/rounding_precision/experiment/numerical_model_stream.py:138)按固定layer hook保存current再匹配reference。每文档应有32hidden、384local、每臂192dynamic，已有覆盖/独审核验。
- [共有模型和权重缓冲身份检查](/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/software/0_Software/rounding_precision/experiment/numerical_model_stream.py:241)每臂结束检查共享buffer的对象/shape/dtype/storage/version；这是变动检测，不单独等于字节哈希。既有消费身份/见证另提供实际量化权重字节核对。

因此“局部”和“整体”在**节点算术定义与相对L2公式上相容**，但前者是同输入局部误差，后者包含输入误差反馈与后续算子响应，不可混成同一误差上界。整体参考仍包含基础量化和共同出口损失，不是整个网络的无限精度oracle。SwiGLU/Host独立全量原始见证仍缺，不能宣称所有软件算子精度均被审计覆盖。

## 2. 首层、末层、残差、Down与Host

- 实际HF [decoder顺序](/home/user/anaconda3/envs/zhouwenjun/lib/python3.10/site-packages/transformers/models/llama/modeling_llama.py:317)统一执行 input RMSNorm → attention → 第一次残差加法 → post-attention RMSNorm → MLP → 第二次残差加法。[32层循环与最终norm](/home/user/anaconda3/envs/zhouwenjun/lib/python3.10/site-packages/transformers/models/llama/modeling_llama.py:421)所有层调用同一实现；final norm位于32层循环之后。读到的实现没有layer0/layer31专属算术或残差分支。
- [attention路径](/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/software/0_Software/FPtoQ/experiment/v5_fullchain.py:1366)共享prepared用于Q/K/V，RoPE后重排，分别量化K/V，再QK/Softmax/PV，经o_proj输出，[attention出口](/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/software/0_Software/FPtoQ/experiment/v5_fullchain.py:1441)转FP32/Q16。最后一层仍相同路径。
- [MLP路径](/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/software/0_Software/FPtoQ/experiment/v5_fullchain.py:1580)gate/up共享prepared，采用共同SiLU LUT与S32 SwiGLU乘积，Down对product直接prepare_raw，输出转FP32/Q16（1616）。未发现把Down S32误作S24截断或再次按S24符号扩展的接线。
- format05由[compat冻结参数](/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/software/0_Software/rounding_precision/experiment/numerical_reference/model_compat.py:106)强制strict_total_shift=True、software_extended=False、down_output_width=32、down_shift12_candidate=True。[Down位宽](/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/software/0_Software/FPtoQ/experiment/v5_fullchain.py:764)Down为S54累加/S45 guard；[出口与S24符号规范化](/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/software/0_Software/FPtoQ/experiment/v5_fullchain.py:783)output_min/max来自output_width，只有width24进入payload符号规范化，S32不进入该分支。
- [Host RMSNorm](/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/software/0_Software/FPtoQ/experiment/v5_fullchain.py:1620)两路共同用FP32 weight/input、均方/rsqrt；[attach统一替换](/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/software/0_Software/FPtoQ/experiment/v5_fullchain.py:1842)包括每层两个norm和最后norm。两路输入不同，故共同函数不意味着输出相等。FP32残差加法也可能缩放、抵消或改变误差方向，误差不要求逐层单调。
- S24整数转FP32精确；S32整数转FP32可能丢低位，两路都保留该共同转换。理论S32转换绝对误差≤64·2^-16（约0.0009765625实值）；这不是整网误差界，也不能仅靠该数值排除转换与后续阈值的交互。当前没有证据将1.44%归给Host转换。

主控/A016已从实际B001数据核得：L30→L31 P95 1.07342%→1.76784%，对应RMSE P50约0.01066→0.01534、signal RMS P50约1.1073→1.1616；finalnorm P50 1.44054%，L31 P50 1.30899%。这支持优先定位**最后decoder内部**，不支持把主要跳点简单归因最后norm或近零分母。此数值分析由A016负责，本报告不另作重复统计。第一层高、第二层下降也不自动指示bug：残差/归一化与后续响应可改变信号和误差；尚需分段实测验证。

## 3. 已确认的floor方向与未确认的放大机制

[Linear当前](/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/software/0_Software/FPtoQ/experiment/v5_fullchain.py:403)先逐组raw算术右移到F24，随后逐步累加/wrap（448–450），最终half-away到F16并sat（452–457）。无overflow/sat的合法域，逐组floor舍弃的余数非负，故**出口前current−精确和非正**；共同half-away为单调函数，所以同输入current−reference_code也非正。[Linear参考](/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/software/0_Software/rounding_precision/experiment/numerical_reference/gpu_reference.py:49)保留所有组商余，归并后才出口舍入。

[QK当前](/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/software/0_Software/FPtoQ/experiment/v5_fullchain.py:932)四组各floor后求和；[QK参考](/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/software/0_Software/rounding_precision/experiment/numerical_reference/gpu_reference.py:147)先精确归并余数再一次floor，同clip。[PV当前](/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/software/0_Software/FPtoQ/experiment/v5_fullchain.py:1004)每key floor到F24，再总和/出口舍入；[PV参考](/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/software/0_Software/rounding_precision/experiment/numerical_reference/gpu_reference.py:195)保留商余后共同出口。两类也有合法域的非正局部差。RoPE乘积分别舍入、Softmax插值/reciprocal误差没有相同单向结论。

**不能由此推断最终隐藏向量负偏差或主导贡献。** 下游权重正负混合，残差、RMSNorm和注意力耦合会旋转/抵消/放大局部误差；floor的符号事实只在固定输入、规定合法域内成立。

动态量化是候选放大机制：[激活前端](/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/software/0_Software/FPtoQ/experiment/v5_fullchain.py:202)FP32→定点half-away/sat；Hadamard整数归一化后用每组min/max确定scale_shift/code/zp与U8值（255–285）；[KV12前端](/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/software/0_Software/FPtoQ/experiment/v5_fullchain.py:880)按组max_abs确定code/shift和S12值；微小输入变化可能跨越离散阈值。QK设计clip、Softmax rowmax/LUT索引（gpu_reference155–180）及SwiGLU LUT地址也是共同但数据依赖的路径。**现有动态码变化只是相关证据，未通过固定码反事实或单开关干预，不能称为主因。**

本轮仅汇总既有16份current/reference audit JSON：两臂所有有记录的saturation/overflow/format-error项合计均0；qk_score_clip current=255962、reference=255994。QK clip属于保留的设计函数，非格式异常。这可排除这些计数器已捕获的大量饱和/overflow作为直接解释，不能证明不存在未观测Host舍入或阈值敏感性，也不能由clip计数差确定贡献大小。

## 4. 实现证据的强度与剩余问题

[B001 generic_v2独审](/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/E012_multistage_rounding_precision/experiment_results/runs/R004/attempts/AT002_formal_batch_b001_numerical/independent_audit/generic_v2.json:1318)：16篇公式核对，1篇预定raw审计（c4:6896）、32原始hidden张量、384见证文件；72064展开输出，其中38376理论适用、33688排除（含Softmax结构mask）。独立Python integer/Fraction复算 code_mismatches=0，适用域raw_theory_violations=0。局部最大码差Linear1/RoPE1/QK3/Softmax6/PV1符合已定义参考。这降低了五节点局部算术/布局配对错误的嫌疑，**不构成所有文档所有中间张量的独立整网证明**。

仍未排除：L31 attention与MLP支路各自的传播增益、两次残差的误差向量相关性、动态量化/LUT/clip阈值的因果贡献、共同Down-S32→Host与SwiGLU的完整原始精度损失、局部方向偏差在全网中的实际贡献。未发现确证实现错误不是证明实现绝无错误。

## 5. 最小可区分的后续干预（本轮不执行）

1. **先定位L31内部，保持一切冻结定义。** 对预定同一文档分别保存L31入口、inputnorm、attention/o_proj输出、第一残差、postnorm、gate/up、SwiGLU S32、Down S32、Host MLP输出、第二残差及finalnorm。两臂均保存。每位置报告信号/误差能量与signed bias；残差处保留进入支路和残差误差的内积，区分新误差与已有误差同向叠加。
2. **同输入整层2×2因果回放。** 对已保存的current入口和reference入口，各跑一次current算术和OUTPUT_ONLY算术，共4个L31结果；比较F_current(x_current)−F_ref(x_current)、F_current(x_ref)−F_ref(x_ref)与入口轨迹变化效应。由此区分该层本地产生误差和对上游误差的响应。层内量化仍按各入口正常重算，不能称固定码整网结果。
3. **再按六开关单独干预。** 同一保存入口，在current基线逐一只关闭Linear floor、RoPE乘积舍入、QK组floor、Softmax插值、Softmax reciprocal、PV项floor，另有全关闭端点；优先分attention和MLP的Linear调用位置做限定。单开关结果不能相加当全关闭结果，需报告交互。先最后一层，再按证据扩到首层或其他层，不先重跑1024整网。
4. **仅在上述表明阈值响应显著时加固定码诊断。** 对同输入整层干预，额外记录/对照冻结当前轨迹的A8/KV12元数据、LUT索引与clip掩码，明确此为局部反事实诊断，已不等同自由传播。若只比较“码不同”数量而无输出反事实，仍不能归因。
5. floor偏差若需独立验证，可在单层/单投影将该项改为最近舍入而保留同出口，作为额外诊断臂；它改变当前生产数值定义，须新实验身份，不能冒充既有OUTPUT_ONLY合同或热改Q001。

当前用户可据实获知：约1.44%/1.76%是参考定义下真实观测到的整体隐藏输出数值差，局部误差小并未阻止自由传播增大；现有证据不足以接受“精度保持”，也不足以确定具体主因。下一步应定位最后层支路并做小范围因果干预，而非先扩大同类统计量。

## 读取身份

- `/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/software/0_Software/FPtoQ/experiment/v5_fullchain.py` SHA256 `58a6bb7c769209925bd3bcd9d1a06414b0a25415a46591f70d8efd62db0b9898`
- `/home/user/anaconda3/envs/zhouwenjun/lib/python3.10/site-packages/transformers/models/llama/modeling_llama.py` SHA256 `c44cb7bbd82d6128ab475d801ff3e3aeaca9356f975a1758baa78890fce19e77`
- `/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/software/0_Software/rounding_precision/experiment/numerical_model_stream.py` SHA256 `87d8763defbd215c377efd1a0caf81d289ae274ba6381aa10f096177aea20519`
- `/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/software/0_Software/rounding_precision/experiment/numerical_reference/model_compat.py` SHA256 `53ef45e269b997bad32d09003bac53a7ccfa9ae006d9e1eecd95e13cb0f23dc0`
- `/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/software/0_Software/rounding_precision/experiment/numerical_reference/gpu_reference.py` SHA256 `a8f4309cb07ec84687903693888602c1fd09fa876d477dcd4c7f488ce4358837`
- `/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/software/0_Software/rounding_precision/experiment/numerical_reference/local_observer.py` SHA256 `b3b2340da40a6ec5c71a50f2e2b218827ebe7e66fa50f2afa517a9f1cfa4a0a8`
- `/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/software/0_Software/rounding_precision/source/numerical_fidelity_contract_v3.md` SHA256 `38ece829fe3673130b64edd64aadfb48137c185a8d46a385e5bbf78238251420`
- `/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/E012_multistage_rounding_precision/experiment_results/runs/R004/attempts/AT002_formal_batch_b001_numerical/independent_audit/generic_v2.json` SHA256 `d012c948638f7d69c138a06050362a07af0130b57db1b08f8bed713221090419`
