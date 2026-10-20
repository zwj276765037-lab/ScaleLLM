最新更正：主锚为wide final_accuracy_comparison.csv六checkpoint，Llama必须选Instruct；secondary截图CSV的base两行不属于用户新截图。见[映射](../actual_checkpoint_source_mapping.json)。此前12行/60显示值验证只针对secondary归档，不代表完整30行截图。

# 新表定位状态

- execution_state: completed
- verdict: 精确定位 BF16/ScaleCode 归档；另 18 控制行及逐题复算受原始路径缺失限制
- applicability: [review.json](../review.json) 的具体输入 SHA 与旧归档版本
- review: 父级整合待收
- measured_progress: 12 匹配行、60 个 MCQA 显示值已核；84 个被引用原始路径当前均不存在
- blocker: 原始 fpga_llm_project/results 根缺失，未扩大盲搜
- resources: CPU8–9/empty CUDA；无 GPU/模型/EDA/进程操作
- next_step: 主控结合其他来源证据向用户说明全 split 与 first300 的区别；本任务不新增 ACC 运行
