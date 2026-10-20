# AT008–AT010：单层 BF16 权重身份诊断

执行范围：M004/SM020/E010，Llama-3.1-8B-Instruct，train:0000 的相同 891-token 前缀，原生 BF16/eager。未修改生产冻结源、验证门、后端、驱动或矩阵；本记录不构成正式 GSM8K 资格。

| 尝试 | 资源与原生进程 | 实测 |
| --- | --- | --- |
| AT008 | GPU1 / CPU18,19；PID292095；03:49:03Z–03:49:49Z，自然 exit0 | 四次 native 输入全字节相同，目标权重 SHA 改变；固定最终权重后，F.linear、复用输出 mm、新分配输出 mm 各6次完整输出全精确一致。 |
| AT009 | GPU1 / CPU18,19；PID295295；03:54:58Z–03:55:39Z，自然 exit0 | 加载器返回后的目标权重已有16345个 BF16 元素与 checkpoint 不同；尚无 native generate 的连续快照之间又改变35和2元素，parameter version始终0。独立新 GPU allocation 的正确权重3次 roundtrip 精确一致。 |
| AT010 | GPU0 / CPU16,17；PID296821；03:57:27Z–03:58:01Z，自然 exit0 | 同版脚本的17个完整目标权重快照全与checkpoint相同；两次 native 的目标输入/输出及最终 logits 全字节一致。独立正确权重3次 roundtrip 也精确一致。 |

AT008最终保存权重与原始 safetensors 的 CPU 对照：16345元素/16345字节不同，64行，高字节变化0，最大绝对差0.09326171875；其中16282个新低字节为0xff，12元素含清除bit。该结果及完整输入/输出原始张量已由A010独立复算（审核文件由A010维护）。

最窄结论：此次原始参数分配在GPU1上的读回内容未维持checkpoint身份；相同脚本在GPU0和GPU1的表现不同，而且GPU1另分配的目标张量可正确读回。当前证据未区分加载路径、特定存储分配、读回路径或设备问题，不能宣布整卡损坏或已修复。

边界：AT008 native1/native2具有相同的调用前权重SHA却输出不同；AT009目标权重稳定后，两次up_proj输出相同而最终logits仍不同。单层观察不能解释所有剩余差异。AT009/AT010保存了所有目标权重快照、坐标/位差、storage/pointer/stride/version及实际诊断前hook/parametrization清单；目标及其父级/global hooks为空、未parametrize。

建议主控维持formal/matrix停点。任何修复先要验证当前checkpoint完整性与GPU参数内容守恒；如继续，采用单独新AT的定点allocation/受保护重定位试验。当前无生产修复通过证据，不建议改阈值、盲目warmup或换后端。

- [CPU复算汇总](analysis_AT008_AT010.json)（含冻结源身份和资源收尾核验）
- [AT008原始记录](AT008/diagnosis.json)、[完整操作数/输出](AT008/raw_operands_and_outputs.pt)、[checkpoint CPU复算](AT008/checkpoint_weight_comparison_recomputed.json)
- [AT009原始记录](AT009/diagnosis.json)、[AT010原始记录](AT010/diagnosis.json)
- [可复现CPU汇总脚本](analyze_lifecycle_cpu.py)

早期AT008补采文件`checkpoint_weight_comparison.json`及`bf16_write_path_inspection.json`保留为过程记录，以对应`*_recomputed.json`和本汇总为当前解释。原生AT的diagnosis.json和source_snapshot.py未重写结论。
