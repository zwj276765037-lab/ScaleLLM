# 已上板验证的工程 bitstream

`ScaleLLM_MLP_GU_only_ENGINEERING_VALIDATION.bit`，80,159,259 B；SHA-256 见 `SHA256SUMS`。

适用 VCU118 / xcvu9p-flga2104-2L-e，core 100 MHz、DDR UI 200 MHz。设计生成于 Vivado 2025.2；Dell 已使用 Vivado 2022.2 下载并完成真实 Llama 32 层推理。该文件为工程验证版，Max-DPO 与外部 reset 物理签核仍有未闭合项。

本目录是原 AT003 文件的逐字节副本；原文件和父 routed checkpoint 保留在研究工作区。下载与接口检查参见 [部署说明](../docs/DEPLOYMENT.md)，资源和验证范围参见 [详细报告](../docs/PERFORMANCE_AND_RESOURCES.md)。
