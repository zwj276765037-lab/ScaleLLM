# M005 全链舍入精度：工程实现与验证方案

A015，2026-10-19。状态：只读工程设计交付；没有实现下述新adapter/kernel，没有启动GPU或模型评测。与A014的`paper_precision_theory.md`互补。本方案不改变现有实验合同或生产源；具体验收预算、正式样本量、GPU配额由Root冻结。

**当前证据只覆盖固定码Linear恢复，不能证明全链精度保持。** 两次真实回放各168个输出来自同一文本、三层、BF16轨迹；不含V5生产轨迹、非Linear节点、32层传播、NLL/PPL或ACC。继续增加这类样本只能增强该局部结论。

权威源：[活动V5](../../FPtoQ/experiment/v5_fullchain.py)、[权重导出器](../../../model/export_scalellm_llama31_artifacts.py)、[独立标量helper](../../../model/fixbit_v2.py)。V5源身份见文末；行号对应当前读到的冻结文件。旧QDQ、`software_extended`和旧04 PPL均不能替代本对照。

## 1. 必须先解决的实际工程缺口

当前`zhouwenjun`环境为Transformers5.3.0、PyTorch2.10.0、Triton3.6.0。BF16捕获成功没有验证`attach_v5_fullchain`可用：

- V5Attention初始化1323–1327直接读取旧Attention的`num_heads/num_key_value_heads/hidden_size`；本地5.3 LlamaAttention只保留config、head_dim等，缺这三个属性。
- 5.3 DecoderLayer要求Attention返回两项；V5Attention1448返回三项。当前参数名也有`past_key_values`与旧`past_key_value`的差别，不能默默吞掉cache。
- 模型版型、attention mask的布尔/加性约定、padding行、position_ids、output tuple、Host residual/RMSNorm/LM head dtype，必须在实验侧兼容wrapper明确。不要改生产V5来迁就库。
- 先做tiny CPU接口测试和真实checkpoint静态形状核查；再按既有资源合同进行有界GPU current路径pilot，核对数值计数和CPU exact spot。上述只是依赖顺序，不增加用户批准门。
- 原HF整批加载超过RSS预算；已验证的逐tensor加载器解决的是BF16基础模型加载，不是完整V5 attachment与reference并存的成本。全链需流式量化/放置、释放原FP权重，禁止整份state_dict或两个8B模型在CPU/GPU常驻。

建议新文件（尚未创建）：`experiment/paper_reference/model_compat.py`负责HF适配；`policy.py`负责唯一数值开关合同；`exact_reductions.py`及独立GPU kernels负责商余参考；`audit.py`负责分层exact审计；`run_paired.py`负责同输入两轨迹。共享接口由Root指定单owner，A016既有文件不在本方案写入范围。

## 2. 活动图的减位宽/量化清单

所有项都应进入版本化节点注册表；“共同边界”仍须有范围、饱和与翻转计数，不等于误差为零。当前M005 exact覆盖只指下表Linear恢复，不能用其他文件存在某个helper当作本轮新验证。

| 节点/源码 | 实际缩减或数值边界 | 主对照处理/开关 | 本轮证据缺口 |
|---|---|---|---|
| checkpoint→W8/W4，exporter246–315 | float32 H32；decoded ScaleCode作除数；weight码half-away；W8[-127,127]/W4[-8,7]，scale编码half-away | 同一量化制品与哈希，禁止两臂重导出；属于共同基础量化 | 已核接口，未证明全权重制品两臂共享 |
| FP入口，V5:202–217 | Host FP32→S24/F16，Down入口S32/F16；half-away、sat | 共同接口；不混入Linear额外舍入 | 有局部前端调用，缺生产轨迹统计 |
| H32，220–253 | 整数蝶形；乘11585/65536后half-away；S27/S35 sat | 固定系数与共同H32出口；该算子本身只有一次归一化出口舍入 | 缺独立exact及全层范围审计 |
| A8 metadata/码，255–299 | min/max、ScaleCode/zp/U8 nearest-even，范围夹取 | 相同算法；局部可固定metadata，freerun必须各臂重算 | 当前真实只是BF16局部前端 |
| Linear，403–450 | 每组向负无穷取整至F24；guard只audit；acc逐组有符号wrap | `linear.group_floor`；关闭时精确累积到共同F16出口；异常单列 | 三profile局部已覆盖；全32层/生产轨迹及GPU差分未覆盖 |
| Linear出口，452–478 | half-away F24→F16，S24或Down S32 sat | 两臂共有出口；保持sat阈值/规则 | 当前局部覆盖，模型范围未覆盖 |
| RoPE，833–861 | 四个乘积各half-away /2^16，再加减、S24 sat | `rope.product_round`；关闭时先精确乘加，再在共有S24/F16出口half-away | 缺fixed-input exact、边界和传播 |
| RoPE系数，1675–1685 | cos/sin按Q16量化，位置0..127 | 同一系数表/哈希；不用精确sin/cos替换 | 系数近似与算术舍入尚未分解 |
| KV12，880–907 | group max_abs→code/shift，q幅度round、±2047；零组规则 | 同一基础KV量化；本轮不移除KV12位宽；metadata翻转计数 | 缺局部exact与动态翻转 |
| QK，910–936 | 精确小整数Group32 dot；乘code与5793；每组floor至F14，再四组相加、clip±16 | `qk.group_floor`；关闭时四组精确和后**floor**一次，保留5793系数与clip | 缺fixed-input exact与GPU整数差分 |
| Softmax指数，940–957 | delta裁[-16,0]；固定exp LUT257项；fraction10位；插值round /1024 | `softmax.interpolation_round`；关闭保留同表/网格的精确有理插值 | 缺精确同近似函数对照；当前torch.softmax trace不匹配 |
| Softmax归一化，957–972 | row_sum；round(2^32/S)至U17 reciprocal；乘积half-up至U16，clamp65535 | `softmax.reciprocal_round`；关闭时精确归一化，U16出口仍共同half-up/clamp | 缺局部exact和mask/padding边界 |
| PV，975–1022 | 每key product floor至F24；跨key和；half-away→S24/F16 | `pv.term_floor`；关闭时精确项和后共有F16出口舍入 | 缺fixed-input exact；活动V5没有S43逐步wrap/audit，不能凭helper推定GPU有限宽行为 |
| SiLU，1451–1461/1526–1534 | Q16 LUT值；地址nearest网格1/256；±16外分支 | 保留同一LUT/地址/分支函数，归为共同函数近似；另做近似消融才可改表或用精确SiLU | 当前误差trace混原始checkpoint权重，不能归因纯舍入 |
| SwiGLU，1535–1541 | exact整数乘积后一次half-away /2^16→S32；越界报错 | 保留共同出口；同输入下不应人为制造与高精度对照差异 | 缺独立边界/生产轨迹审计；输入变化会翻转SiLU地址 |
| Down S32→Host，1616 | int32→FP32再乘2^-16；abs(code)>2^24时FP32可丢低位 | 主对照共有Host转换；单独记录被丢位，不声称转FP32恒精确 | 当前LSB表未覆盖此Host转换误差 |
| Host RMSNorm，1620–1635 | FP32平方/均值/rsqrt/权重乘；没有此V5中的硬件定点RMSNorm | 主对照保持Host FP32与相同顺序；Host FP64仅单独敏感性 | 未有Host高精度审计 |
| residual/最终norm/LM head，1835–1853及HF Decoder | FP32 residual、Host norm/LM head；初始embedding原dtype | 两臂相同dtype、顺序、TF32设置、weights；不混attention-only/MLP-only BF16模式 | 缺同协议完整两臂运行 |

符号扩展/重排/合法范围内的int32打包并不自动产生数值误差。必须检查范围后再cast；不能把int32溢出或mask导致的错误归为正常舍入噪声。

## 3. 真正匹配的“仅输出舍入”对照

此名称指**每个注册算子的共有出口**，并不表示整张网络只在最后logits舍入一次。权重量化、A8/KV12基础码制、量化RoPE系数、HEAD_SCALE=5793、SiLU/exp LUT系数与网格、mask和有意clip完全匹配。保留共有算子出口F16/F14/U16、饱和与Host FP32接口；只切换表中五类额外中间缩减。Softmax的两个开关可分开作单注入，合并作同族注入。

同近似Softmax的连续目标必须先写死：以当前量化LUT作piecewise-linear插值，再归一化。去掉插值/reciprocal有限精度，是去掉同一近似计算图中的算术缩减；不能改用`torch.softmax`或真实exp。SiLU本轮保持原分段查表函数，禁止把表索引量化也移除后继续称“同近似函数”。

局部因果回放固定同一输入码和metadata。完整两轨迹使用同一量化**算法**、同一权重制品和同一文本，各自在自己的激活上重算metadata；输出微变导致q/zp/code/shift、KV12、LUT地址、clip分支变化是传播效应，必须统计。不能同时要求整网动态码相同并声称测到了真实freerun传播。

### 可落实的策略接口草案

```python
@dataclass(frozen=True)
class ArithmeticPolicy:
    linear_group_floor: bool
    rope_product_round: bool
    qk_group_floor: bool
    softmax_interpolation_round: bool
    softmax_reciprocal_round: bool
    pv_term_floor: bool
    # 其余基础量化/函数表/共同出口由独立frozen contract固定，不提供任意隐式覆盖。

def build_model(artifact_manifest, hf_compat_contract, policy, host_policy, device): ...
def evaluate_node(node_id, frozen_inputs, policy, audit_sink): ...
def forward_paired(tokens, current_policy, output_only_policy, comparison_sink): ...
```

实际run manifest还必须保存完整format05字段：strict=True、software_extended=False、Down shift12=True、Down output32、guard45/acc54，以及Attention/Gate/Up各位宽。模式名或format ID不能代替字段。主对照两策略分别六个开关全开/全关；其余配置相同。Host FP64不得偷偷出现在其中一臂。

## 4. 高精度参考不必依赖FP64：精确商余累加

对二进制项`b_g / 2^k_g`，在目标出口整数码域分解`b=q·2^k+r`，`q=floor(b/2^k)`且`0≤r<2^k`；负数也使用这个非负余数。k<0的项左移精确，余数0。令K为非负k的最大值：

`Q=sum(q_g)`；`R=sum(r_g << (K-k_g))`；`Q += R >> K`；`R &= (1<<K)-1`。

于是`Q+R/2^K`精确等于未截断出口码。floor出口直接取Q。half-away出口：Q≥0时加`2R≥2^K`；Q<0时加`2R>2^K`。K=0直接返回整数。此处商余参考与Python任意精度oracle独立实现，并在合法范围内证明int64不溢出；范围外必须报告，不能依赖机器wrap。

| 算子 | 出口整数码域的b与k | 保守int64安全条件 |
|---|---|---|
| Linear | b=dot·act_code·weight_code，k=total_shift−16 | 物理dot界/合法shift下Q和绝对部分和<2^46；G≤448，K≤31，未归一化R<448·2^31<2^40 |
| QK | b=dot_S40·KV_code·5793，k=KV_shift+18 | b在S61；四组，K≤50，R<4·2^50=2^52，Q部分和在S37内；输出floor再clip |
| PV | b=prob_U16·value_S12·KV_code，k=KV_shift | key≤128，K≤32，R<128·2^32=2^39；Q绝对部分和<2^35；输出half-away再sat |
| RoPE | b=x·cos−y·sin或x·sin+y·cos，k=16 | S24输入、系数abs≤65536，乘加abs<2^40；int64直接exact乘加后half-away |
| Softmax | E_num=1024·high−(high−low)·fraction；最终prob码=65536·E_num/sum(E_num) | E_num≤2^26，128key和≤2^33，分子≤2^42；整数除法商余可精确half-up；mask项0 |

Softmax单开关组合也可保持整数表示：插值舍入开启时把rounded_E乘1024放回共同分母；reciprocal开启时`inv=round(2^42/sum(E_num))`，最终prob码为`E_num·inv/2^26`的half-up；关闭时直接用上表的精确归一化。保留U16上限65535，单key产生的65536→65535仍是共同设计clamp。

FP64只在已证范围可以称“整数精确”：A8/W8 Group32 dot绝对值≤1,036,320；QK的小整数dot<2^40；RoPE乘加、SwiGLU整数乘积≤2^46。**QK乘code/5793后的S61原数、跨shift共同分子、任意长链分数不能无条件转FP64称精确。** S54整数域在严格边界内可与53位有效精度相容，但这不证明保留分组低位后的二进制有理和精确；不能以格式宽度或单个dtype代替逐操作证明。

若首个GPU参考采用FP64近似实现而非上面的exact reduction，须另标近似reference；对与exact差异可能改变最终码/阈值的样本fallback精确重算，并报告reference误差。不能把其误差混入被测舍入误差。

Host RMSNorm的rsqrt不是有限二进制有理数。主对照共用原FP32，因此不是本轮extra-round开关；可选CPU spot以精确输入位模式、epsilon位模式和80/120位Decimal或区间sqrt审计FP64敏感性，不能把FP64 rsqrt宣称数学exact。

## 5. 从局部到32层传播的执行次序

1. **算子资格**：每类开关定向覆盖正负ties、负floor、消减/长和、shift端点、近clip/近LUT地址、全mask padding及合法单key。current适配器对活动生产规则0 mismatch；新输出一次路径对任意精度oracle 0 mismatch。非法格式/溢出与有意clip分别计数。
2. **固定输入跨节点审计**：先真实V5 current轨迹的全32层七Linear及Attention/MLP内部节点取样。每层/节点/幅度/shift/距阈值分层；普通随机样本与近ties、近量化/clip/LUT阈值样本共同覆盖。BF16旧输入保留其来源身份，只作补充。
3. **单注入**：以输出一次全链为共同起点，每次在一个指定layer×node启用生产缩减，下游正常重算量化码；32层×六开关=192个位置配置（Softmax两项可另分组），另外做每个节点族在全部层启用的六配置。不要把单点局部误差和当全开实测。
4. **全注入**：六开关在全32层启用，对同一文本比较输出一次基线。记录所有层的residual/Attention/MLP/logits误差及动态翻转；同时直接跑当前实现和输出一次，不从单注入曲线拼接终点。
5. **交互诊断**：只对实测高贡献/阈值翻转节点增加有依据的组合，不默认枚举2^192。可选F24→F28敏感性必须同时扩guard/acc整数范围并固定共有出口，另标候选；只加整数位不能测舍入精度。
6. **模型任务**：独立留出文本/题目、两臂相同hardware_128切块、stride/重置position、tokenizer、mask与计分token集合。先paired ΔNLL/Δlogits，再完整同协议WikiText-2 PPL；ACC用事先冻结且128协议兼容的likelihood任务，逐题paired预测与margin。GSM8K的生成/cache/context不兼容不能直接借M004结果；不自动恢复M004。

单注入可先在定位集测所有192配置的logit/NLL变化，再选择必要子集做昂贵完整任务；主对照两臂完整任务不能只在筛选用文本上报告。δ_NLL/δ_ACC、置信区间、独立单位和多任务规则由正式数据前的协议冻结，不在此编造阈值。不把“未显著”当非劣效。

完整任务不可为通过理论界而删去饱和/困难样本；模型所有计分样本都进入任务分母。strict非法shift或未解释溢出导致运行不完整/格式资格失败，须保留并修复；有意score/softmax clip按共同算法执行并单独统计。

## 6. 可执行成本分级与证据接口

| 级别 | 实际可交付物 | 成本/资源处理 |
|---|---|---|
| A：当前只读设计 | 本文、接口/兼容缺口、精确int64范围 | 已完成，无GPU |
| B：CPU exact资格 | 小型node batches、独立大整数spot、tiny HF接口 | 每次≤5分钟pilot、1线程；本轮未启动新实现 |
| C：GPU单块/短序列 | one layer/32tokens的current-vs-reference双kernel及审计 | 新AT、Root既有GPU资格；测kernel、RSS/显存、吞吐后才估计扩展 |
| D：全32层paired定位 | 32/128tokens、多文本块，流式节点统计；192单注入先小定位集 | 以实测基线时间t为单位；顺序重放成本至少约194次forward外加加载/统计，不声称45秒BF16采集可外推V5 |
| E：正式PPL/ACC | 两主臂完整匹配任务、paired不确定性与异常率 | 总token/题目×实测吞吐规划；保留独立留出，不能在现有300秒采集预算内假设可完成 |

正式规模不能全量Python逐标量JSON或把每层完整tensor回传CPU。GPU内流式累计count、signed sum、squared sum、max、F16/F14/U16码差直方图、异常/阈值翻转计数；按text block先归约，保留统计独立单位。P99可由有界整数直方图精确得到；若用sketch需记录近似规则。原始日志保存每块摘要、稳定seed的分层reservoir及全部最坏/违例反例；样本上限和重复计数策略冻结，避免overflow后悄悄截断证据。

审计对象建议为结构化二进制小tile（NPZ/safetensors）加JSON manifest，而非百万条lane JSON：

```text
run_id, policy_hash, artifacts_hash, source_hashes, hf_contract_hash
trajectory=current|output_only|single_injection, input_ids_hash
layer, node, shape, fractional_bits, reduction_axis, group_order
sample_selector(seed/stratum/indices), integer_inputs + metadata + LUT references
current_code, output_only_code, exact numerator/denominator on audited samples
valid_count/total_count, clip/overflow/illegal_shift, q/code/zp/LUT-index flips
per-block logits/NLL/scoring-mask identity; peak RSS/GPU/time/exit status
```

两臂权重制品只读共享；运行可顺序进行，以tokens与immutable artifacts配对并保留按节点抽取的审计证据。不要求同时常驻两套大模型。首个实现可只审计CPU样本，但正式reference若用GPU exact reduction，也必须抽样反向对照任意精度oracle，特别覆盖负半tie、抵消和距阈值最小样本。

## 7. 当前交付边界

工程上最优先是兼容wrapper资格、精确node reduction与开关合同，随后生产轨迹的分层审计和真正两轨迹传播。当前局部结果是这些阶段的基础，不是完整论文证明。所有建议均为设计，文件存在不代表实现/运行/验收完成；本轮不修改生产或A016文件。

源码身份（本次只读核查）：

- `project/software/0_Software/FPtoQ/experiment/v5_fullchain.py`：SHA256 `58a6bb7c769209925bd3bcd9d1a06414b0a25415a46591f70d8efd62db0b9898`。
- `project/software/model/export_scalellm_llama31_artifacts.py`：SHA256 `689ddf269ff951e437cc3232c5b544b461e4a0b2ff737e21f69e2f93b8f2a300`。
- `project/software/model/fixbit_v2.py`：SHA256 `fb4b34397edc9d14ed3ef4f0b46d60a61b545a52a7a47d15c2eec8ba7b6db271`。
- 本地Transformers5.3 Llama实现：`/home/user/anaconda3/envs/zhouwenjun/lib/python3.10/site-packages/transformers/models/llama/modeling_llama.py`，SHA256 `c44cb7bbd82d6128ab475d801ff3e3aeaca9356f975a1758baa78890fce19e77`。
