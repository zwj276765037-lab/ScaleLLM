# ScaleLLM 六模型五配置扩展数据集评测任务书

版本：2026-09-15  
状态：扩展 PPL 双 GPU 正式运行中  
关系：本任务是已完成六任务 ACC + WikiText-2 PPL 正式矩阵的增量扩展，不替换原结果。

## 1. 纠正目标

现有正式矩阵只有 PIQA、ARC-Easy、ARC-Challenge、BoolQ、HellaSwag、
WinoGrande 六项 ACC 和 WikiText-2 PPL。项目本地实际上还有更多已固定的数据集。
因此问题不是现有任务选择错误，而是结果覆盖数量不足。

每个新增数据集必须覆盖同一组六个 checkpoint 和以下五种配置：

1. Full precision (BF16)
2. A8W8 / FP32 scale
3. A8W4 / FP32 scale
4. A8W4 / FP16 scale
5. A8W4 / ScaleCode

不得使用插值、复制 BF16、理论估算或空白占位冒充 GPU 实测。

## 2. 本地数据集全集及执行边界

### 2.1 已完成 ACC

| 数据集 | Split | 样本数 | 当前状态 |
|---|---|---:|---|
| PIQA | validation | 1,838 | 新正式五配置完成 |
| ARC-Easy | test | 2,376 | 新正式五配置完成 |
| ARC-Challenge | test | 1,172 | 新正式五配置完成 |
| BoolQ | validation | 3,270 | 新正式五配置完成 |
| HellaSwag | validation | 10,042 | 新正式五配置完成 |
| WinoGrande | dev | 1,267 | 新正式五配置完成 |
| OpenBookQA | validation | 500 | gyrot-aligned 论文表五配置已有实测 |
| GSM8K | test first-300 | 300 | 论文表五配置已有实测；不是 full split |

原正式六任务页与论文六任务页并列保留。二者 split、prompt、metric 或样本范围
不同，不允许把两页数值混成同一个所谓统一 Macro ACC。

### 2.2 本轮立即补测的 PPL

| 数据集 | 固定本地范围 | 五配置正式状态 |
|---|---|---|
| WikiText-2 raw-v1 | test/full | 已完成 30/30 model-case |
| PTB legacy text-only | test/full | 双 GPU 运行中 |
| C4-en official fixed subset | validation shard-0 rows [0,10000) | 双 GPU 运行中 |
| LAMBADA OpenAI | test/full，全篇 token PPL | 双 GPU 运行中 |
| IMDB | test/full | 双 GPU 运行中 |
| AG News | test/full | 双 GPU 运行中 |

新增五项统一采用每 checkpoint 原生 tokenizer、`add_special_tokens=False`、
2048-token non-overlap 完整 block、tail-drop、每 block 首 token 不计分，以及
`exp(total_NLL / total_scoring_tokens)`。文档间使用 `separator=none`，并在结果
manifest 中记录原始 token 数、完整 block 数、scoring tokens、tail 和数据 SHA-256。

LAMBADA 在本页定义为全文 token PPL，不是标准末词 accuracy；必须在论文中单独
注明，不能与末词协议混称。

### 2.3 已就绪但属于后续专项

| 数据集 | 类型 | 样本数 | 后续要求 |
|---|---|---:|---|
| GSM8K full | 数学生成 | 1,319 | 固定 prompt、解码参数和答案解析后重跑五配置 |
| MMLU | 57 学科选择题 | 14,042 | 0-shot 与 5-shot 分表；dev 只作 few-shot 示例 |
| MATH-500 | 数学生成 | 500 | 固定数学答案归一化器 |
| IFEval | 指令遵循 | 541 | 使用 pinned 官方 evaluator |
| HumanEval+ | 代码生成 | 164 | 使用 EvalPlus 隔离 sandbox 报告 pass@1 |

这些生成式或代码任务不能直接塞进当前 likelihood ACC runner；在 scorer、prompt、
解码和沙箱规范冻结前，只标记“数据已就绪”，不能产生不可复核的混合分数。

## 3. 双 GPU 任务规模与输出

本轮新增 PPL 工作量：

```text
6 models × 5 configurations × 5 additional PPL datasets
= 30 model-case phases
= 150 new measured PPL cells
```

GPU0、GPU1 各自常驻一个完整 model-case；单个模型只加载一次后顺序评测五个语料。
每完成一个语料立即写独立 JSON，因此中断后只重跑未完成语料。

程序：

- `exp/run_extended_ppl_worker.py`
- `exp/run_extended_ppl_eval.py`

结果目录：

```text
ScaleLLM/0_Software/fix_experiment/results/
  six_model_algorithm_literature_2048/extended_ppl_2048
```

最终 Excel 必须保留：逐模型、逐配置、逐数据集 PPL，BF16 delta，A8W4/FP32
与 ScaleCode 的直接 delta，scoring token 数和结果来源；不得只给跨数据集平均 PPL，
因为不同语料的绝对 PPL 不可直接做无权平均。
