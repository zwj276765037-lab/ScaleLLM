# AT003 C01 完整有向cut与实际索引投影独立审核

接受本次C01完整cut：原生query/stage均0。实际归档cut/逐网JOIN算法独立重放，结果与工程native_result完全相同；十份完整语义账本与已接受R005逐字节一致，全部非身份语义汇总也相同。14,307次新TOP_PORT_INDEX_JOIN逐一与旧真实ALL_TOP_PORTS查询比较，完整segments、端口名称及方向均相同（全部端口投影为空）；纯投影没有伪装native_tcl_code，完整候选覆盖未扩大。

实测14,307 canonical nets、55,605候选leaf pins、58,361保留端点；3,087 reduced/11,220 full，3,087 ingress/55 egress，21,479边界driver-load对。先前C01连接代价判断直接复用：3,072条data/select输入网形成6,144对，外向945对中896落外部row-ring BRAM；未知/常量/时钟位置及兄弟控制耦合限制保持，不重新解释为必然布通。

重放仅对index validator的DCP内容哈希做明确范围处理：执行其完整native语义路径require_closed=False，独立补核全部非DCP闭合marker/source/artifact/input-path检查，DCP内容身份归工程真实闭合证据。原归档代码文件未改、没有读取DCP或执行EDA。sidecar/index实际资格复用刚完成的独立审核。

当前接受完整cut，不预填新timing、C02结果、候选选择或物理通过。后继比较复用既有C01已审时序，并以C02实际完整结果确定单候选实验。

[逐项身份、真实重放和14,307网投影比较](C01_cut_review.json)
