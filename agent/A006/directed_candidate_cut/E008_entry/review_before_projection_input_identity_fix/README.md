# E008 完整 implementation：候选有向边界入口

这是独立于旧 b59 包的新入口，继承原 E008 合同并采用 2026-10-17 范围修订。候选仍未选定；CPU 准备不代表已启动或获得原生资格。生产 RTL/IP/ABI/数值/时钟不改，不运行 bitstream、板卡、GPU、PPL/ACC。

共享 `directed_exporter.tcl` 与 `directed_evidence.py` 与已冻结 E006 R005 包字节相同。pre-place、place、physopt、route 每阶段在实际图重新构建本地 leaf、DSP children/origin-copy P、完整 aliases、原生 class 与角色资格。唯一外部 driver 的网仅省略外部普通 peer LOAD，其他网完整回退；整网覆盖与 directed-boundary 完整性分开声明。

原 b59 pre-place 恢复、80 保护、原时钟/复位/CDC/IO 资格、资源可迁移性、实际约束/宏/Pblock冲突检查与 SLR2 hard/nonexclusive/non-routing-contained Pblock 保持；物理命令仍为 SSI_SpreadSLLs place→Default physopt→Default route，包含正式 setup/hold/PW、完整路由、DRC/资源与全局原生报告。每阶段 actual P 全部符合 SLR2 才能通过 locality；正式安全结论仍需真实验证。

## 实际 P 与证据投影

原 `candidate_P_<phase>.tsv` 是该阶段 literal resolve 账本；post-place/physopt/route 的实际迁移对象还可能包含经原生 origin 核实的 root 外 copy。native collector 直接使用 reconcile 后的真实 P。

CPU adapter 在新的 `candidate_directed_validation_<phase>/` 中建立只读符号链接视图：RAW/S 对应该阶段 literal 账本；P 对应同阶段已经闭合且 `qualified=true` 的 `candidate_reconciled_P_<phase>.tsv`；pre-place 使用当时 native literal P。所有 local owner/pin/alias/role/endpoint/timing 表均指向同阶段原文件。原始 literal P 不覆盖，不跨图沿用成员或位置。

共享 validator 对此视图核实际 P→native owner→local leaf→retained endpoint 及方向时序集合，结果内 artifact identity 解析为真实原始文件。投影身份按新增版本留存，既有输入身份不能变化。此视图不修改设计，不伪造新原生查询。

## 运行依赖

`launch_detached.py --attempt <真实新AT> --report <真实新报告> --e006-closeout <Root实际closeout>` 仅在真实单候选选型、E006 终态/PID/start/输入/锁收尾闭合后可运行；不排队，不控制 E006。

closeout 需包含 `phase=E006_attribution_closed`、`successor=SM012/E008`、`engineering_execution_verified=true`、`candidate_scope_supported=true`、实际 `selected_candidate` ID/root、真实证据及 terminal_status identity，并同时绑定：

- `base_contract`：原 E008 合同实际 identity。
- `scope_revision`：本次 candidate_directed_cut_v1 修订实际 identity。
- `preparation_manifest`：本目录最终 prepared_manifest.json 实际 identity。

单 EDA、CPU0–7/nice5/max8、树 RSS192 GiB、可用内存48 GiB持续30秒、磁盘30 GiB保护保持；正常进程无墙钟/无输出强停。
