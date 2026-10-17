# AT003：真实 before、硬 Pblock 与物理导出审核

接受本次已闭合的 before 策略、硬 SLR2 Pblock 创建和物理 XDC 导出子步骤。7 份真实 resource/before 原始账本与已独立逐对象核查的 AT002 内容逐字节相等，9514 个资源对象及 9525 个策略对象的证据可增量复用。[完整审核](actual_before_pblock_export_review.json)。

Pblock 回读为 `m002_exact_hotspot_SLR2`，30 个原生 SLR2 时钟区准确组成 `CLOCKREGION_X0Y10:CLOCKREGION_X5Y14`；IS_SOFT、EXCLUDE_PLACEMENT、CONTAIN_ROUTING 均为 0，成员 9491，原生站点数 78266。9491 个候选既有约束行无 LOC／相对宏／原 Pblock 冲突。

实际生成的 1598546 字节物理 XDC 已只读解析：其中候选成员 9491 个、无重复，与实际 P 的全名称集合完全相同，建区范围和显式硬约束与原生回读一致。另两项默认策略由原生回读明确为 0。原生日志已记录 `E008_QUERY_COMPLETED hard_SLR2_pblock members=9491`，因此本轮实际设计的 `-type physical` 导出成功。没有执行或重新加载导出的 XDC。

after 策略快照和 preservation 标记在审核时尚不存在，因此这不代表完整策略保持、完整 pre-place 或布局通过。资源站点范围覆盖也不等于可用空闲容量或布通。实现正常继续，无新增门。
