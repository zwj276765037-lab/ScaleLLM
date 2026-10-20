# M005 真实BF16输入局部回放：GPU0有界阶段

状态：准备；本文件定义资源准入条件，不表示已启动或已获得数据。

用户2026-10-19明确授权实验设计、目录管理和子智能体实验。Root依主合同安排新M005独立采集，不恢复M004、不控制任何外部进程。A016负责采集器/监控和执行；A014独立审核；A015只读协助数值接口。保留并适配其他所有者文件。

## 范围与对照

Llama-3.1-8B-Instruct本地BF16权重；单个固定校准文本、eval/no_grad、eager attention、use_cache=False。采用模型真实BF16前向的Linear输入，通过生产前端得到同一份qa/zp/qw/code/shift，在CPU做当前实现和仅输出舍入的成对局部回放。这是BF16输入轨迹的局部实验，不是V5生产轨迹或全模型任务精度。

先单独32-token pilot，层0/15/31×7 Linear×token [0,31]×4输出通道，最多168输出；真实执行达标后另开128-token尝试，token [0,127]。两个token长度不得混成同一统计。保存文本行SHA、token IDs、实际位置、原始选中BF16激活/权重切片及其SHA、qa/zp/qw、组序与metadata，重算dot。输入不足规定长度则在载模型前失败，不填充或重复文本。权重切片可核查身份不冒称整个16GB checkpoint内容hash。

生产接口：权重quantize_folded_rows/encode_scales；激活fp_to_fixed_raw/prepare_fixed_activation。W8为[-127,127]、W4为[-8,7]，保留各步骤的实际舍入规则。strict_total_shift=True、software_extended=False、down_shift12_candidate=True、down_output_width=32；非Down input24/H27，Down input32/H35。Down来自BF16输入适配，不能声称生产SwiGLU输出已验证。

## 资源准入与停止

仅GPU0 UUID GPU-78b42905-e40c-4ab9-30cf-b8e6f7e8c0f6；GPU1排除。启动前重新检查free>=30GiB且系统MemAvailable>=32GiB，记录所有外部进程；不kill/暂停/调参外部负载。

单自有worker、2 CPU线程、CPU RSS<=8GiB；GPU进程/allocated使用<=24GiB；总显存实时空闲保留>=8GiB，超出时停止本任务自有worker。模型以low_cpu_mem/device_map流式或mmap加载直接到GPU，不能完整复制权重至CPU，不因成本超限放宽预算重试。

pilot墙钟<=300秒，128-token单次也先按300秒执行；监控只管理launch receipt登记的自有进程组，退出保留输入/命令/错误/资源峰值及收据。任务源码及输入在消费期间冻结。原始证据目录<=256MiB。出现非有限值、几何/身份不符或捕获协议错误，留证据并停止该次。外部占用变化导致余量不足时缩采/排队，不改其他任务。

每次实际launch前保存资源快照、命令和身份；技术准备完成且准入条件成立可连续运行，无额外逐项用户审批。达标不等于精度通过；CPU独立同码回放和独审另列。

## 验收边界

所有目标捕获条目有真实来源链、整数码可复核、无静默掉样；不满足合法数值条件的条目单列且保留分母。合法条目的精确误差界违例0；若出现误差/溢出/饱和如实报告，不调容差迎合。输出图使用真实测量标明样本范围。全32层、V5轨迹误差传播、PPL/ACC仍为后续工作。
