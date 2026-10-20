# AT017：apply 调用路径的限定源审核

对象：project/hardware/vivado/scripts/m003_joint_checks.tcl，29,704 B，SHA256 083ac863f89974dbb9e6a29d4409466485f64f7d7fd1140a3e73a42a553e7c54。

结论：源码中有尚未按对象、次数和耗时归因的原生查询。祖先 pblock 成员查询已经在一次 apply 内共享缓存，不能按 payload 数误算成每个 FF 都重新查询。本项仅为自然终态后的性能定位准备，不阻断当前运行、选型、合同或 G4，不增加批准要求。

A006报告 apply1 自约11:45Z仍正常执行，12:05Z CPUticks持续增加、RSS约20.21GiB，未有success/error/终态。本审核未读取运行进程或日志复核这些实时值；不据时间或静默判断挂起，不定位当前执行位置。

## 查询位置与复用边界

| 当前源位置 | 对象与调用 | 复用与可能重复 |
| --- | --- | --- |
| one 40–43；resolve 166 | one每次执行get_cells -quiet -hier -filter NAME==，再验证NAME。resolve逐一验证parent/meta/core_meta/C01四个层级root。 | one没有缓存；这四次验证不填ancestor_pblocks，也不能替代physical或保护清单的后续查找。这里没有list_property。 |
| primitive_scope 99–107；调用179、205 | meta和C01各有一次宽primitive查询。root含左方括号时，100–101截到第一个左方括号前；C01分支可能因此有更宽候选，再以完整root加斜杠过滤。候选读NAME/REF，排除GND/VCC后调用physical。 | 107才对返回的physical对象去重。宽候选数、保留数、多输入映射同一对象的次数和耗时未知；不能把宽查询数当作最终C01成员数。 |
| physical 87–97；one 41 | REF以DSP开头但非DSP48E2时，沿dirname逐层one get_cells并读取REF，找到DSP48E2后返回父对象。这一路径可能访问层级/复合DSP对象。 | 无physical父查找缓存；多个输入若共享父对象，会在primitive_scope最终去重前重复遍历。触发次数、对象和耗时未测。其他对象直接返回原cell。 |
| hard_pblock 217–227、244–247；supported_prop 210–212 | 每个cells循环项在218做一次list_property，后续fixed/macro/RLOC支持性检查复用supported列表。输入来自payload/CE、URAM/helpers及C01 physical结果；C01结果若被提升为DSP父对象，这里可能枚举该父对象。 | 这是已审的函数调用内支持列表复用，不缓存属性值、不跨对象/类型/阶段复用。IS_LOC_FIXED的值在220和244仍各读一次；只有fixed才查LOC/sites。此处没有对每个祖先cell做list_property的代码。每个循环项实际耗时未知。 |
| hard_pblock 229–238；apply 267 | 每个cell先直接get_pblocks。祖先dirname循环中，仅ancestor_pblocks没有该键时才在233 one get_cells、234 get_pblocks -of_objects该层级对象。 | 267每次apply清空缓存，全部hard_pblock调用共享；空结果也缓存。原生祖先查询按本次apply首次遇到的不同祖先发生，不按每leaf重查。每leaf直接get_pblocks、字符串祖先遍历仍重复；缓存不覆盖physical/resolve/protection的one查询。 |
| hard_pblock 236–242；prop 46–48 | direct和ancestor pblock列表concat后未去重。每个非当前目标pblock调用prop检查IS_SOFT；prop每次先list_property，支持时再get_property。 | list_property对象是pblock，不是祖先cell。同一pblock可能在合并列表内、多个cell间重复。全局prop未改，per-cell supported列表不覆盖此处；次数和耗时未测。 |
| apply 291–293；one 41 | 对c01_protected每个名字再次精确get_cells，再读DONT_TOUCH。类型由实际清单名称决定。 | 无共用one缓存；若与先前root/physical父/祖先重合仍再查。仅凭此源码不能断定清单全部为primitive，或给出当前命中/耗时。 |

其他primitive查询在payload115、CE168、原地址137，都含IS_PRIMITIVE过滤；它们不是层级parent属性枚举，但查询及逐对象属性读取也缺当前分段计时。primitive_scope105和physical88重复读REF；meta在resolve181再次读NAME/REF。这里只确认调用机制，不把次数直接换算为耗时。

## 已审部分和定位限制

之前7419的hard_pblock支持列表复用在当前083完整保留。已审cell_row同类复用属于后续snapshot路径，apply不直接调用它；本次未复审或重跑相关CPU测试。CPU语义等价性不证明原生加速幅度。

trace在260–261先写attempt，之后才有require_project runtime(266)、缓存清空(267)、resolve(268)、各hard_pblock(280/286/287/290)、保护清单(291–294)；成功回执最后在297–298写。只有attempt1且尚无success，不能定位到其中哪一项。require_project含来源/运行身份验证；250–255还有create、set_property、resize、add_cells等原生操作，不能只列查询就排除这些阶段的成本。

AT014测得层级parent属性枚举较慢，只适用于当时的对象和诊断调用；不能证明AT017当前在list_property，也不能外推当前cell或pblock的耗时。缺少per-call BEGIN/END、当前对象NAME/REF、阶段完成点、返回大小和累计次数，故不作瓶颈排序、卡点判断或强停建议。

## 自然终态后的准备

若真实证据仍需要定位，可由A006在独立冻结、审核后的后继入口设计低开销计时：分开记录resolve、两次primitive_scope、physical父查询、各hard_pblock批次，以及cell属性枚举、直接pblock查询、祖先缓存miss、other IS_SOFT检查的次数/累计时间，保留少量慢调用对象身份。区分primitive、提升后的DSP父、普通层级祖先及pblock；记录缓存hit/miss、宽候选与去重后数量。

这里只提出准备项，当前不实施、不热改、不另开EDA、不控制运行，不因等待时间结束正常进程。

execution：源审核完成。verdict：静态机制已确认，原生性能归因未评估。applicability：精确checks083。review：信息性、非阻断；G4依原合同等待真实证据。
