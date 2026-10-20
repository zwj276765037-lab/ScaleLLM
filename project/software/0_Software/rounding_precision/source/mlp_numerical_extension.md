# MLP数值扩展观察器接口 v1

新增模块：`experiment/mlp_numerical_extension.py`。生产V5与R004冻结源保持不变。此模块不在import时执行CUDA操作；真实GPU资格由Root统一启动。

```python
from mlp_numerical_extension import (
    MLPNumericalObserver, expected_coordinates, row_coordinate,
)

# 必须在旧dynamic trace/local observer安装前构造，保存原始frontend引用。
observer = MLPNumericalObserver(
    v5, model, sink=save_row, audit_doc_ids=predeclared_audit_docs,
    samples_per_layer=16,
)
for arm in ('current', 'reference'):
    observer.set_context(doc_id=doc_id, arm=arm)
    # current: 旧local observer外层；reference: arithmetic_context外层。
    with observer.context():
        result = run_selected_arm()
rows = observer.flush(doc_id)
assert {row_coordinate(row) for row in rows} == expected_coordinates()
```

同一个observer可在两臂间重新进入context，保留当前臂小量GPU输出用于自由传播配对；flush必须在两条完整路径结束后调用。默认完整32层，416唯一行/文档。tuple坐标为`(layer, op, arm)`；comparison为各op固定定义，不允许临时改名。

| arm | 每层op | 总行数 |
|---|---|---:|
| current、reference各自 | silu_lookup、gating_multiply_total、gating_multiply_extra、down_host_total | 256 |
| current | whole_mlp_local、mlp_fixed_residual_local | 64 |
| paired | mlp_branch_propagation、mlp_residual_input_propagation、mlp_residual_sum_propagation | 96 |

行字段为`doc_id, layer, node='mlp_extension', op, arm, comparison, trajectory, metrics, metadata, qualifiers`。metrics沿用能量、相对L2百分比、有符号和、最大绝对误差、RMS与计数，不执行bootstrap或batch置信区间。异常输出不能被当作成功有限样本；非有限计数大于0时能量/ratio为null。分母是全部已接受真实坐标，不授予逐输出严格域资格。

`silu_lookup`从真实`_swiglu_s32`输入、同一生产表和地址/外分支规则重建SiLU中间值；不是独立截获的生产内部张量。它核对同一函数语义，并保留±16外分支、地址网格偏移、packed S24规范化与实际乘积的一致性。不能把此行0误差画成解析SiLU总数值损失为0。

门控乘法total的精确参考实值为`(silu_integer*up_integer)/2^32`。actual为生产S32码乘`2^-16`。extra对照为相同精确乘积经过独立整数half-away共同出口；extra=0不代表total=0。S32 overflow按生产拒绝，没有sat替代；无overflow条件下total绝对误差不超过`2^-17`。Down Host行另测实际FP32结果对转换前精确整数实值的误差；Gate/Up在该生产MLP中直接传整数给SwiGLU，没有额外真实Host出口。

whole_mlp_local固定同一真实MLP入口。参考分支直接调用构造时捕获的原FP→定点与激活frontend、独立exact Linear、同生产SwiGLU和Host出口，各阶段按自身输入重新算动态码。它不调用全局被包装的production forward/project_prepared，所以不重复进入旧local/dynamic trace，也不用主audit。fixed residual另固定同一post-attention residual base，在相加后比较。paired三行则用两条自由传播路径自己的base/branch/sum，不能冒充同输入局部干预。

额外计算约为当前臂每层再运行一个参考MLP分支，不是再运行完整模型；真实GPU耗时仍须pilot测定。两臂配对保留最多32层base/branch/sum，128token×4096 FP32时约192MiB；不保存这些大张量为证据。

只有预定审计文档保留每层每arm默认16个边界+SHA256固定输出点，不按误差选点。SiLU样本含原gate/up payload、规范化S24、地址、同表SiLU值、actual product、精确乘积分子十进制字符串及分母bits=32。每层完整8193项小LUT只在current行保存一次，reference引用同doc/layer/current与同hash。Host样本含Down原整数与实际FP32结果，可独立重算。完整分支/残差小样本只支持输出配对公式核查，不具备整个MLP完整输入/权重依赖，不能声称独立重执行整个分支。所有新增metadata总量对每审计文档硬限8MiB。

CPU资格：`tests/test_mlp_numerical_extension.py` 6 tests PASS，unittest报告0.261s；原执行日志与manifest保全在`R005/qualification/mlp_cpu/`，没有为归档重跑。采用真实V5 frontend/SwiGLU/Host与测试专用CPU integer/Fraction Linear adapter，验证开关两臂输出、完整audit、旧local记录、动态frontend事件数量、原输入/权重不变，负half-away边界、S32 Host非零丢位、异常context恢复。此资格不等于GPU Linear或完整32层模型资格。
