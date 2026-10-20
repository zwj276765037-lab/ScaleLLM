# R003：GPU0 与静态权重身份完整性

主控技术决定：[GPU0 恢复决定](../../../../../E010_gsm8k_six_model_completion/gpu0_integrity_recovery_decision_20261018.md)。此目录只定义新版本；GPU 启动以主控真实回执为准。

R001/R002 的失败、诊断与已通过组保持原证据。AT008–AT010及 A010 独立审核显示 GPU1 原加载参数的已保存值不同于冻结 checkpoint、推理前快照仍发生变化，而 GPU0 同脚本单目标生命周期通过。因此暂不向 GPU1 分配任务；这不构成 GPU 硬件故障判断。

新 R003 全 30 配置统一 GPU0 UUID `78b42905-e40c-4ab9-30cf-b8e6f7e8c0f6`、CPU16–17、一个 worker。原最多两卡预算减少为一卡，其他资源保护不变。全部 smoke/pilot 重新执行；不复用旧六组 smoke 或旧双卡时延估计。失败/未完成 AT 不导入部分生成行，保留旧文件并用新 AT 重做该组；同 R 完整 AT 仍须通过全部身份/数值/完整性门才能复用。

原六模型×五配置、1319 test、训练提示、请求字节、seed、checkpoint、QDQ 算法与 dtype、greedy 生成、stop、评分均保持。`protocol.verification_contract_id` 仍为 `native_cache_call_parity_v2`，原 logits/KV/破坏负例、同设备跨进程重复和 pilot 预算门不放宽；原 cache-on/off 容差诊断及其真实 False 仍保留。

新增独立 `protocol.integrity_contract_id=checkpoint_static_content_v1`：从可信 checkpoint 到 CPU 原生加载、再到 GPU 复制逐 tensor exact；QDQ 保持原 GPU、完整 shape 和浮点算法，由可信输入附加、同 backend 独立重建建立有效静态 buffer 基线。全部参数、所有 buffers（包括 nonpersistent QDQ）和全局 Hadamard cache 均纳入完整清单。每个完整推理单元前后、阶段末检查内容与 storage 身份；不强制 CPU/GPU QDQ 数学输出逐字节一致。

worker 的 identity 绑定完整性合同；manifest 和 summary 绑定 `integrity.json` SHA 与基线 root。该 JSON 包含完整 checkpoint/effective 清单、逐阶段覆盖和守恒检查，并绑定 `integrity_checks.jsonl` 哈希及逐行内容。共享 validator 核每条请求的前后检查与最后 `stage_complete`；matrix 完成复用/晋级、summarizer train 资格及 formal 接受均调用。正式行的后检查未通过，不能登记为有效完成。跨 smoke/pilot/formal 的有效静态内容 root 必须一致。

代码更新边界：A010 owns matrix/summarizer/protocol及其 tests、此新 plan；A011 owns worker/run_eval及完整性实现/专用 tests；父负责最后冻结、最终摘要/renderer/publisher兼容和实际调度。新完整性门及额外开销须经 CPU 正负例和 GPU0 受控 smoke 核查后冻结；尚未获得正式结果。
