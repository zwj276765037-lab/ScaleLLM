# AT003：两候选成员与 C01 class schema 独立阶段审核

执行：本次有界审核 completed；判断：两候选实际成员资格及 C01 class schema 得到支持。适用源为 R005 b330、实际 AT003；此处不选择候选，不代表cut/时序或物理资格通过。

C01/C02 的实际 query 和 stage code 均为0，运行内系统Python适配器生成资格JSON。RAW/S/P分别9514/9507/9491和7260/7257/7257；12份当前成员/物理/共享站点账本独立实核哈希，全部同已独立复核的AT002字节一致，RAW/P集合不相交。资源报告仍为R004复用，不冒称新测。

C01实际原生list_property -class pin与list_property_value DIRECTION -class pin均返回0；NAME、DIRECTION、IS_LEAF存在，DIRECTION实际枚举为IN/OUT/INOUT/MIXED/UNKNOWN。MIXED/UNKNOWN在既定non-IN角色库存内保留，后续逐网适用判断不能将其当普通IN丢弃。class级schema资格不等于逐网native_role_gate已通过。

[完整身份与字段核验](membership_C01_schema_review.json)保存12234 B独立记录。local leaf/alias映射、逐网角色与回退、完整候选cut、有界方向时序及真实终态仍待阶段证据；最终仅可选一个获支持候选进入E008 da34。

未执行EDA、大DCP读取、生产写入、信号或锁控制；实际运行继续。
