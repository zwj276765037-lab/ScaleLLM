# GPU0推理速度修复报告（2026-10-18）

用户要求已落实：当前ACC矩阵停止，仅对GPU0做有限速度诊断；两个模型诊断进程已自然退出、项目GPU0锁已释放。yqh的PID23186/attempt03始终保持运行，没有向其发送信号、消息或修改任务。GPU1与M003/EDA未操作，每小时ACC提醒仍关闭。正式结果保持0/39570，本报告没有发布ACC。

主要瓶颈是每题前后对全模型权重执行GPU→CPU复制、转bytes和CPU SHA256。旧8B/BF16四题纯生成7.724秒，总worker979.389秒；逐题非生成额外约105–106秒。

修复已生产接入：一次性加载/文件SHA/CPU→GPU身份与原生全形QDQ重建保持；可信不可变CPU字节基线在捕获时再次核SHA。重复检查使用16MiB pinned buffer完整复制并逐字节比较，完整相等后才复用基线SHA/root，明确标记derived hash。所有检查频率、名字/角色/metadata/storage/参数/静态buffer/非持久QDQ buffer/Hadamard cache覆盖保持；capture后host至少余80GiB。8B两配置约多占16.1GB CPU基线，不复制整模型GPU副本。

GPU0真实诊断：Llama-3.1-8B-Instruct，同一四题train、5-shot原样提示、greedy、每题最多64新token，单worker串行。新运行与yqh共享GPU0，旧R003是同GPU/系统驱动的较早基线；下表是观测对比，未取得独占受控吞吐资格。

| 配置 | 旧每题持续间隔中位数 | 新每题持续间隔中位数 | 观测提速 | 旧四题worker总耗时 | 新四题worker总耗时 | 短worker整体提速 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| bf16 | 107.437 s | 9.290 s | 11.56× | 979.389 s | 433.238 s | 2.26× |
| a8w4_fp32 | 112.019 s | 14.246 s | 7.86× | 1148.907 s | 601.538 s | 1.91× |

持续间隔来自相邻generate_one记录的completed_at差值，两版在相同位置记录，均含前题postcheck、下题precheck、下题generation及持久化。四题给出3个间隔，取中位数；不包含加载和最终文件复核。worker总耗时含这些一次性成本，不能把持续提速比称为短worker整体提速。

BF16四题纯生成7.724→8.782秒，量化24.286→24.732秒；生成计算路径本身未加速。主要改善来自完整性检查：真实16GB全静态内容单次约3.4–3.9秒，原约51秒。加载和最终文件SHA仍有分钟级成本。

父核和A010独立审核均通过：两配置各四题请求文件逐字节相同、输入token与所有生成token/文本/stop字段相同；两个32token验证前缀相同；checkpoint/tokenizer/generation/method/packages和完整静态baseline/root相同。每配置仍为15阶段、12个runtime全字节阶段，每次分别覆盖16060523008/16060529152字节，原native_cache_call_parity_v2及变异负例通过；全部声明artifact hash、canonical identity及16源前后/快照核对完整。

生产CPU worker88/88、consumer初版109/109、最终readiness补强后120/120通过；GPU0合成64MiB+37字节5轮中位旧0.220955610秒、新0.015279226秒（14.461倍），首字节/chunk边界两侧/末字节四个真实翻位均被拒绝。合成比值不能外推全模型。受限模型诊断资源guard经独立10/10 CPU测试通过。

恢复准备补强：另查到readiness若省略新旧helper来源仍可能被旧通用入口接受。已在两个模型诊断及16源独立审核完整结束后应用最小拒绝校验，仅改变matrix readiness及新增测试；新模式必须包含生产canonical worker/run_eval/protocol/双helper身份，未知模式/缺来源/伪同basename/错误SHA均拒绝。最终consumer回归120/120通过，21个生产和测试源前后稳定；worker/helper/protocol及其他数值源保持GPU验证时版本，完整16源见[release_sources.json](release_sources.json)。未来候选配置保存为project/software/0_Software/fix_experiment/source/gsm8k_execution_bytewise_integrity_20261018/plan.json，execution_authorized_this_turn=false，尚未创建或启动R004。

限制与后续：此处仅八道训练诊断，最多64 token，不能当作完整GSM8K精度、全部30组资格或完整矩阵ETA。若用户后续恢复，应采用本版完整来源冻结的新R，重新跑全30组smoke→pilot→formal，正式独立复算验收后才回填ACC。旧R003不复用行或资格。yqh保持原样，GPU1排除。

主要证据：

- [BF16父完整核验](/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/E010_gsm8k_six_model_completion/experiment_results/performance_repair/production_integration_20261018/shared_model_diag_AT001/bf16/parent_independent_comparison_AT002.json)
- [QDQ父完整核验](/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/E010_gsm8k_six_model_completion/experiment_results/performance_repair/production_integration_20261018/shared_model_diag_AT001/a8w4_fp32/parent_independent_comparison.json)
- [独立模型审核收件](/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/E010_gsm8k_six_model_completion/experiment_results/performance_repair/production_integration_20261018/independent_model_reviews_received.json)
- [原始来源及数值AST审核](/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/E010_gsm8k_six_model_completion/experiment_results/performance_repair/production_integration_20261018/shared_model_diag_AT001/parent_source_review.json)
- [资源释放与yqh保持](/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/E010_gsm8k_six_model_completion/experiment_results/performance_repair/production_integration_20261018/after_model_diagnostics_resources.json)
- [CPU与合成测试原证据](/home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/E010_gsm8k_six_model_completion/experiment_results/performance_repair/production_integration_20261018/parent_pre_model_validation.json)
