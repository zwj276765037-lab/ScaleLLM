# R002/AT002 Python环境适配独立接受

A007无实质阻断：可按已有授权立即以新AT开始fresh create/synth。适用42源manifest `d1f904569c6818c0827f7048a0b0961104a1868c6b242779b8289f4ad03bb697`；G3b v3已接受的非变更部分继续适用，G4/物理仍未通过。

已核5份实际M003调用Tcl的完整diff+新增272B `m003_system_python.tcl`；36旧源逐SHA相同，三RTL/选型/池/预算/策略不变。新wrapper仅对子进程清除PYTHONHOME/PYTHONPATH，保留Vivado自身环境与legacy分支，Tcl list参数和失败传播语义保持。42源及回归44个原件/归档绑定全部匹配，工程191 tests（其中46资格）原log全成功。

A007独立46项资格重放exit0（chunk b74356），含污染负例、净化正例、实际entry和参数/父环境。另直接source实际constructor前缀：在污染环境成功取得43项源，按预置version stub停于原生API前；此仅验证真实启动前缀，不冒充Vivado/native通过。重放后42源不变。

A007第一次重放因login shell改变cwd，未导入tests即失败，原log保留；显式login=false重放通过。AT001原生失败也保留，不覆盖或改写。后续仍以真实create、新综合与G4包分别审核。[正式JSON](AT002_python_environment_fix_review.json)。
