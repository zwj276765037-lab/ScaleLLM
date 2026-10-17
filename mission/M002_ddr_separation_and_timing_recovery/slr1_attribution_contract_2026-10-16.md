# M002 / SM010 / E006：SLR1拥塞快速归因

用户在Q002讨论“模块×SLR资源、热点贡献、连接及真实失败对应”后明确授权“火速去查明”。本轮执行只读物理诊断和工程解释，E005的失败终态不改，不启动新的implementation。以最少检查点打开次数取得有区分力的事实，优先输出第一批模块/热点排名；常规查询及入口错误在本授权内修复，不增加审批门。

## 输入与不变量

平台沿用VCU118 / xcvu9p-flga2104-2L-e / Vivado2025.2，core100MHz / DDR UI200+200，Attention→DDR0、MLP→DDR1；算法、数值、ABI、RTL、XDC、IP、约束均保持。唯一实现根project/hardware与project/software；旧工程严格只读。不得运行综合、place、physopt、route、write_checkpoint、bitstream、板卡、GPU、PPL/ACC。

优先仅打开E005 R004/AT003原physopt.dcp，SHA256 `766217926d5e8d01137d0ba39f4512dd2337f9fcbcb788525320b5bd0a810a2d`，579969232字节。原E005的144输入manifest保持。复用其R006/AT003实际NW001–NW010 tile名单与原48行/12峰行关联，不重新创造拥塞坐标。E005 route_failed.dcp（SHA256 `6d1cf5ef3fea7b8ca0ab7ba27aaa61383ce487a640bcb63248cb6a9af7009590`）仅在确有不能由原日志和physopt回答的路由归属问题时，另开范围明确的只读AT；failed图不作签核或成功父链。

## 必须回答的问题

1. 当前互斥模块归属×SLR的实际资源分布：Attention、MLP、权重缓存/加载/核心其余逻辑、DDR0/DDR1、PCIe和其余互联。原生report_utilization -cells -slr按唯一精确实例取得，向SLR1主要贡献者展开相关子模块。表中total与exclusive口径分开，未分类实际对象单列，不混旧E003分布。
2. 新峰10区域各自及去重并集的实际模块资源构成。根据实际tile/site/primitive/完整hierarchy归属，报告LUT/寄存器/存储/DSP/站点及来源；父子层次不重加、跨模块共享site不假设互斥，DSP拆分primitive不按记录行数算DSP。全部区域相互重叠，不能累加区域总数。固定窗口拥塞API未验证仍UNAVAILABLE，占用不是拥塞。
3. 主要贡献模块与热点连接的源/负载位置、模块及SLR关系，区分宽数据和CE/reset等控制，unknown/multidriver/未放置单列。合并hierarchical segments，区分unique nets、leaf pins、跨SLR负载与SLL；说明全量覆盖和有界选样。重点判断是否模块资源集中、内部控制跨区、模块间宽连接或共享互联压力，不能以一个top net代替整体解释。
4. 与E005真实route失败节点/contender信号交叉验证。先复用原日志全部top10节点样本并保留行号与每节点最多5条的限制；查询所涉net实际模块/位置。若提取更多冲突需核实接口和实际覆盖，不预承诺完整百万级冲突清单。说明密度热点与路由失败样本是否重合，相关性不等于单项因果。

## 交付与验收

E006/R001为工程只读查询和各次AT；R002为CPU资料分析与独立审核。交付模块×SLR表、热点模块排名、主要连接关系与失败样本关联，以及按证据排序的原因、未知项和下一步最小区分实验。重要数字指向原生报告/原对象，不以工具code0替代覆盖正确。保留原始命令、源/DCP身份、查询回执、真实退出、资源、PID/start与锁收尾；原检查点与144输入执行前后保持。普通定位和必要只读补采持续至本轮问题在可测范围内回答，不追求无法由观察证明的因果断言。

## 分工和资源

- 主控：合同/SM010、goal/mission/results、E006三摘要、Q002答复及共享索引；整合判断和用户报告。
- A006（复用m002_build_verify，期望gpt-6.1-sol/xhigh）：唯一EDA调度者，独占E006/R001、新只读脚本/launcher、工程报告和agent/A006。生产树及旧尝试归档不改，复用可靠guard；常规入口修复自主继续。
- A007（复用m002_physical_architecture_review，期望gpt-6-astra/xhigh）：独占E006/R002和agent/A007，CPU并行准备模块与失败样本targets、分析RTL职责和独立核验结果，不启动EDA。

最多3个活跃agent含主控，无后代。多人共享工作区，保留他人改动；各文件单一负责人。模型期望与实际配置分开，实际仍未独立核实；不重绑旧长期会话。

单重工具、CPU0–7/nice5/max8线程；树RSS192GiB，MemAvailable低于48GiB持续30秒，磁盘低于30GiB才按保护处理。正常进程无墙钟/无输出强停。只管理本任务PID/start身份，不影响其他项目。工程第一批闭合数据及时消息交付，独立分析可并行，不等全部诊断结束才报告。
