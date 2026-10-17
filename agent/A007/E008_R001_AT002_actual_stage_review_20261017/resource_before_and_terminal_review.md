# AT002：真实 before 策略及自然失败收尾

接受已闭合的资源准入与 before 策略子步骤。9525 个对象的 exact 身份、schema、原生 RLOC_ORIGIN 返回码和值及策略快照逐个一致：9514 个对象复用本次逐对象资源查询，另有 10 个根／祖先和 1 个根内 u_silu 非 primitive 层级新查询。全部明确记录 unsupported、native0、空值；其他 11 个必需属性均受支持。资源和策略冲突清单为空。[before 审核](actual_resource_before_policy_review.json)。

P 的资源分类为 9483 个 CLB 逻辑对象、6 个 RAMB36、2 个 DSP；16 个 DSP 内部对象和 7 个常量均不在 P。原生目标站点种类具备不等于空闲容量、可打包或可布通，未作此推断。

AT002 于 2026-10-17T07:36:55.602571Z 自然 native1/supervisor1 结束，无 stop／cleanup。失败在 constrain_region 末尾的无效 `write_xdc -constraints physical` 参数；after 快照和 preservation 标记未产生，尚未 place，不能判完整策略保持或物理实现通过。

独立复核 185 个非 DCP 身份、91 个 stage 非 DCP 输入及 144 个生产输入，8 个原 PID/start 身份均已消失，观察时项目 lane 无锁记录。14 项工程收尾检查均通过；DCP 内容哈希明确归属工程。[自然失败收尾审核](AT002_natural_failed_terminal_review.json)。这次入口失败不反驳 C01 卸载假设。

[一行导出修复已集中审核通过](physical_xdc_fix_review/review.md)，按现有委派同 C01 新 AT 继续，不新增批准门。
