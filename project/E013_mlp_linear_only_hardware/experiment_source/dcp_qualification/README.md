# AT004 同一DCP的独立原生资格检查

AT004 保持 FAIL：23 个 synth_design 命令及完整DCP写出成功，末尾查询未匹配 OOC 模块前缀且误拒 pre-opt dbg_hub_CV。AT007 关闭不存在设计的入口失败；AT008 已原生确认精确模块及24级reset结构，随后clock查询的对象集合类型报错，亦保持原结果。当前 AT009 修复原生集合后实际打开同一 DCP。

AT004_origin.json 绑定原始失败、23份原生成功日志、DCP SHA、1433项综合后生成文件、原质量报告和530/554个DDR debug对象。AT004_requalification.json 绑定当前清单和四文件准确差异；旧版 AT007 transition/patch 已另存，原attempt中亦有当时的副本。

四文件仅为 build/runner 的查询、原生资格、阶段检查与两XDC各删除一条literal puts。RTL、IP、ROM、source graph、生产shape和有效约束逐哈希保持。旧 diagnostic_cleanup 的13case仅针对未应用草案，不能充当当前恢复证明。

新原生检查精确实例和完整模块类型、100/200MHz实际pin clocks、有效XDC/ports及已审核6条reset链的24级寄存器/ASYNC_REG/相邻连接。原timing/DRC/CDC保持原字节和FAIL/PENDING含义，未重新计算。只有新native0、无漂移/保护/残留且所需工件完整，才签新成功资格回执；不接受任意失败父。

后继实现消费该成功回执及同SHA DCP。在同一原生流程opt后、place前，强制全部黑盒消除，记录原530/554个对象消失或实际clock覆盖，并复查6条同步链；不预判debug占位自动解决。6条CDC critical和其他CDC warnings不作waiver，最终物理质量独立判断。

post_opt_debug 中的 removed 只表示原精确对象名不再命中；不是全部debug逻辑已删除的证明。该局部PASS仅覆盖零黑盒与指定旧名对象的存续/clock查询。get_clocks非空不等于最大/最小延迟约束充分，最终完整unconstrained、timing、CDC和route仍独立保留及判断。
