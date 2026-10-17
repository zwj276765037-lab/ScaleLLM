# AT002 失败适用性与系统 Python 入口修复审核

执行：独立有界审核 completed。判断：R005 `b3308185` 与后继 E008 `da34c310` 的系统 Python 适配得到源码与 CPU 集成支持；原生 class/role/cut 和候选收益尚未在本审核证据中取得。实际选型仍须完整候选边界与有界时序。

AT002于01:45:04Z自然失败，native/supervisor=1/1，stop=null、cleanup=false。两个实际 `readonly_resolve` 均写出closed；首错发生在后续 `exec python3` 的适配器导入，traceback指向Vivado自带Python3.13的tkinter，缺少 `_tkinter`。因此owner修复已在实际入口生效，Python资格判读、class/role/cut未执行完成。原始失败状态保持。query_receipts包含未转义多行traceback，旧逐行TSV解析的order=false不能解释为实际查询缺失。

已有真实成员证据可复用：独立使用AT002归档validator、系统Python和另存输出，完整核对RAW/S/P、membership、physical_members、site_members与闭合R004相等；两个root一致，RAW/P不相交。C01为9514/9507/9491，C02为7260/7257/7257。[离线适用性记录](AT002_membership_applicability.json)。这不改写原运行querycode，也不冒充新资源测量或候选支持。

新包装通过绝对`/usr/bin/env`清理子进程的Python、动态库、Tcl/Tk变量，禁用user-site后使用绝对`/usr/bin/python3`。没有改Vivado父进程环境、图或约束。保留原tkinter.Tcl原生list解析；原split/tdict及全部directed验证函数AST不变，collector只有适配器调用替换。E008除main新增预检外的适配函数AST保持；真实加载旧diagnostic_common与新hooks后，m002_post两处、live_restore一处均已改为包装调用，所有实际加载过程无裸exec python3。

独立执行两个完整真实Tcl入口，并在运行Tcl中设置vendor PATH、PYTHONHOME/PATH/PLATLIBDIR/USERBASE、LD_LIBRARY_PATH/PRELOAD、TCL/TK_LIBRARY和launcher污染。真实Python适配器及_tkinter导入成功，系统Python3.12/Tcl8.6.14；R005在mock open_checkpoint前、E008在mock open_project前已写真实预检。只模拟version/thread参数/设计打开边界，没有替换适配器、helper或list解析。故意制造的多行错误保留完整原错误文件，新的TSV为3行、每行5字段，换行/tab明确转义。[独立测试](independent_runtime_entry_checks/results.json)。

R005最终15源/10CPU/19外部、11runtime含wrapper，实际只读verify_preparation通过；E008最终14own/16reused/3CPU/2运行二进制依赖及双合同，实际verify_manifest通过。共享collector/validator/wrapper一致。E008 runner仅增加运行二进制身份和stage_inputs绑定，原POST、80保护、约束/来源、选择依赖、单EDA及无墙钟/静默强停保持。[R005身份](R005_final_b330_identity_review.json)、[E008身份](E008_final_da34_identity_review.json)。旧558c/a660/1d612及失败证据不覆盖；后续E008真实选择应绑定da34。

另已完成[候选保护与容量前置要点](candidate_policy_capacity_notes.md)：C01必须保留25个DONT_TOUCH，C02保留24个；祖先/继承Pblock/组外macro资格仍需fresh pre-place。源CLB大多共享，SLR2 CLB已93.07%，不以触及站点数宣称直接释放。完整cut与时序前不选候选。

本次无EDA、大DCP读取、工程源写入、信号、锁控制或后代。适配是已有授权内常规修复，不增加用户批准门，也不把入口修复当原生成功或布通保证。
