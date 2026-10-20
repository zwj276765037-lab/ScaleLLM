# R009 AT003 出口扩精度实现窄审

结论：所审核v2核心/v3资格/v3 runner的关键边界未发现阻断。此结论是实现和有限原语/前4篇记录资格，不是优化效果通过，也不是全36篇完成证明。审核无GPU、无模型前向，未修改消费源/生产源。

## 冻结版本与旧失败边界

- 核心 `r009_lastlayer_kernels_v2.py` SHA `3d36f1cca1cbab72bc4310fd598af30b43ec9f345fb8b7cd93ffaab80768d050`。
- 资格 `r009_qualification_v3.py` SHA `4cc010d9af43314d4abb901f336860b6cc2ec4f6f758ba4cc5644a4f05567da0`。
- runner `r009_run_lastlayer_precision_v3.py` SHA `febef9d125b11e039976184910d4e40723603b6f65b2bfab40d7f629e526b1e2`。
- 三者当前SHA均与AT003 manifest相同。旧v1的legal_shift漏+b问题不从记录抹除；本审核只针对v2。v2第126行使用`delta+24+EXTRA_BITS`，正确还原原total_shift，不把新增小数位误作非法shift。

## 关键算术与边界

候选第120–125行对齐到F24+b，inactive有效shift归0；第257–264行guard/acc范围和wrap mask均+b；第169–180行最终half-away仍右移8，出口F16+b。第226–227行首次分配即int64，第195行存储也是int64，Down S34/S36不会先经int32截断。Guard保留原audit语义，acc仍逐组wrap。

独立reference第300行`k=total-(16+b)`，第350行`common_bits=shift_max-(16+b)`；其q/r和表示精确F16+b码值，第308–313行进位后对负半值使用严格大于、对正半值使用大于等于，符合half-away。Attention b0/2/4的共同分母位数31/29/27，Down为28/26/24；合法total确保右移不超共同位数。G≤448时remainder和及物理quotient均远低int64上限，没有用FP64累加冒充精确。Reference移除内部有限guard/acc，仍保留真正末端sat，不能把其空计数解释为未发生硬件越界。

Context只定位`model.model.layers[31]`的o/down。第401行临时width为24+b/32+b，绕开原S24 packed-negative解释。第416/422行分别在Attention tuple[0]/MLP结果乘一次2^-b，auxiliary概率原样返回；未缩放残差base或已相加的hidden。原分支Host仍FP32，额外低位可能因24有效二进制位和残差加法丢失，参见本目录`boundary_review.md`与`host_precision_probes.json`，不能宣称硬件ABI或Host无限精度。

第427–433行按原实例字典存在性逆序恢复属性/绑定，恢复global grouped函数与marker。对原本继承的方法会删除临时实例覆盖；原已有实例方法则保留原对象。CPU实际context测试覆盖正常/异常退出、candidate/reference、b2/b4，缩放、aux、非目标dispatch均符合预期。

## 配对与运行原件

Runner第148行主要三候选统一对reference4；matched-format及reference漂移单列，candidate4/ref4同一关系复用，无移动reference取有利指标。第155行先进入原OUTPUT_ONLY context再加两个出口overlay，其余reference节点沿用原精确实现。第137、159、181–183行留存并严格比较0..30层prefixhash，候选比baseline、reference2/4比reference0。第156–166行检查属性/函数恢复、32层动态事件和每个扩宽出口/Host缩放恰好一次。原b0与R007 raw及指标进行逐bit/逐字段匹配。

本审核独立读取已完成前4篇的24个arm记录：全部31层prefix覆盖及四组prefix相等，扩宽raw为int64，Host事件为FP32×2^-b、每出口一次，恢复记录为true。该证据不外推为后32篇已核；全36完成、source unchanged、资源/回执及最终效果由工程收口。

## 实际核查与限制

- 自有CPU运行 `A015_check_implementation.py`：2,430个独立Fraction/商余参考公式用例（含120个负半值），0不符；8个实际context用例通过；CUDA未初始化。开始/结束时间与源SHA见`A015_implementation_checks.json`。
- 读取AT003原有CPU资格：2,781整数/Fraction用例、正常/异常恢复通过。读取其GPU资格：Attention/Down/多组混合各b0/2/4共51输出，候选/独立Fraction reference相符，b0 raw/counter与生产相符；含o正码大于旧S24上限、Down大于int32，全部PASS。本独审没有重新启动GPU。
- 上述GPU定向夹具所有overflow/sat计数均0；没有实测非零guard/acc overflow或sat路径，不能声称全部异常边界已由GPU覆盖。有限宽度代码路径与生产差异已静态核查，真实合法物理范围按扩宽合同界安全。
- 不从局部正确性推导整网误差必降，不把开发集重复测量变成独立正式总体证明，也不回避hidden/TV/Top1之间可能的取舍。未对未结束运行下完成判定。
