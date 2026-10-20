# R003 最终启动只读审核材料

父拥有最终 readiness、冻结副本和实际启动。本文不创建 R003 raw 目录或进程。当前 `ready=false`：89 项消费者 CPU 稳定通过，A011 82 项 CPU 稳定通过，GPU0 BF16 四题已独立完整接受；GPU0 QDQ 终态仍待独立审核。

[命令数组、15 个 runtime 源哈希及现有证据哈希](R003_launch_review_AT001.json) · [BF16 完整终态审核](integrity_v3_gpu_bf16_terminal_review_AT001.json) · [输出路径修订证明](R003_output_destination_review_AT001.json)。

| 旧 readiness 字段/对象 | R003 必须使用 |
| --- | --- |
| `ready` / `scope` / `reviewed_at` | 新终态审核完成后的真实决定和时点，不复制旧 ready |
| `plan_sha256` | 新冻结副本的 SHA；仅输出目标修订后预期 `2e77661b67dc69ed6ae0b75d43580b75975f551cf5a683a498d510e9ba6b1426` |
| `source_hashes` / `frozen_sources` / manifest | 重新读取现有全部 15 个 runtime 源，含新 integrity helper；保留新测试证据哈希，不能用 R002 旧源哈希 |
| `evidence_hashes` | 最新稳定 CPU、源审/AST、请求及输出路径 parity、BF16/QDQ 原始完整性/v2/独立审核及终态回执 |
| `gpu_uuids` | 仅 `GPU-78b42905-e40c-4ab9-30cf-b8e6f7e8c0f6`；worker CPU16–17，supervisor 可沿用 CPU14–15 |
| `package_versions` | 与当前已测 GPU0 实际版本复核；Python3.10.19/Torch2.10.0+cu128/Transformers5.3.0/lm_eval0.4.11 等不能用请求值冒充 |
| verification / integrity | 保持 `native_cache_call_parity_v2`，新增 `checkpoint_static_content_v1` |
| NVML / 资源 | 新本地匹配库查询作为父侧独立监控证据；GPU0 本次已测 `LD_LIBRARY_PATH=None`，不得隐式继承 GPU1 修复对照的局部库环境 |
| 旧估时/旧通过组 | 不复用；BF16 prep 总耗985.565秒、纯生成7.907秒，后续估时须用包含完整性开销的新 pilot |

新 raw run 建议为 `results/gsm8k_full_completion/R003_gsm8k_gpu0_weight_integrity`。父先将 source v3 plan、fewshot schedule、修订说明和 parity 证据放入全新 `frozen_inputs`，只在冻结 plan 修订 `paths.user_display_results` 为当前 Workspace 的 `project/software/0_Software/fix_experiment/results`。旧历史 CSV 路径继续只读。运行中的 source plan 保持；两个 plan SHA 不同必须如实记录。临时副本已证明此单字段修订不影响任何 smoke/pilot/formal 请求、prompt 字节、协议或数值规则。

初始命令完整数组见 JSON 的 `command_not_executed`：使用指定 conda Python、CPU14–15 supervisor、单 GPU0、worker CPU16–17、`--stages smoke,pilot,formal`，新 R003 plan/readiness/run-root。初次不传 `--allow-resume`。同 R 完整 AT 只能在原门和新门均通过后复用；失败/未完成 AT 的 partial 行不导入。无需为此命令加入新 `--driver-library-dir`。启动前由父核 GPU0 准备进程已退出、原锁可获、CUDA 显存及 host80GiB 预留；新 PID/日志/启动回执以真实工具结果登记。

`frozen_contract.json` 应由新 matrix 在真实启动时按新 readiness 生成：新 plan/protocol/source 身份、三 stage 请求 SHA、六 checkpoint fingerprints、全30组到同 GPU0 的固定映射和 integrity ID。不得复制/迁移 R002 contract 或旧6组 smoke。

最终 `finalizer_readiness.json` 必须重新生成，所有 summarizer/renderer/publisher 参数仅指向新 R003 和新冻结 plan；不沿用 R002 旧命令。完整正式验收仍为30组、39570行，由新 summarizer 的完整性门及独立 harness 复算控制。若未准备 finalizer，matrix 会如实停在 `generated_pending_review`，不能宣称已经发布。

CSV 列/renderer 接口不需修改。给父拥有的 publisher 的最小建议：校验 `merged/source_manifest.json` 的 SHA 与 `validation.source_manifest_sha256` 一致，并将其 `plan_sha256` 与传入新 plan 比较；新完整性协议下确认30个 accepted source 都带同合同的完整性引用。现有 publisher 主要绑定 CSV/render，缺少该 source/plan 绑定。本文未修改 publisher；若父实施此兼容，应单独记录该源版本及有意义的正负例，不重复已稳定的消费者 CPU 测试。
