# rounding_optimization_runner

内部记录 ID：A019；工程角色；M005 / SM021 / E012 / R007。实际协作身份 `/root/rounding_optimization_runner`；无后代。父主控 `/root`。

目标：在保持既有数值接口与有限位宽的独立软件候选中，验证 Linear 组对齐及可选 PV 项对齐的 nearest-even，检验第32层累计误差。授权、候选边界与资源以 `project/E012_multistage_rounding_precision/experiment_results/runs/R007/optimization_contract.json` 为准；旧 goal 中的生产数值冻结继续保护生产文件，本次只是用户明确授权的隔离数值候选试验。

写入责任：新 `project/software/0_Software/rounding_precision/experiment/rounding_optimization/` 源码；R007 新 attempts/报告；本 A019 记录。Root 于本轮启动后明确移交 E012 三摘要发布与 R007/run.md 的唯一写入责任；共享 mission/index/最终 Root 审核仍由 Root 负责。保留其他执行者所有更改；生产文件及旧冻结源只读。

验证：CPU Fraction 边界 oracle → 同一 GPU worker 原语 → 一份驻留模型，dev4 的 baseline/3候选/common OUTPUT_ONLY 配对初筛 → 合格 provisional 候选 next32dev 配对验证。前4 baseline/reference 必须与 R006 同文档哈希、L2、Top1、TV 完全对齐。保存所有文档和真实位置，不做末端校准；输出原始 hidden、有限宽审计、全部尾部和运行成本。完成后 CPU 独立重算与 Python PNG，Root 最终验收待真实结果。

资源：唯一 GPU0 UUID GPU-78b42905-e40c-4ab9-30cf-b8e6f7e8c0f6，CPU1，RSS8GiB，GPU24GiB；launch free30GiB/runtime free8GiB/RAM32GiB；GPU阶段<=2400s；证据512MiB。只控制本次自有进程；不触碰其他 GPU/EDA，不扩至全1024、PPL、ACC、RTL部署或时序测量。

重要阶段及时使用 collaboration.send_message 通知 Root，并用 console.py 报告真实任务状态。实际 worker PID/PGID/startticks 以 AT001/actual_launch.json 为准；runtime model/effort 未核实时保留未核实。
