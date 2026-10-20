最新更正：主锚为wide final_accuracy_comparison.csv六checkpoint，Llama必须选Instruct；secondary截图CSV的base两行不属于用户新截图。见[映射](../actual_checkpoint_source_mapping.json)。此前12行/60显示值验证只针对secondary归档，不代表完整30行截图。

# 新表原始来源定位

A010 工程只读审核。输入为旧软件目录的小型汇总及脚本明确指向的 `0_Software/results` 归档。精确匹配截图锚点的文件为旧根 `0_Software/results/_summary/截图模型精度.csv`；该归档只有 BF16/ScaleCode 12 行。输入 SHA、源路径和样本/指标字段见 [review.json](../review.json)，文件名发现范围见 [discovery_inventory.json](../discovery_inventory.json)。

CPU8–9、empty CUDA、标准库解析，无模型/torch/GPU/EDA 或旧文件写入。
