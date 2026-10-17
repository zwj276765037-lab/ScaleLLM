# E004 R003：主控整合方案独立审核

execution_state: completed
review: 最终有界独立审核已完成，未发现阻碍本轮分析交付的实质问题；不代表用户批准实施或结果验收。下文保留初稿修订记录，最终版本与结论见末节。

审核对象：[optimization_plan.md](../../optimization_plan.md)，首次读取分析中版本（2026-10-15 23:28 UTC附近，非精确版本冻结）。

## 已发出的精确修订意见

1. C1的“SLICEM LUT只能用于存储/移位”含义不准确。SLICEM同样可以做普通logic，正确因果是SRL受SLICEM位置限制；用FF替代可解除这组history的该种位置需求，是否释放有用局部通道须实测。10752/15360只为实际源参数下的预估上界，不能当已综合节省。
2. SLL每列Estimated Demand在E003来源是route Phase3，不能当place/physopt已有输出。place比较真实cross nets/loads/SLL Used，route初始化后才比较同口径estimated demand；二者均不构成保证布通的阈值。
3. C1“2拍/1拍历史”应写2次/1次accepted inputs，避免stall时误做每周期shift。其独立CE/INIT/clear要求主控初稿已正确保留。

其余初审结论：原终态/口径、不外推Attention样本、保留frontend快照、singlebank中间可见性、失败产物保留与自然终态要求均合适。主控须在R001结果后明确最小组合及有条件后备，而非默认把所有候选一起实施。

## 最终复核待项

- 对首选每项绑定实际模块/控制net、源码行和物理统计；未取得字段明确缺口。
- primary bundle区分无周期变化与协议重构，不把新增pipeline、共享loader或singlebank算入纯同周期结构重写。
- 保留独立事务oracle、原module测试含义和具体回归入口；明确目标映射未落实或局部压力恶化时的工程处置。
- 首选directive有精确2025.2官方依据；安装版native help本轮未取得，明确列下一阶段无DCP轻量核查，不把网页当安装成功回执。不做无界扫参，不宣称成功概率。
- execution/verdict/applicability/review分开；physopt查询完成不等于优化已实现或方法已supported。

## 新增关键口径修正（已实发主控）

全设计LUT as Shift Register9047、SRL16E primitive10993不一致，故10752源SRL不能按1:1预测释放10752物理LUT。原0.91pp LUT下降估算已撤回；source facts保留更正及历史错误假设，不再作为候选收益。最终计划必须使用R001精确repack LUT/BEL占位，15360仅候选FF状态位，候选综合网表尚未生成。

C2 input双wave为24×2=48输出CE边界，context16×4=64，合计112。该数是可定位的标量decoder边界数，不是112 LUT净增量或资源上界；index+qual输入数可能超过单LUT容量，实际级数/复用待综合。A008已修正原88混合口径。

## MLP同拍output CE具体化已交付

R003方案§6已给出精确源行和资格：两个repacker193/215/236–238行等价`rst_n && !clear && input_fire && produces_output_c`；16row各512b（Down）或384b（Gate），32个标量identity LUT1仅保留控制边界，metadata等原逻辑保持，不加拍、不改reset/clear含义、不保护数据bank。目标fanout从大trunk分成16副本及实际其余负载，实际净资源和局部性仍需测量。S24 history转FF可能增加CE端点，应与S32-only分支区分。

基线中frontend已经使用类似local CE且失败样本#9仍含input_fire_local_21（log626），这是“局部控制不是充分布通条件”的明确限制。建议不能称此pattern已由本项目证明可布通；它只证明可实现同周期控制分组，新的实际收益需新netlist/place/route。

## 首选组合闭合后的补充审核

当前整合版已采纳两项同周期RTL：input双wave固定24×256bit目的写（48个资格边界）与MLP32个row output CE。Input原生CS56不支持宣称完全缺少local CE；十根index6170+负载也没有REF_NAME分类。必须保留当前区分：固定slice使data直连、避免索引广泛进入数据选择，再核查local CE及原控制剩余负载；不把所有负载称为CE或把源generate写法当综合网表机制已落实。

Gate/Down精确scope当前SRL物理槽2304/3072，合计5376，已由小原报告逐行核查。3072可以界定S32-only影响范围，不能推演净LUT/CLB回收；S24的双深FF代价和额外CE终端风险保持。Source10752是原语实例数，15360是候选FF状态位，均不是实测资源节省。

A007选SSI_SpreadSLLs为单一新placement参数，physopt/router保留默认；SSI_SpreadLogic_high有条件后备。实际读取官方UG904 2025.2两页及所述范围，见architecture_plan §11；native help缺口不阻塞分析收尾，也不被当作安装验证通过。2296个Attention DSP超单SLR2280的容量反证、后者由原生Used/Util%唯一整数反演的方法已保存target_physical_evidence.json。

Postprocess保留双bank、固定48b目的写可列在singlebank之前；原整bank写后RoPE覆盖的同拍优先级必须保留，256个写边界不是净LUT计数。singlebank、共享loader、窄frontend、reset移除和pipeline均继续有条件后备，不混入首轮。最终冻结版SHA、R001最后target/packing/terminal和整体review结论将在末节追加。

## 最终冻结版审核

对象：`experiment_results/optimization_plan.md`，27297 bytes，SHA256 `9b666f60371b07f67284b0ae402fda28ee3e1ae30db8bac243bd03064a7567f3`。实际核对时间、原始小文件身份与复算结果见[final_review_evidence.json](final_review_evidence.json)。此审核绑定该版本，后续实质修订需按变更范围更新审核，不能把书面审核当作用户决定。

**结论：本轮分析交付无待修实质问题。** 两个首选RTL改法、单一SSI_SpreadSLLs placement和失败取证修复有具体模块/信号/原生基线、机制、代价及可证伪检查。首轮保留reset、快照、周期与数值规则；现有S32测试MATRICES2与生产1的差异、S24自身覆盖、input全slot中断及新epoch缺口均已纳入。失败取证逐项catch后重抛原route错误，失败产物不得进入成功父链；该设计未安装，注入验证仍待实施。

R001终态独立核查：status记录native/监督0且stop_reason=null；48条原回执中35code0、13help失败；6项小输入哈希与绑定一致，前后DCP记录SHA一致（未重读DCP），5个原PID/start与supervisor均已消失。52目标含全部27原样本；10根index计数与SLR2分布、4个MLP控制精确跨0/1分布、10个INT样本全SLR2均由原TSV复算。原报告身份与此前A007保存的9项小原证据一致。

自建packing LUT/FF槽全0已明确INVALID，没有被用作根因/收益证据；原生scope资源仍有效。native help未取得、负载类型及SLR内包络缺失、没有失败route全图均明确写入最终计划。官方2025.2方法足以支持提出候选，安装版无DCP轻量接口检查列下一阶段，不默默替换策略。

判断范围：execution=completed；候选优化verdict=inconclusive/NOT_RUN；applicability=当前冻结RTL和成功physopt父点；review=A007分析评审完成、主控整合独立记录、用户尚未验收下一轮结果。没有布通保证，没有把局部功能、资源、DRC0或阶段计数代替最终合法route；时序、reset/CDC安全和板级资格继续独立。
