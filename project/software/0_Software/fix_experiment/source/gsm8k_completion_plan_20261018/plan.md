# fix_experiment：GSM8K 补测实施计划

制定日期：2026-10-18（Asia/Shanghai）。负责人：本独立对话的工程实验角色。

**交付目标：补齐 6 个指定 checkpoint × 5 种配置的 GSM8K 完整 test，共 30 组、每组 1,319 题；验收后填入当前展示表，并重算六任务平均 ACC。** 本轮完成计划和只读准备核查，尚未实现生成入口、加载模型或启动推理。

本计划是独立的软件补测准备，不改变 M003/E009 硬件任务、既有资源归属和验收。当前不分配新的全局 M/SM/E 编号，不将软件准备登记为已启动实验。进入实际执行时再登记独立软件实验，按范围分 R、按具体尝试分 AT。

配套文件：[机器可读计划](plan.json) · [准备核查证据](preparation.json) · [固定 few-shot 抽样清单](fewshot_indices.json)。计划参数为推荐的 v1；经过下述技术核验及 train pilot 后封存为正式运行协议。

## 1. 本次补测的边界与比较对象

主表任务顺序固定为：**PIQA、ARC-Easy、GSM8K、BoolQ、HellaSwag、WinoGrande、Avg.** GSM8K 替换 ARC-Challenge；本计划不补 PPL。已有五项分数来自 `six_model_algorithm_literature_2048`，旧 first-300 GSM8K 不作新表输入。

| Checkpoint，名称必须精确一致 | BF16 | A8W8 FP32 scale | A8W4 FP32 scale | A8W4 FP16 scale | A8W4 ScaleCode |
| --- | --- | --- | --- | --- | --- |
| DeepSeek-R1-Distill-Llama-8B | 待测 | 待测 | 待测 | 待测 | 待测 |
| GLM-4-9B-0414 | 待测 | 待测 | 待测 | 待测 | 待测 |
| Llama-3.1-8B-Instruct | 待测 | 待测 | 待测 | 待测 | 待测 |
| Llama-3.2-3B-Instruct | 待测 | 待测 | 待测 | 待测 | 待测 |
| Qwen2.5-7B-Instruct | 待测 | 待测 | 待测 | 待测 | 待测 |
| Qwen3-8B | 待测 | 待测 | 待测 | 待测 | 待测 |

列对应 `bf16`、`a8w8_fp32`、`a8w4_fp32`、`a8w4_fp16`、`reference_qdq`。每格独立完成 1,319 题，正式规模 **39,570 条生成答案**，不含 smoke、pilot、重复性检查或重试。Llama-3.1 必须使用 Instruct checkpoint。

量化路径沿用现有算法：Hadamard32、Group32、激活 A8、Attention W8；MLP 按配置用 W8/W4；scale 按配置用 FP32、FP16 或 uint8 code + shift；计算 dtype 为 BF16。GLM 的融合 `gate_up_proj` 属于 MLP，`lm_head` 不量化。只复用算法级 QDQ，原生 Attention/RoPE/KV；本次不选择 V5 整数硬件仿真分支。

目标是测量各配置的实际 EM 及相对 BF16 的变化，不预设“必须无损”或某个最低精度作为实验完成条件。

## 2. 已完成的准备核查

以下是准备事实，原始路径、文件哈希、逐模型检查及 GPU 查询错误保存在 `preparation.json`。

| 项目 | 本轮实查 | 尚待执行前验证 |
| --- | --- | --- |
| GSM8K test | 1,319 行、1,319 个唯一问题，全部有唯一 `####` 数字答案 | 正式入口再次核对冻结哈希 |
| GSM8K train | 7,473 行、7,473 个唯一问题，全部有唯一 `####` 数字答案 | train 只用于示例、smoke、pilot |
| train/test 重复 | 原始问题字符串的精确交集为 0 | 该检查不等于语义去重或训练污染检测 |
| 六个模型 | 配置、tokenizer 等历史清单中的非权重文件 SHA-256 均匹配；权重分片存在，大小匹配 | 权重内容尚未重新哈希，不能据此宣称完整 checkpoint 身份已复核 |
| 量化实现 | `mlp4_method_inference.py`、`scalepath4_method_inference.py`、`six_model_matrix.py` 与历史代码哈希一致 | 当前 worker、协议及 runner 等有差异，需要对执行路径作差异审核 |
| Python/包 | Python 3.10.19；lm_eval 0.4.11；Transformers 5.3.0；datasets 4.8.4；accelerate 1.13.0；Triton 3.6.0；torch distribution 2.10.0 | 本轮未 import torch 或验证 CUDA；历史 torch runtime 为 2.10.0+cu128，启动时核对 runtime 与 CUDA 信息 |
| GPU | `nvidia-smi` 退出码 18，`Failed to initialize NVML: Driver/library version mismatch`；内核模块 580.159.03，NVML 库报告 580.178 | GPU 型号、数量、空闲显存和 CUDA 可用性均未确认；不得据旧双 GPU runner 推定当前有两卡可用 |
| EDA 资源 | E009 AT003 启动记录分配 CPU 0–7 | 软件真实启动前重新核对当前资源；本轮未干预该任务 |

数据路径为 `/home/user/EDA-202/zhuowenjun/fpga_llm_project/data/gsm8k_openai_main_raw/`。

| 文件 | SHA-256 |
| --- | --- |
| `test.jsonl` | `a85528f2887da03d6d2329a8bd8e4af761a853c27e9bbe59c92080ae73987be9` |
| `train.jsonl` | `76aa081e0b242a767660dbc738a524d746036ed39686b68ce3ce1ab6d670ac61` |

**本地字段是 `instruction` / `output`，不是 `question` / `answer`。** 入口严格映射 `question = instruction`、`answer = output`，并断言 `system` 和 `input` 为空、source 为 `openai/gsm8k`、config 为 `main`、split 正确。映射失败应中止，不能将空问题/空答案继续送评。数据源为本地导出，本轮未对照远端 revision；正式证据必须保留此来源限制和精确本地哈希。

## 3. 推荐评测协议

协议标识：**`gsm8k_main_5shot_raw_greedy_8k_v1`**。以安装环境中的 lm_eval 0.4.11 `gsm8k`（task metadata version 3.0）为提示和评分依据，显式固定长度、抽样和生成参数。它是 GSM8K 专用协议，不能冒称所有六任务仍使用 `literature_2048`。

选择标准 5-shot，是为了使用任务自身的解题示例和 `####` 最终答案格式，减少为不同模型单独调整提示造成的偏差。最终表注须写明：其余五项为 0-shot likelihood，GSM8K 为 5-shot greedy generation；六任务均值是本项目固定组合的等权指标，不能称为统一 0-shot 成绩或直接对照厂商榜单。

| 要素 | 固定规则 |
| --- | --- |
| 数据范围 | main/test 全部 1,319 行，sample ID 为 `test:0000` 至 `test:1318`；每题仅生成一次 |
| Few-shot | 5 个 train 示例；seed = 20260913；使用已保存的逐题示例 ID 清单，所有模型/配置共享相同原始 prompt |
| Prompt | 示例为 `Question: {question}\nAnswer: {完整 train answer}\n\n`；最后接 `Question: {test question}\nAnswer:`，不接 test answer |
| 抽样语义 | 按 test 原始顺序，每题调用同一个 `Random(20260913).sample(range(7473), 5)`；与独立 train/test 的 harness ContextSampler 语义对齐。分片/恢复直接查清单，不重新从种子起点抽样 |
| Chat/system | 不使用 chat template，不加 system prompt，不使用 fewshot-as-multiturn |
| Thinking | 不加 `/think`、`/no_think` 或强制 `<think>` 前缀；不调用模板 thinking 开关；`think_end_token=None`，不剥离模型自行生成的思考文本。此设置不声称禁用了模型的内生推理 |
| 解码 | greedy；`do_sample=false`、`num_beams=1`、`num_return_sequences=1`、repeats=1；不传 sampling temperature；repetition penalty=1、no-repeat-ngram=0 |
| 长度 | 总窗口 8,192 tokens；`max_gen_toks=4096`；prompt 预算 4,096 tokens；实际 tokenizer 加特殊 token 后审计所有请求，禁止静默左截断 |
| 停止 | harness stop strings：`Question:`、`</s>`、`<\|im_end\|>`，以及 tokenizer EOS 对应字符串；同时记录该 checkpoint 实际 EOS token IDs。不在遇到 `####` 的瞬间停止，以免截去答案 |
| Tokenizer/BOS/PAD | 本地原生 tokenizer；沿用 harness 的原生 BOS 处理，不手工重复添加；无 PAD 时按现有 loader 设为 EOS；保存最终生效 token IDs 和完整配置 |
| 数值/后端 | BF16、eager attention、TF32 关闭；batch=1；原生动态 KV cache，`use_cache=true`，KV 不量化；同模型五配置规则一致 |
| 主指标 | `exact_match,strict-match`，主表显示 `100 × correct / 1319` |
| 辅助指标 | `exact_match,flexible-extract`、invalid 数、长度上限命中数、输出 tokens、吞吐、显存峰值；辅助分数不代替主分数 |

`fewshot_indices.json` 已固定 1,319 组正式示例 ID 与 32 组 train pilot 示例 ID。首题的 train 行号为 `[782, 5096, 7402, 6428, 1554]`（从 0 开始）。正式实现必须与 harness 实际构造的 prompt 做逐字节核验，再保存所有请求及其 SHA-256；目前尚未完成该运行时核验或 tokenizer 长度审计。

### 评分与异常答案规则

- 只对**新增生成的 continuation**做抽取，绝不能把输入中的五个示例答案一起交给评分器。
- strict 使用 `#### (\-?[0-9\.\,]+)`，取**第一个**匹配，遵循 harness 的 `group_select=0`；没有匹配时为 `[invalid]`，得 0。不能自行改成取最后一个或 `boxed` 答案。
- 预测和参考遵循 harness exact-match 规范：依次忽略逗号、`\$`、`(?s).*#### `、结尾 `\.$`，ignore_case=true、ignore_punctuation=false；保留原始答案。使用字符串匹配，不能偷偷引入浮点容差或把 `18.0` 与 `18` 视为同一答案。
- flexible 使用 `(-?[$0-9.,]{2,})|(-?[0-9]+)` 的最后一个匹配，仅用于判断输出格式影响。不得按哪个指标更高来选主分数。
- EOS 后空输出、无法解析的输出均保留在分母内并计错。命中生成上限的输出也按同一规则评分，不自动删题或自动计错；单独记录 `length_capped=true`，即使其严格答案恰好正确也需披露。
- 加载失败、OOM、CUDA 异常属于未完成执行，不是假答案：保存错误，重试缺失题；只有得到 1,319 个有效执行记录，才可标 `full_split=true`。不得将分母改成成功运行的题数。

## 4. 需要补齐的程序与写入范围

唯一实现目录：`/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/software/0_Software/fix_experiment/exp/`。下列新增文件名是实施设计，**本轮尚未创建这些程序**。

| 拟新增文件 | 职责与可核验产物 |
| --- | --- |
| `gsm8k_protocol.py` | 本地字段映射、冻结协议、few-shot 清单、完整 prompt 构造、长度预检和评分规则；输出 request manifest |
| `run_gsm8k_worker.py` | 一个模型/配置的生成任务；复用现有 loader 与量化 attach，保存原始 continuation、token IDs、逐题时间、停止原因、评分和方法摘要 |
| `run_gsm8k_matrix.py` | 单 GPU 串行队列、配置验证、执行资源锁、按身份断点恢复、R/AT 日志及 30 格状态；不能直接使用要求双 GPU 的旧 runner |
| `summarize_gsm8k.py` | 从逐题原始输出重新评分，校验完整性，生成 30 组表、相对 BF16 差值和与历史五任务的合并 CSV |
| `test_gsm8k_protocol.py` | 数据映射、评分边界、prompt 答案隔离、few-shot 可复现、完整性与错误恢复的 CPU 回归 |
| `render_accuracy_table.py` | 从合并 CSV 生成 Markdown/PNG/PDF，固定任务顺序、单位和待测标识，保留当前论文样式 |

`six_model_matrix.py` 是模型结构与五配置的唯一配置来源。四个量化配置均调用 `validate_quantized_summary`，核对逐 op 位宽、替换个数和 payload；预期模块数分别为 DeepSeek 224、GLM 240、Llama-3.1 224、Llama-3.2 196、Qwen2.5 196、Qwen3 252。

现有 `run_eval_worker.load_model()` 默认 `use_cache=false`；已检查 harness 的生成方法会显式 `use_cache=true`。新入口必须记录**实际生效**值，不能沿用旧方法摘要造成矛盾。QDQ 当前仅替换 Linear，原生 Attention/KV 留存，但这只支持“可复用”的设计判断，尚不等于六模型生成与 cache 兼容性验证通过。

优先通过独立 GSM8K 入口复用 loader，避免改变旧任务默认行为。若需要提取共用加载函数，只改当前工作区，运行相关回归；不改旧目录源码、量化数值规则或 format 05。

## 5. 执行顺序与验收关口

这些是实施后的技术依赖，不代表本轮已经执行，不增设普通修复的逐项用户审批。

| 阶段 | 工作及规模 | 验收与阶段交付 |
| --- | --- | --- |
| P0 环境与身份 | 先核对 GPU/CUDA、资源分配；数据哈希；逐个串行重算六 checkpoint 完整身份；审核当前路径与历史代码差异 | GPU 型号/显存/占用可核查，CUDA 小张量运算通过；模型身份与历史一致或有明确差异处置；保留 preflight 原始回执 |
| P1 入口与 CPU 核验 | 实现上节入口、原始输出记录、评分及恢复；全量 1,319 请求逐字节对齐 harness；六 tokenizer 全量长度审计 | 与 harness prompt、strict/flexible 评分逐项一致；无 test answer 泄漏、无截断；配置替换与清单身份检查齐备 |
| P2 生成 smoke | 30 组，每组 train 行 0–3；每题最多 64 新 tokens，共 120 条；目录明确标 smoke | 6 类 checkpoint/5 配置均可生成、记录停止原因、保存并恢复；验证 finite 数值与 attach 摘要。64-token 截断或未出最终答案不作为精度失败 |
| P3 train pilot | 30 组，每组 train 行 0–31，使用正式推荐长度；共 960 条。示例排除该条 train 题，独立于正式 test 抽样 RNG | 汇总长度、invalid、显存峰值、每题耗时与输出 bytes；完成 cache/重复性核验；形成资源和总时长估算、正式协议冻结包 |
| P4 正式全量 | 协议封存后，30 组 × test 1,319 题；batch=1，单 GPU 串行 | 每组输出完整且身份一致；每完成一组发布实际进度和证据；不根据中途 test 成绩修改提示/解析/长度 |
| P5 独立复算与回填 | 重新读取全部 continuation，用独立路径复算两类 EM、stderr/CI、配置差值；与历史五项合并 | 30/30 组验收完成、39,570 题无缺失/重复；CSV/Markdown/PNG/PDF 一致；旧原始 CSV 和 manifest 未被改写 |

建议正式队列先完成 Llama-3.2 的五配置，随后 Llama-3.1、Qwen2.5、Qwen3、GLM、DeepSeek；每个模型按 BF16 → A8W8 FP32 → A8W4 FP32 → A8W4 FP16 → ScaleCode 顺序独立加载。每组从原始 checkpoint 开始，禁止在已替换的模型对象上叠加另一种量化配置。

### 必须覆盖的验证

1. **评分器边界：** 正负数、千分位、小数、结尾句点、空串、缺失 `####`、多个 `####`、`boxed`、思考文本和输出含 stop string；与安装版 `RegexFilter` 和 exact-match 实现对照。`#### 18`/gold18 应为 1，`#### 18.0`/gold18 应为 0，无标记应 strict=0。测试 gold 标记剥离与预测标记剥离的不同位置，不能只测自身实现的副本。
2. **Prompt 隔离：** test gold 的内容变化不能改变 prompt；同 sample ID 的五配置 prompt/token IDs 完全一致；分片起点或恢复顺序改变时依旧使用原 few-shot 清单。六模型 token IDs 可以不同，但问题/示例的原始文本必须相同。
3. **生成与 KV：** 每组使用两条固定 train prompt，比较 cache 开/关的短程生成及固定前缀 next-token logits，记录 max absolute difference。预设 logits 判据 `atol=0.125, rtol=0.01`，前 16 个 greedy tokens 要一致；失败需检查实现或近似数值影响，不宣称量化方法无效，也不混用 cache 策略。检查每个投影的 prefill 多 token 与 decode 单 token 均经过预期 QDQ。
4. **重复性：** 同组两次新进程、同输入、同设备和 seed 的前 32 个 greedy tokens 一致。相同 checkpoint 的 EOS、PAD、generation config 最终生效值保存在 manifest，避免偷偷继承采样、惩罚等默认值。
5. **恢复与完整性：** 用 CPU 模拟中途缺题、重复 ID、截断 JSONL、协议哈希变化、模型身份变化。只恢复完全同一身份下的已持久化完整记录；不同答案的同 ID 冲突必须报错，不能择优取正确答案。
6. **独立复算：** 不信任 worker 已写的 `correct` 字段；从原始 continuation 经安装版 harness 重新计算全部正确性，逐题核对。重点人工抽查每模型 strict/flexible 不一致、invalid、长度上限样本；抽查不改变统一评分规则。

### 长度和格式问题的预先处置

8,192/4,096 是 v1 推荐预算，尚未用精度结果选择。若 CPU 审计发现 prompt 超过 4,096，先修正字段或构造错误；若是合法请求真实超长，统一新建协议版本，保留完整示例，禁止偷偷截断。

train pilot 中，若任一组有 **超过 5%**（32 题中至少 2 题）命中 4,096 输出上限，v1 不作为正式主表协议；统一评估 v2：总窗口 16,384、输出 8,192，并对 30 组重新做同一 train pilot。若 v2 仍明显不足或显存无法承载，记录具体阻塞及新预算方案，再决定正式范围；不无限递增长度、不因某模型得分低而只为它加预算。上述扩展属于尚待资源评估的预案，不能越过已确认的资源额度。

格式不匹配高时先核对 prompt/stop/parser 与 harness；若实现一致，则视为该协议下的模型表现，保留 strict 和 flexible 的差异，不改用更高的指标。正式 test 开跑后如确需变更提示、长度、cache 或评分，另开 R/协议版本，受影响的完整比较矩阵重新测；不能混合不同版本凑齐 30 格。

## 6. 资源、耗时与异常处理

默认 **同时最多 1 个 GPU worker、每 worker 1 张 GPU、2 个 CPU 线程、batch=1**。建议 CPU 8–9，实际使用前核验资源归属，避开已登记给 EDA 的 0–7。使用进程级 GPU 可见范围和锁，保存 GPU UUID、显存、主机和线程设置；实际没有适合的空闲卡时，保留 CPU 准备结果，等待可用资源。不开两卡并发，不将 agent 并发额度当 GPU 配额。

当前首要环境阻塞是 NVML 版本不匹配。下一步先只读定位工具加载的用户态库和内核驱动版本，判断能否通过进程隔离使用匹配库，再验证 NVML 与 CUDA。当前没有驱动修复结果。若修复需要机器重启、驱动替换或影响运行中的 EDA，应协调共享机器维护窗口；本轮不重启机器、不卸载模块、不停止他人的进程。

显存启动门槛由本组 pilot 实测峰值加 **20% 余量**决定；保留模型加载/QDQ 临时权重与 KV cache 的峰值，不能按 W4 文件大小推定 QDQ 显存。输出磁盘预估按 pilot 每题 JSONL/token IDs bytes × 39,570，再计日志和尝试保留量；不得为腾空间清理旧实验。

不预报没有依据的“几小时完成”。每组估算为 `加载及 attach 秒数 + 1319 × pilot 平均每题秒数`，串行求和；同时给出每组耗时分布、p95、长度命中率和估算限制。pilot 仅 32 题，不能视为正式长尾的上界。8,192/4,096 协议下正式生成 token 的理论上限为 162,078,720，实际规模用测量值估计。

正常运行不设置墙钟/静默强停。CUDA 异常、OOM、身份不一致、记录损坏应停止发起该组后续题，保存原始尝试和退出状态；修复后按独立 AT 恢复，不能悄悄改 prompt、降低输出预算或按正确率重试。自然产生的错误答案不触发重采样。每次真实启动、阶段完成、异常与最终结束报告本对话；没有实际持续运行机制时不宣称后台监控。

## 7. 结果放到哪里、更新哪些文件

| 内容 | 位置和处理 |
| --- | --- |
| 本次计划与只读准备证据 | 本目录 `project/software/0_Software/fix_experiment/source/gsm8k_completion_plan_20261018/` |
| 新程序 | 当前工作区 `project/software/0_Software/fix_experiment/exp/` |
| 新补测原始证据 | 当前工作区 `project/software/0_Software/fix_experiment/results/gsm8k_full_completion/` 下独立 R/AT |
| 用户总表入口 | `/home/user/EDA-202/zhuowenjun/ScaleLLM/0_Software/fix_experiment/results/README.md` 及 `accuracy_table.md/.png/.pdf`；验收后更新展示并链接新证据 |
| 历史五项来源 | 旧 `results/six_model_algorithm_literature_2048/six_model_summary.csv` 和每组 merged manifest，只读保留 |

计划的原始证据布局如下；该运行目录尚未创建：

```text
gsm8k_full_completion/<R编号_协议范围>/
  frozen_inputs/                 # 协议、请求、few-shot、数据/模型/代码/环境身份
  smoke/<模型>/<配置>/<AT编号>/
  pilot/<模型>/<配置>/<AT编号>/
  formal/<模型>/<配置>/<AT编号>/
    command.json
    manifest.json                # starting/running/complete/failed，不预填成功
    generation.jsonl             # 逐题原始 continuation + token IDs + 停止信息
    scores.jsonl                 # 两类提取值、gold、正确性
    summary.json
    stdout.log
    stderr.log
  merged/
    gsm8k_summary.csv            # 每模型/配置一行，共30行
    gsm8k_delta.csv              # 相对同模型BF16，单位百分点
    six_task_with_gsm8k.csv      # 新表六项原始精度与宏平均
    validation.json             # 完整性、独立复算、来源身份和合并资格
    source_manifest.json        # 显式选择每格 AT 与逐题原始证据
  experiment_source/summary.md
  experiment_results/summary.md
  experiment_status/summary.md
```

逐题记录至少包含：sample ID/源行号、question hash、prompt hash、示例 ID、输入 token 数、新增 token IDs 与原始文本、评分用文本、EOS/stop/length 结束原因、gold 原文/规范化值、strict/flexible 提取值与正确性、耗时、执行错误和来源 AT。保存完整生成结果与截取 stop 后的评分文本，两者须可相互追溯。

身份键至少覆盖：模型完整指纹、tokenizer/配置、数据哈希、few-shot/request manifest、代码、有效生成参数、评分器、dtype/attention/KV 策略、环境版本。GPU/驱动/主机/命令/起止时间另外记录；更换实际设备或环境时核查复现资格。恢复只接受完全匹配的身份，旧模型名称与样本下标本身不足以授权复用。

每组汇总保留 `n_expected=1319`、执行完成数、正确数、strict/flexible EM、invalid 数、长度上限数、输出长度统计、时间、峰值显存和 full_split 状态。主 EM 可报告 Wilson 95% 区间；它描述该题集作为样本时的二项比例不确定性，不代表跨训练种子方差。配置差值与 BF16 使用相同题号配对计算；如给差值区间，使用固定 seed 的成对 bootstrap，而不把两组题当独立样本。

## 8. 汇总回填的验收标准

历史输入 CSV 的 SHA-256 为 `b2f93da7a0b0cde8e2456dabef9cd460f6128318566cd2fe39437801beb134b9`。正式合并前再次核对历史输入及每组模型/量化身份：仅“同名模型”不够。如果权重或 tokenizer 有实质变化，该组新的 GSM8K 不能直接与旧五项拼接；需找回匹配 checkpoint，或另定五项重测范围，不能默认为同一结果行。

每行平均值使用六项**未舍入的 0–1 分数**：

`Avg (%) = 100 × (PIQA_acc_norm + ARC-Easy_acc_norm + GSM8K_strict_EM + BoolQ_acc + HellaSwag_acc_norm + WinoGrande_acc) / 6`

先平均再保留两位小数；不按任务题数加权、不沿用含 ARC-c 的旧均值，不用五项均值冒充六项。任何一项缺失或组内验收未过，该组 GSM8K/Avg 继续显示 `--`。可以逐组回填已验收的行，同时明确覆盖数；只有 30/30 全部通过才标整批完成。

最终验收同时满足：30 个唯一模型/配置键；每格恰有 test ID 0–1318；同一冻结协议；输入无截断；全部输出可追溯；worker 与独立复算逐题一致；五配置身份符合预期；合并来源匹配；图表值与 CSV 一致。得分高低不是执行验收的替代物。

完成后更新用户总览的补测覆盖数和批次链接，更新 `accuracy_table.md/.png/.pdf` 并加协议表注，发布软件实验三摘要。历史含 ARC-c 的表与原始 CSV/manifest 保留。

## 9. 本轮交付状态与下一入口

| 维度 | 当前状态 |
| --- | --- |
| 计划交付 | 已制定，包括协议推荐、30组矩阵、步骤、验收、资源和输出位置 |
| 实施执行 | `not_started`；未创建生成程序、未加载模型、未运行 GSM8K |
| 精度判断 | `inconclusive`；新增可入表结果仍为 0/30 |
| 适用范围 | 本地 main 全量 test，六 checkpoint、五种算法级配置；不含 PPL/硬件验收 |
| 审核 | 计划由本对话自检；独立运行结果审核尚未发生 |
| 下一入口 | 按 P0/P1 处理 GPU 环境资格、完整 checkpoint 身份、生成入口及 CPU 核验；之后才能开展 smoke/pilot |

计划制定已完成。当前尚不能直接宣称“可以开跑”：GPU/NVML 故障、完整权重身份、生成入口、prompt/tokenizer/评分/恢复和 KV 兼容性仍有明确待办，均已纳入技术步骤。
