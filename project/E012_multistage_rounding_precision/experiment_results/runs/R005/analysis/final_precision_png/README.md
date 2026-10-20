# 最终单张PNG后处理（待正式完整数据）

本目录A015独占，不是GPU消费源。数值采集、正式group日程、独审和原始结果由Root/A016/A014维护。当前只有实现和CPU小测试；**没有渲染开发或部分数据为最终图**。

## 输入分析manifest

Root在实际group计划及独审身份稳定后提供JSON，schema为`m005_r005_analysis_inputs_v1`：

- `formal_plan`、`formal_stream`：各自`{path,sha256}`，原冻结1024及512/256/256目标。
- `session_analysis_manifest`：常驻会话在global native0/reap且完整1024后才生成的`analysis_manifest.json`身份。聚合器显式核验其global receipt/launch、唯一shared worker、全group receipt/output身份；单独group完成不足以最终接纳。
- `expected_worker_sources`：全部实际消费源码的`{path,sha256}`列表，不只算术核心子集。
- `expected_core_auditor_sha256`、`expected_extension_auditor_sha256`：独审源码身份。
- `groups`：按实际完整group逐项声明`group_id, attempt, doc_ids, core_audit, extension_audit`，后两项为`{path,sha256}`。group数量不预设为25，也不等于独立GPU装配次数。

所有目标doc必须恰好一次、文档簇不能复用。失败/未reap/source_changed/身份不同/不完整coverage均拒绝，不剔除后画成功子集。每group必须有core和extension独审，审计doc集合须与冻结预定raw集合一致。resident group使用实际`execution_receipt.json`，并绑定global receipt/launch；共享base loader身份读取session目录，不伪造每group独立启动或loader。

## 命令

```bash
python -B make_inputs.py --session-analysis <session_S001/analysis_manifest.json> \
  --core-audit-pattern '<审核目录>/{group_id}_core.json' \
  --extension-audit-pattern '<审核目录>/{group_id}_extended.json' \
  --core-auditor-sha <冻结旧core审核源码SHA> \
  --extension-auditor-sha <冻结新扩展审核源码SHA> --output <新的analysis_inputs.json>

CUDA_VISIBLE_DEVICES='' OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  python -B aggregate_final.py --manifest <Root冻结analysis_manifest.json> --output-dir <新的aggregate目录>

CUDA_VISIBLE_DEVICES='' OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  python -B render_final.py --aggregate <aggregate目录/final_aggregate.json> --output-dir <新的PNG目录>
```

聚合逐行读取JSONL并保存文档级最大值、逐层hidden、精确覆盖计数及Top1文档整数分母；不把全量raw或一个大JSONL一次读进内存，不进行模型前向。输出完整aggregate JSON、文档点CSV、P50/P95/P99/max CSV及可读表和文件SHA。PNG renderer只输出PNG、source_data和SHA manifest，**不输出SVG/PDF**。

域内CSV/报告另保留冻结v3§7的95%条件次序统计量区间：只读复用`metric_uncertainty.rank_interval`，family_size=1，IID假设未验证，无跨类别/域联合保证。N256的P99上界可为∞，按真实rank保留，不能用样本max替代。合池不提供CI，主图不绘CI。

## 图形与比较对象

上部13列共享百分比log轴：Attention线性（仅Q/K/V/O）、RoPE、QK、Softmax、PV；MLP Gate/Up/Down；门控乘积出口损失；whole MLP、同residual base相加后；自由传播final hidden与full-vocabulary logits。每列完整1024文档点和P50/P95。P99/max留在CSV/可读表，不挤图。

门控乘积列为当前S32/F16出口对同LUT精确乘积，含共同出口损失；其他局部列为同输入当前对保留中间精度且同出口参考；最后两列为自由传播两轨迹，不统称额外中间舍入误差。SiLU只显示实际语义/异常计数，不画0%总损失。

下部左图两个整数分母：所有词表分数用预定threshold的score_within_threshold_counts/score_pairs准确合池；每篇全部分数用E_d=max_{t,v}|delta logit|是否≤threshold直接数文档。不得用插值分位数反推覆盖率。右图Top1文档等权均值、全token计数合池、整篇所有位置一致，保留N和整数计数。固定相同前缀，不等于任务ACC或自由生成保持。

局部0/0原ratio保持null；全零精确匹配只给最小非负约束0并单列；零参考非零误差为∞；缺失/非法为不可估，任何分位不从成功子集补算。log图对0/∞/不可估单独标示，不往数值加epsilon。固定域配额合池仅描述，不标无条件CI。

CPU小测试`test_analysis.py`：扩展零/∞/不可估、完整位置缺失拒绝、数字层号tie顺序、score与文档覆盖分母不混、Top1宏/微/整篇三比例、拒绝16篇partial渲染，以及拒绝group完成但global失败。日志`/tmp/A015_R005_final_analysis_cpu.log`为初版4tests；session绑定补强后的实际测试另存`qualification/`。这不是实际1024聚合或最终图目视资格；须等待真实完整数据及实际group/audit接口后执行。
