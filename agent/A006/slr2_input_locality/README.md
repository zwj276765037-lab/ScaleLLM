# E007 输入局部性 SLR2 实现入口（探索对照，未执行 EDA）

R004热点证据已使本候选降为探索对照；不作为默认下一implementation，未生成ready。2026-10-17在独立源码中修复optional属性批量空值对齐及出/入组时序负载集合，保留旧B049/7f6源与manifest；当前native资格仍未验证。

源码唯一写入者 A006；本目录不控制 E006，不改生产脚本、RTL/XDC、E005 原报告或旧工程。实际后继身份为 SM011/E007。CPU 交付关联 E007/R001/AT001，物理尝试预定 R002/AT001。

- `candidate_hooks.tcl`：与 A007 相同的字面前缀/排除规则，分别保存 RAW、S、P 和映射。RAW 含常量；S 排除 GND/VCC；P 把获准 DSP 内部对象归一到 Hadamard 内实际 DSP48E2 父对象，仅接受已审核 logic/DSP REF；选中 clock/IO/BRAM/URAM/未知 REF 会报错。当前 physopt 参考为 77360 / 77246 / 77182，不能作为 pre-place 匹配数量保证。
- `runtime_hooks.tcl`：补充原有 Pblock/SLR/宏和相对位置政策前后核查，实际 Pblock 与原生 ORIG_CELL_NAME 对应先归并、解释 missing/clone，再对阶段实际 P 导出完整 cut。缺失或新增对象没有足够原生对应、成员覆盖不一致、属性或实际 SLR2 服从不成立都会阻止下一阶段。RLOC/宏兼容证明不足或必要 API 不可用时保留未验证并报错，不清除原政策。
- `evidence_adapter.py`：复用现有原生 POST、reset/CDC/clock/IO 与原 80 结构门限，只适配真实 E005 成功来源及程序化位置约束。OPT 继承真实原生日志证明，没有虚构 timeout 或独立 OPT 收据。正式安全仍 OPEN。
- `implementation.tcl`：由 `prepare.py` 有界改写既有控制器；同一会话恢复、检查、完整 cut、place SSI_SpreadSLLs、physopt Default、route Default。原生失败由既有 capture 保存，POST 失败也保留可获得的局部性证据。
- `run_candidate.py`：复用已用过的监督/身份辅助函数；非阻塞单 EDA 锁、实际 E006 收尾和工程依赖、144 冻结输入、父链与准备源身份均须通过。CPU0–7/nice5/max8、RSS192GiB、MemAvailable48GiB/30s、磁盘30GiB；无墙钟或无输出 watchdog，无旧 timeout 恢复标志。

hard Pblock 从真实 SLR2 clock-region/site 集建立并展开核对，读回 `IS_SOFT=false`、`EXCLUDE_PLACEMENT=false`、`CONTAIN_ROUTING=false`；原 LOC/BEL、macro/RLOC/Pblock 记录并保留，冲突不自动清除。设置成功不等于迁移成功，后续各阶段须核实际 SLR2 服从情况。缺失原对象、新 Pblock 对象和有真实 ORIG_CELL_NAME 对应的副本分别记录，不凭名称后缀推断复制。

完整 cut 包含 RAW/S/P 全部附着 canonical nets、IN/OUT/INOUT/未知 leaf 端点和 top ports；top IN 为 driver、top OUT 为 load。REF+REF_PIN+原生 clock 证据区分 DSP.C 数据、FD.C 时钟及 clock buffer 输出；未知语义明确保留。端点另有 BEL/site/tile/clock region、owner/detail 和原生寄存器时钟组依据，查询不明保留 UNKNOWN。canonical net、cell、site 信息缓存；cell 属性分批读取，pin 属性按 net 批量读取，不调用大 leaf-list utilization。全部 candidate pin 名单另存；没有精确 leaf 匹配不冒充已知断连。阶段切口时序按 ingress/egress/unresolved 和 min/max 诊断，每组最多16路径，保留原全局/所有时钟门限；有上限路径不代表完整 cut TNS。

CPU 准备不创建物理 `started.json`、不取 EDA 锁、不打开 DCP：

```text
python3 /home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/agent/A006/slr2_input_locality/prepare.py
```

已完成一次闭合 physopt 导出的有界选择器核查与 59 个 Python/Tcl 字面案例；literal selector 未变，继续引用原案例。bindable/REF 接纳逻辑已实改，集中修复 CPU 检查复用原 REF 分布逐类核对，并覆盖不支持 REF、REF-aware pin、missing/unknown/跨前缀 clone/Pblock 覆盖反例；未重扫676MB导出。旧准备源与 manifest 保存于 `review_before_runtime_fixes/`。`parent_CPU_validation.json` 是真实成功父来源的 CPU 核查，适用于其中记录的 adapter 修订。最终新会话仍会重新核父链与实际图。原生选择/几何/宏与SLR政策API、完整连接 cut、切口时序和任何新物理阶段仍未验证。

启动只剩以下必要依赖：

1. E006 实际结束，热点/端点归因支持该边界，主控/A007给出有证据的工程收尾；所有登记 PID/start 已退出且释放单 EDA 锁。
2. 集中审核准备源后，主控绑定真实 E006 工程收尾 JSON。它是阶段依赖，不是新增用户审批。JSON 必须包含 `phase=E006_attribution_closed`、`successor=SM011/E007`、`engineering_execution_verified=true`、`candidate_scope_supported=true`、`terminal_status`（真实 status.json 的 path/bytes/sha256）和非空 `evidence` 身份列表。当前尚无此收尾，不生成虚假的 true。
3. 使用未占用的下列 R002/AT001/report 路径。原生 pre-place 身份、索引、几何/冲突、约束读回、完整 cut 和 live 资格均在同一新会话内检查，失败不得越过门限进入 place。

实际执行命令（当前不可运行，E006 尚未结束；此命令不会排队等待或绕过依赖）：

```text
python3 /home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/agent/A006/slr2_input_locality/run_candidate.py --attempt /home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/E007_m002_slr2_input_locality_implementation/experiment_results/runs/R002/attempts/AT001_pre_place_SLR2_full_implementation --report /home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/project/hardware/vivado/reports/m002_E007_R002_AT001_pre_place_SLR2_full_implementation --e006-closeout /home/user/EDA-202/zhuowenjun/Workspace/ScaleLLM/results/reviews/SM010_E007_readiness.json
```

CPU/源码审核不能保证下轮布通。最终报告分别给出卸载是否生效、压力变化、合法路由、setup/hold/PW 和尚未关闭的全局安全；不运行 bitstream/板卡/GPU/PPL/ACC。
