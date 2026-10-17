# M002 / SM010 / E006 R004：热点局部候选的同图比较

用户已授权“查明清楚后进行针对性的优化SLR1”及“进行针对性优化后开启下一轮implementation”。本批次是该授权内必要的只读选型和查询修复，不增加用户批准门。用户对原R001的明确停止例外已执行完毕；本批次正常进程仍无墙钟或无输出强停。

## 为什么另开R004

R003/AT001真实闭合的热点UNION有103313条primitive记录，MLP占79277；旧输入前端候选仅1042条，40条失败样本网只命中3条组内CE网、23/657热点负载。旧候选降为探索对照，尚未实施，不能称物理失败。R003的failure_samples、hotspot_ownership、exact_hierarchy_resources三个阶段code0；UNION连接因常量单元optional LOC/BEL属性对齐失败而code1，整次自然终态native1/supervisor1、stop=null，输入与PID/start/锁收尾已核。

R004在修复连接缺项之外新增两项独立候选的exact资源/完整边界比较，因此另开R，不冒用未执行的R003/AT002连接-only执行绑定。原数据、失败、源码与授权记录全部保留。

## 唯一输入与精确目标

同一E005/R004/AT003 physopt.dcp，579969232 bytes，SHA256 `766217926d5e8d01137d0ba39f4512dd2337f9fcbcb788525320b5bd0a810a2d`。沿用原144项冻结生产输入和真实10峰窗tile名单/40失败样本；不重做已闭合全设计primitive导出、失败样本、热点归属或9份exact资源。

A007目标定义：`project/E006_m002_slr1_congestion_attribution/experiment_results/runs/R004/independent_candidate_targets.json`，12016 bytes，SHA256 `8a07bcbef2061ee98d9255ef59c0d94bd27ddfd573990eccc90140518e4dcff5`。本合同采用其中selector、collection、acceptance与不变量；两个候选分别测量和比较，不组成联合迁移组。

- C01：independent 8-row producer1；exact root `scalellm_vcu118_f05_bd_i/core/inst/u_core/u_compute/u_mlp/u_serial_command/u_gate_scheduler/u_swiglu/g_row_branch[1].u_branch_leaf`。
- C02：down weight repack；exact root `scalellm_vcu118_f05_bd_i/core/inst/u_core/u_compute/u_mlp/u_serial_command/u_down_scheduler/u_weight_repack`。

C01原热点8697条primitive记录，独立native资源尚未测；源码输入3072-bit、输出32-bit及tags仅为接口信息。C02原热点2303条、旧全图7260条primitive（7257在SLR1、3未放置），原生资源尚未测；源码载荷2272-bit入/1704-bit出同样不是实际cut net或SLL。NET001的1144个load只有576属于C02，512属于w4half0、56属于join；不把父范围归因搬给子块。

## 原生工作与覆盖

1. 新独立源及输出目录，复用已审监督器/真实原终态准入，重新核身份并打开同DCP。optional属性批量长度不齐时逐对象回退且每对象保留一个值（含空），记录属性/context/vector/scalar/error；NAME/REF/DIRECTION等必要身份未知须显式失败。以失败相关9对象的原生probe核补丁，不热改运行中源。
2. 各root必须唯一且原生NAME等于字面root；`[1]`是字面值，宽查询后再按literal前缀筛选。保存RAW、只排除GND/VCC后的S、真实physical/placeable对象P及映射/未知。DSP内部对象按实际父关系归一；保留存储、时钟/控制资源，不套旧E007无BRAM/8DSP/双12288银行等断言。
3. 每候选一个exact hierarchy原生SLR资源报告；raw primitive、native LUT/FF/BRAM36eq/URAM/DSP、shared/exclusive站点分别报告。保存当前真实位置与LOC/BEL固定状态、Pblock/SLR/RLOC/macro及相关属性；不创建或更改区域约束。
4. 完整枚举每候选S附着的canonical nets和segment aliases，追全primitive IN/OUT/INOUT以及top ports端点，保留内外membership、实际位置、时钟证据、REF-aware类别和无/多driver/unknown。顶层方向按外部driver/load解释。保留内部附着网供失败样本匹配，边界net须同时有组内和组外端点；计数/alias/覆盖闭合，不截断成top-N。
5. 对当前physopt图的完整boundary端点集合查询入/出、max/min各最多16条路径，记录集合、原生命令、返回路径、clocks/slack/delay/异常。空、不可用与失败分别记录；cap16不是全cut TNS或签核，不能推造迁至SLR2后的时序。
6. 与已闭合10窗UNION和40个失败canonical样本网交叉，保留NET ID、driver/load/内外/位置关系，不把raw记录数当物理资源，也不把当前跨区负载当未来SLL需求。
7. 修复并补全原UNION连接，原10窗范围保持，旧IN/OUT覆盖与新candidate完整INOUT/top覆盖分开声明。优先交付候选资源/成员与各已闭合数据；共享时钟/常量等查询可在同会话缓存复用，不能以缓存或提速理由漏端点。

## 判断与后续实现

执行完整性、候选适用性与物理收益分别判断。A006提交实际查询/阶段/终态与输入/资源/PID/锁事实，A007交叉核两候选的完整资源、边界、约束和有界时序。相对SLR2实际剩余容量、站点共享、数据/控制跨区代价、热点与失败关系比较；最多推荐一个，或明确二者均不适合直接迁移。容量计数能容纳不等于打包或布通。

在真实证据到达前candidate_supported=false。若有候选支持下一实现，主控据实际范围绑定对应实现合同/入口，先原生pre-place重解析和完整cut/约束资格，再连续完整implementation。新物理实验与本只读批次分开记录；本合同不预先批准任何查询结果为成功。

## 不变量、资源与分工

不改RTL/XDC/IP/ABI/时钟/算法、Hadamard/ScaleCode/format05。只读诊断不执行综合、place/phys_opt/route、Pblock修改、write_checkpoint、bitstream、板卡/GPU/PPL/ACC。旧工程严格只读，全部原始产物不覆盖。

A006唯一EDA执行者，拥有R004工程源/实际运行/工程facts；A007拥有targets和独立对照审核，不运行EDA；root拥有合同、实际执行绑定、记录/三摘要和共享索引。最多3个活跃agent含root，无后代，保留他人改动。期望与实际模型配置继续分别记录，不重新绑定旧会话。

仅一个EDA，CPU0–7/nice5/max8；树RSS192GiB、MemAvailable低于48GiB持续30秒、磁盘低于30GiB按既有保护处理。正常运行不因时间或静默强停，只管理本任务PID/start。实际新R004绑定真实用户历史停止范围、原replacement授权、R003/AT001自然失败status/facts、本合同与targets身份；源码有界审核和真实资源准入后直接执行，无新用户许可。
